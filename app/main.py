"""RM Lab – webové API + statický frontend."""
import datetime as dt
import json
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from . import ai, enrich, places, sites
from .auth import hash_password, secret_key, verify_password
from .config import (ADMIN_NAME, ADMIN_PASSWORD, ADMIN_RESET, ADMIN_USER, AUTO_IMPORT, BASE_DIR, CLAIM_DAYS, ENRICH_MAX,
                     HTTPS_ONLY, LOGIN_MAX_FAILS, ROOT_REDIRECT)
from . import checklist as checklist_mod
from .db import connect, get_meta, init_db, set_meta
from .geo import bbox, haversine_km
from .refdata import (FORM_GROUPS, FORM_LABELS, NACE_DIVISIONS, PRESET_LOCAL_SERVICES,
                      katpo_label, katpo_rank, nace_division, nace_label)
from .scoring import score
from .webcheck import strip_accents

STATIC = BASE_DIR / "app" / "static"

STATUSES = {
    "new": "Nový", "claimed": "Rezervováno", "contacted": "Osloveno", "interested": "Zájem",
    "meeting": "Schůzka", "won": "Zakázka", "lost": "Nezájem", "do_not_contact": "Nekontaktovat",
}
FINAL = {"won", "lost", "do_not_contact"}
OUTCOMES = {
    "no_answer": ("Nedovolal/a se", "contacted"),
    "callback": ("Zavolat později", "contacted"),
    "not_interested": ("Nemají zájem", "lost"),
    "interested": ("Mají zájem", "interested"),
    "offer_sent": ("Poslána nabídka", "interested"),
    "meeting": ("Domluvena schůzka", "meeting"),
    "won": ("Zakázka", "won"),
    "do_not_contact": ("Nepřejí si kontakt", "do_not_contact"),
    "note": ("Jen poznámka", None),
}
CHANNELS = {"phone": "Telefon", "email": "E-mail", "visit": "Osobně", "other": "Jinak"}

app = FastAPI(title="RM Lab", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=secret_key(), max_age=60 * 60 * 24 * 30,
                   same_site="lax", https_only=HTTPS_ONLY)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def _startup():
    init_db()
    with connect() as conn:
        # první admin z proměnných prostředí (na serveru není kde spustit manage.py adduser)
        if ADMIN_USER and ADMIN_PASSWORD and not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            conn.execute("INSERT INTO users(username, display_name, password_hash, is_admin) VALUES (?,?,?,1)",
                         (ADMIN_USER.strip().lower(), ADMIN_NAME or ADMIN_USER, hash_password(ADMIN_PASSWORD)))
            print(f"[rmlab] založen admin {ADMIN_USER}", flush=True)
        elif ADMIN_USER and ADMIN_PASSWORD and ADMIN_RESET:
            uname = ADMIN_USER.strip().lower()
            n = conn.execute("UPDATE users SET password_hash=?, is_admin=1, active=1 WHERE username=?",
                             (hash_password(ADMIN_PASSWORD), uname)).rowcount
            if not n:
                conn.execute("INSERT INTO users(username, display_name, password_hash, is_admin) VALUES (?,?,?,1)",
                             (uname, ADMIN_NAME or ADMIN_USER, hash_password(ADMIN_PASSWORD)))
            print(f"[rmlab] heslo admina {uname} nastaveno z LF_ADMIN_PASSWORD – smažte LF_ADMIN_RESET", flush=True)
        print("[rmlab] uživatelé: " + ", ".join(r[0] for r in conn.execute("SELECT username FROM users")), flush=True)
        if ADMIN_PASSWORD:
            print(f"[rmlab] heslo z LF_ADMIN_PASSWORD má {len(ADMIN_PASSWORD)} znaků", flush=True)
        # import se zkouší při každém startu, dokud jednou celý neproběhne (i po přerušení nebo plném disku)
        need_data = AUTO_IMPORT and get_meta(conn, "auto_import_done") != "1"
        need_mini = (not need_data and get_meta(conn, "firm_mini_ok") != "1"
                     and conn.execute("SELECT 1 FROM firm_geo LIMIT 1").fetchone() is not None)
    import threading
    if need_data:
        threading.Thread(target=_auto_import, daemon=True).start()
    elif need_mini:
        threading.Thread(target=_build_mini, daemon=True).start()


def _build_mini():
    from .db import rebuild_firm_mini
    print("[rmlab] stavím rychlý index pro hledání…", flush=True)
    with connect() as conn:
        n = rebuild_firm_mini(conn)
    print(f"[rmlab] rychlý index hotov ({n} firem)", flush=True)


IMPORT_STATE = {"running": False, "step": "", "error": ""}


def _auto_import():
    """Stáhne a naimportuje RES (firmy) a RÚIAN (souřadnice adres). Trvá desítky minut."""
    from .config import DB_PATH
    from . import importers
    raw = DB_PATH.parent / "raw"
    IMPORT_STATE.update(running=True, error="")
    try:
        IMPORT_STATE["step"] = "Stahuji registr ekonomických subjektů (RES)…"
        res = importers.download_res(raw)
        IMPORT_STATE["step"] = "Stahuji adresní místa (RÚIAN)…"
        ruian = importers.download_ruian(raw)
        IMPORT_STATE["step"] = "Importuji firmy…"
        importers.import_res(res)
        IMPORT_STATE["step"] = "Importuji souřadnice adres…"
        importers.import_ruian(ruian)
        with connect() as conn:
            set_meta(conn, "auto_import_done", "1")
        # stažené soubory už nejsou potřeba – uvolní místo na disku serveru
        for f in (res, ruian):
            try:
                Path(f).unlink()
            except OSError:
                pass
        IMPORT_STATE["step"] = "Hotovo"
    except Exception as ex:  # noqa: BLE001 – stav se ukáže v aplikaci
        IMPORT_STATE["error"] = str(ex)
        print(f"[rmlab] import selhal: {ex}", flush=True)
    finally:
        IMPORT_STATE["running"] = False


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


# omezení pokusů o přihlášení (v paměti, na jednu instanci stačí)
_FAILS: dict = {}


def _client_ip(request: Request) -> str:
    # poslední položku přidává proxy hostingu – první si může klient podvrhnout
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[-1].strip() if fwd else (request.client.host if request.client else "?"))


def _too_many(ip: str) -> bool:
    now = dt.datetime.now().timestamp()
    recent = [t for t in _FAILS.get(ip, []) if now - t < 15 * 60]
    _FAILS[ip] = recent
    return len(recent) >= LOGIN_MAX_FAILS


def _now():
    return dt.datetime.now()


def _iso(d):
    return d.isoformat(timespec="seconds")


def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def current_user(request: Request, conn=Depends(db)):
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(401, "Nepřihlášen")
    row = conn.execute("SELECT id, username, display_name, is_admin FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    if not row:
        request.session.clear()
        raise HTTPException(401, "Nepřihlášen")
    return dict(row)


# ---------------------------------------------------------------- přihlášení

class LoginIn(BaseModel):
    username: str
    password: str


@app.get("/", include_in_schema=False)
def public_web():
    """Veřejný web RM Lab (na doméně CRM lze přesměrovat proměnnou LF_ROOT_REDIRECT)."""
    if ROOT_REDIRECT:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(ROOT_REDIRECT)
    return FileResponse(STATIC / "web" / "index.html")


@app.get("/nase-crm", include_in_schema=False)
def crm_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/nase-crm/")


@app.get("/nase-crm/", include_in_schema=False)
def index():
    """Neveřejná část – vyhledávání firem, CRM, editor webů."""
    return FileResponse(STATIC / "index.html", headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return Response("User-agent: *\nDisallow: /nase-crm/\nDisallow: /api/\nDisallow: /p/\n", media_type="text/plain")


@app.post("/api/login")
def login(body: LoginIn, request: Request, conn=Depends(db)):
    ip = _client_ip(request)
    if _too_many(ip):
        raise HTTPException(429, "Příliš mnoho pokusů. Zkuste to znovu za 15 minut.")
    row = conn.execute("SELECT * FROM users WHERE username=?", (body.username.strip().lower(),)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        _FAILS.setdefault(ip, []).append(dt.datetime.now().timestamp())
        raise HTTPException(401, "Špatné jméno nebo heslo")
    _FAILS.pop(ip, None)
    if not row["active"]:
        raise HTTPException(403, "Účet je deaktivovaný")
    request.session["uid"] = row["id"]
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "is_admin": row["is_admin"]}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/meta")
def meta(user=Depends(current_user), conn=Depends(db)):
    users = [dict(r) for r in conn.execute("SELECT id, display_name FROM users WHERE active=1 ORDER BY display_name")]
    return {
        "import": dict(IMPORT_STATE),
        "inquiries_new": conn.execute("SELECT COUNT(*) FROM inquiries WHERE status='new'").fetchone()[0],
        "demo": enrich.is_demo(conn),
        "google": places.enabled() or enrich.is_demo(conn),
        "firms": conn.execute("SELECT COUNT(*) FROM firm_geo").fetchone()[0],
        "res_imported_at": get_meta(conn, "res_imported_at"),
        "nace": [{"code": k, "label": v[0]} for k, v in NACE_DIVISIONS.items()],
        "preset_local": PRESET_LOCAL_SERVICES,
        "preset_venues": ["9602", "561", "563"],
        "forms": [{"key": k, "label": v["label"]} for k, v in FORM_GROUPS.items()],
        "statuses": STATUSES, "outcomes": {k: v[0] for k, v in OUTCOMES.items()}, "channels": CHANNELS,
        "enrich_max": ENRICH_MAX, "claim_days": CLAIM_DAYS, "users": users,
    }


@app.get("/api/obce")
def obce(q: str, user=Depends(current_user), conn=Depends(db)):
    qa = strip_accents(q.strip()).lower()
    if len(qa) < 2:
        return []
    rows = conn.execute("""SELECT name, lat, lon, n FROM obce WHERE name_ascii LIKE ?
                           ORDER BY (name_ascii = ?) DESC, n DESC LIMIT 8""", (qa + "%", qa)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- vyhledávání

class SearchIn(BaseModel):
    lat: float
    lon: float
    radius_km: float = Field(10, gt=0, le=60)
    forms: List[str] = ["fo", "spol", "druzstvo"]
    nace: List[str] = []
    min_staff: int = 0                    # 0 = bez omezení, 1 = aspoň „bez zaměstnanců“, 2 = 1+ zam.
    max_staff: int = 4                    # 5 = včetně 50+
    hide_worked: bool = True              # skrýt oslovené a rezervované někým jiným
    min_p_noweb: float = 0.0
    min_vitality: float = 0.0
    only_enriched: bool = False
    limit: int = Field(500, le=5000)


def _lead_view(row, user_id, now_iso):
    status = row["l_status"] or "new"
    claimed = bool(row["l_owner"]) and (row["l_until"] or "") > now_iso and status not in FINAL
    return {
        "status": status, "status_label": STATUSES.get(status, status),
        "owner_id": row["l_owner"] if claimed or status != "new" else None,
        "owner": row["l_owner_name"] if claimed or status != "new" else None,
        "claimed": claimed, "mine": claimed and row["l_owner"] == user_id,
        "next_action": row["l_next"],
    }


FULL_COLS = """f.*, s.p_noweb, s.vitality, s.priority, s.enriched,
               l.status l_status, l.owner_id l_owner, l.claimed_until l_until, l.next_action l_next,
               u.display_name l_owner_name"""
FULL_JOINS = """LEFT JOIN scores s ON s.ico = f.ico
        LEFT JOIN leads l ON l.ico = f.ico
        LEFT JOIN users u ON u.id = l.owner_id"""


def _search_rows(conn, body, forms, nace_set, box):
    """Kandidáti v okruhu. Nejdřív se filtruje nad malou tabulkou firm_mini (rychlé),
    teprve pro vyfiltrované firmy se čtou celé záznamy z velké tabulky firms."""
    min_lat, max_lat, min_lon, max_lon = box
    ph = ",".join("?" * len(forms))
    if get_meta(conn, "firm_mini_ok") != "1":   # starší databáze, než se index dopočítá
        return conn.execute(f"""SELECT {FULL_COLS} FROM firm_geo g JOIN firms f ON f.rid = g.id {FULL_JOINS}
            WHERE g.min_lat >= ? AND g.max_lat <= ? AND g.min_lon >= ? AND g.max_lon <= ?
              AND f.forma IN ({ph})""", [min_lat, max_lat, min_lon, max_lon, *forms]).fetchall()
    cand = conn.execute(f"""SELECT m.rid, m.lat, m.lon, m.nace, m.katpo FROM firm_geo g JOIN firm_mini m ON m.rid = g.id
        WHERE g.min_lat >= ? AND g.max_lat <= ? AND g.min_lon >= ? AND g.max_lon <= ?
          AND m.forma IN ({ph})""", [min_lat, max_lat, min_lon, max_lon, *forms]).fetchall()
    rids = []
    for rid, lat, lon, nace, katpo in cand:
        if haversine_km(body.lat, body.lon, lat, lon) > body.radius_km:
            continue
        if nace_set and not any((nace or "").startswith(c) for c in nace_set):
            continue
        rank = katpo_rank(katpo)
        if (body.min_staff and rank < body.min_staff) or rank > body.max_staff:
            continue
        rids.append(rid)
    rows = []
    for i in range(0, len(rids), 900):
        chunk = rids[i:i + 900]
        rows += conn.execute(f"SELECT {FULL_COLS} FROM firms f {FULL_JOINS} WHERE f.rid IN ({','.join('?' * len(chunk))})",
                             chunk).fetchall()
    return rows


@app.post("/api/search")
def search(body: SearchIn, user=Depends(current_user), conn=Depends(db)):
    min_lat, max_lat, min_lon, max_lon = bbox(body.lat, body.lon, body.radius_km)
    forms = [c for k in body.forms for c in FORM_GROUPS.get(k, {}).get("codes", [])]
    if not forms:
        return {"total": 0, "results": []}
    nace_set = set(body.nace)
    rows = _search_rows(conn, body, forms, nace_set, (min_lat, max_lat, min_lon, max_lon))
    now_iso = _iso(_now())
    out, to_score = [], []
    for r in rows:
        d = haversine_km(body.lat, body.lon, r["lat"], r["lon"])
        if d > body.radius_km:
            continue
        if nace_set and not any((r["nace"] or "").startswith(c) for c in nace_set):
            continue
        rank = katpo_rank(r["katpo"])
        if body.min_staff and rank < body.min_staff:
            continue
        if rank > body.max_staff:
            continue
        lead = _lead_view(r, user["id"], now_iso)
        if lead["status"] == "do_not_contact":
            continue
        if body.hide_worked and ((lead["status"] not in ("new", "claimed")) or (lead["claimed"] and not lead["mine"])):
            continue
        if body.only_enriched and not r["enriched"]:
            continue
        item = {
            "ico": r["ico"], "nazev": r["nazev"], "adresa": r["adresa"], "obec": r["obec"],
            "lat": r["lat"], "lon": r["lon"], "dist_km": round(d, 2),
            "forma": r["forma"], "nace": nace_division(r["nace"]), "nace_label": nace_label(r["nace"]),
            "staff": katpo_label(r["katpo"]), "addr_count": r["addr_count"],
            "p_noweb": r["p_noweb"], "vitality": r["vitality"], "priority": r["priority"],
            "enriched": bool(r["enriched"]), "lead": lead,
        }
        if item["p_noweb"] is None:
            to_score.append((dict(r), item))
        out.append(item)
    # Základní skóre pro firmy, které ještě nikdo nehodnotil (jen z dat RES)
    for firm, item in to_score:
        s = score(firm)
        item.update(p_noweb=s["p_noweb"], vitality=s["vitality"], priority=s["priority"])
    if to_score:
        conn.executemany(
            "INSERT OR IGNORE INTO scores(ico, p_noweb, vitality, priority, enriched, computed_at) VALUES (?,?,?,?,0,?)",
            [(i["ico"], i["p_noweb"], i["vitality"], i["priority"], now_iso) for _, i in to_score])
    out = [i for i in out if i["p_noweb"] >= body.min_p_noweb and i["vitality"] >= body.min_vitality]
    out.sort(key=lambda i: (-i["priority"], i["dist_km"]))
    return {"total": len(out), "results": out[: body.limit]}


# ---------------------------------------------------------------- obohacení

class EnrichIn(BaseModel):
    icos: List[str]


@app.post("/api/enrich")
async def enrich_start(body: EnrichIn, user=Depends(current_user)):
    icos = list(dict.fromkeys(i for i in body.icos if i.isdigit()))[:ENRICH_MAX]
    if not icos:
        raise HTTPException(400, "Žádné firmy k obohacení")
    return enrich.start_job(icos, user["display_name"])


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, user=Depends(current_user)):
    job = enrich.JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Úloha neexistuje")
    return {**job, "errors": job["errors"][-5:], "error_count": len(job["errors"])}


# ---------------------------------------------------------------- detail firmy

def _links(f):
    q = f"{f['nazev']} {f['obec'] or ''}"
    from urllib.parse import quote_plus
    return {
        "ares": f"https://ares.gov.cz/ekonomicke-subjekty?ico={f['ico']}",
        "justice": f"https://or.justice.cz/ias/ui/rejstrik-$firma?ico={f['ico']}",
        "google": f"https://www.google.com/search?q={quote_plus(q)}",
        "mapy": f"https://mapy.com/fnc/v1/showmap?mapset=basic&center={f['lon']},{f['lat']}&zoom=18&marker=true",
        "firmy": f"https://www.firmy.cz/?q={quote_plus(q)}",
    }


def _lead_row(conn, ico):
    return conn.execute("""SELECT l.*, u.display_name owner_name FROM leads l
                           LEFT JOIN users u ON u.id = l.owner_id WHERE l.ico=?""", (ico,)).fetchone()


def _lead_payload(conn, ico, user_id):
    l = _lead_row(conn, ico)
    now_iso = _iso(_now())
    acts = [dict(a) for a in conn.execute("""SELECT a.*, u.display_name user FROM activities a
                                             JOIN users u ON u.id=a.user_id WHERE a.ico=? ORDER BY a.ts DESC""", (ico,))]
    for a in acts:
        a["outcome_label"] = OUTCOMES.get(a["outcome"], (a["outcome"],))[0]
        a["channel_label"] = CHANNELS.get(a["channel"], a["channel"])
    if not l:
        return {"status": "new", "status_label": STATUSES["new"], "claimed": False, "mine": False,
                "owner": None, "claimed_until": None, "next_action": None, "contact_note": None, "activities": acts}
    claimed = bool(l["owner_id"]) and (l["claimed_until"] or "") > now_iso and l["status"] not in FINAL
    return {"status": l["status"], "status_label": STATUSES.get(l["status"], l["status"]), "claimed": claimed,
            "mine": claimed and l["owner_id"] == user_id, "owner": l["owner_name"], "owner_id": l["owner_id"],
            "claimed_until": l["claimed_until"], "next_action": l["next_action"],
            "contact_note": l["contact_note"], "activities": acts}


@app.get("/api/firm/{ico}")
async def firm_detail(ico: str, user=Depends(current_user), conn=Depends(db)):
    f = conn.execute("SELECT * FROM firms WHERE ico=?", (ico,)).fetchone()
    if not f:
        raise HTTPException(404, "Firma nenalezena")
    f = dict(f)
    ares_d, web_d, google_d, glink = enrich.load_signals(conn, ico)
    google_error = None
    if glink and glink["place_id"] and not google_d and places.enabled():
        try:
            client = places.new_client()
            google_d = await places.details(client, glink["place_id"])
            await client.aclose()
        except Exception as e:  # noqa: BLE001
            google_error = str(e)
    s = score(f, ares_d, web_d, google_d, google_checked=bool(glink))
    enrich.rescore(conn, f)
    contacts = []
    if google_d and google_d.get("phone"):
        contacts.append({"type": "phone", "value": google_d["phone"], "source": "Google (živě)"})
    if ares_d:
        if ares_d.get("phone"):
            contacts.append({"type": "phone", "value": ares_d["phone"], "source": "ARES / registr osob"})
        if ares_d.get("email"):
            contacts.append({"type": "email", "value": ares_d["email"], "source": "ARES / registr osob"})
        if ares_d.get("datova_schranka"):
            contacts.append({"type": "ds", "value": ares_d["datova_schranka"], "source": "Datová schránka"})
    return {
        "firm": {**f, "forma_label": FORM_LABELS.get(f["forma"], f["forma"]), "nace_label": nace_label(f["nace"]),
                 "staff": katpo_label(f["katpo"])},
        "score": s, "ares": ares_d, "web": web_d, "google": google_d,
        "google_status": "not_found" if glink and not glink["place_id"] else ("matched" if glink else "unchecked"),
        "google_error": google_error, "enriched": bool(glink or ares_d or web_d),
        "contacts": contacts, "links": _links(f), "lead": _lead_payload(conn, ico, user["id"]),
    }


# ---------------------------------------------------------------- CRM

def _ensure_lead(conn, ico):
    if not conn.execute("SELECT 1 FROM firms WHERE ico=?", (ico,)).fetchone():
        raise HTTPException(404, "Firma nenalezena")
    conn.execute("INSERT OR IGNORE INTO leads(ico, status, updated_at) VALUES (?, 'new', ?)", (ico, _iso(_now())))
    return _lead_row(conn, ico)


def _check_not_taken(lead, user):
    now_iso = _iso(_now())
    if lead["owner_id"] and lead["owner_id"] != user["id"] and (lead["claimed_until"] or "") > now_iso \
            and lead["status"] not in FINAL:
        raise HTTPException(409, f"Firmu má rezervovanou {lead['owner_name']} do {lead['claimed_until'][:10]}")


@app.post("/api/leads/{ico}/claim")
def claim(ico: str, user=Depends(current_user), conn=Depends(db)):
    lead = _ensure_lead(conn, ico)
    _check_not_taken(lead, user)
    if lead["status"] == "do_not_contact":
        raise HTTPException(409, "Firma si nepřeje být kontaktována")
    until = _iso(_now() + dt.timedelta(days=CLAIM_DAYS))
    status = "claimed" if lead["status"] in ("new", "claimed") else lead["status"]
    conn.execute("UPDATE leads SET owner_id=?, claimed_until=?, status=?, updated_at=? WHERE ico=?",
                 (user["id"], until, status, _iso(_now()), ico))
    return _lead_payload(conn, ico, user["id"])


@app.post("/api/leads/{ico}/release")
def release(ico: str, user=Depends(current_user), conn=Depends(db)):
    lead = _ensure_lead(conn, ico)
    _check_not_taken(lead, user)
    status = "new" if lead["status"] == "claimed" else lead["status"]
    conn.execute("UPDATE leads SET owner_id=NULL, claimed_until=NULL, status=?, updated_at=? WHERE ico=?",
                 (status, _iso(_now()), ico))
    return _lead_payload(conn, ico, user["id"])


class ActivityIn(BaseModel):
    channel: str = "phone"
    outcome: str
    note: Optional[str] = None
    next_action: Optional[str] = None     # YYYY-MM-DD


@app.post("/api/leads/{ico}/activity")
def add_activity(ico: str, body: ActivityIn, user=Depends(current_user), conn=Depends(db)):
    if body.outcome not in OUTCOMES or body.channel not in CHANNELS:
        raise HTTPException(400, "Neplatný výsledek nebo kanál")
    lead = _ensure_lead(conn, ico)
    _check_not_taken(lead, user)
    now = _now()
    conn.execute("INSERT INTO activities(ico, user_id, ts, channel, outcome, note) VALUES (?,?,?,?,?,?)",
                 (ico, user["id"], _iso(now), body.channel, body.outcome, (body.note or "").strip() or None))
    new_status = OUTCOMES[body.outcome][1] or lead["status"]
    if new_status in FINAL:
        owner, until = user["id"], None
    else:
        owner, until = user["id"], _iso(now + dt.timedelta(days=CLAIM_DAYS))
        if body.next_action:  # rezervace aspoň do dalšího kroku
            until = max(until, body.next_action + "T23:59:59")
    conn.execute("UPDATE leads SET status=?, owner_id=?, claimed_until=?, next_action=?, updated_at=? WHERE ico=?",
                 (new_status, owner, until, body.next_action if new_status not in FINAL else None, _iso(now), ico))
    return _lead_payload(conn, ico, user["id"])


class NoteIn(BaseModel):
    contact_note: str


@app.post("/api/leads/{ico}/contact-note")
def contact_note(ico: str, body: NoteIn, user=Depends(current_user), conn=Depends(db)):
    lead = _ensure_lead(conn, ico)
    _check_not_taken(lead, user)
    conn.execute("UPDATE leads SET contact_note=?, updated_at=? WHERE ico=?",
                 (body.contact_note.strip() or None, _iso(_now()), ico))
    return _lead_payload(conn, ico, user["id"])


@app.get("/api/my")
def my_leads(scope: str = "mine", user=Depends(current_user), conn=Depends(db)):
    """scope: mine = moje rozpracované, all = všechny oslovené (přehled týmu)."""
    where = "l.owner_id = ? AND l.status NOT IN ('won','lost','do_not_contact')" if scope == "mine" else "l.status != 'new' OR l.owner_id IS NOT NULL"
    params = [user["id"]] if scope == "mine" else []
    rows = conn.execute(f"""
        SELECT l.*, f.nazev, f.obec, f.adresa, u.display_name owner_name,
               (SELECT MAX(ts) FROM activities a WHERE a.ico = l.ico) last_ts,
               (SELECT COUNT(*) FROM activities a WHERE a.ico = l.ico) n_act
        FROM leads l JOIN firms f ON f.ico = l.ico LEFT JOIN users u ON u.id = l.owner_id
        WHERE {where}
        ORDER BY (l.next_action IS NULL), l.next_action, l.updated_at DESC LIMIT 1000""", params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["status_label"] = STATUSES.get(d["status"], d["status"])
        out.append(d)
    return out


@app.get("/api/stats")
def stats(user=Depends(current_user), conn=Depends(db)):
    rows = conn.execute("""SELECT u.display_name, l.status, COUNT(*) n FROM leads l
                           JOIN users u ON u.id = l.owner_id GROUP BY u.display_name, l.status""").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- správa týmu (jen admin)

def admin_user(user=Depends(current_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "Jen pro administrátory")
    return user


USERNAME_RE = __import__("re").compile(r"^[a-z0-9._-]{2,32}$")


def _users(conn):
    rows = conn.execute("""
        SELECT u.id, u.username, u.display_name, u.is_admin, u.active,
               (SELECT COUNT(*) FROM leads l WHERE l.owner_id = u.id AND l.claimed_until IS NOT NULL
                  AND l.status NOT IN ('won','lost','do_not_contact')) open_leads,
               (SELECT COUNT(*) FROM activities a WHERE a.user_id = u.id) n_act,
               (SELECT MAX(ts) FROM activities a WHERE a.user_id = u.id) last_ts
        FROM users u ORDER BY u.active DESC, u.display_name""").fetchall()
    return [dict(r) for r in rows]


def _active_admins(conn):
    return conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=1 AND active=1").fetchone()[0]


@app.get("/api/admin/users")
def admin_list(user=Depends(admin_user), conn=Depends(db)):
    return _users(conn)


class UserIn(BaseModel):
    username: str
    display_name: str
    password: str
    is_admin: bool = False


@app.post("/api/admin/users")
def admin_create(body: UserIn, user=Depends(admin_user), conn=Depends(db)):
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Uživatelské jméno: 2–32 znaků, jen malá písmena bez diakritiky, číslice, tečka, pomlčka")
    if len(body.password) < 8:
        raise HTTPException(400, "Heslo musí mít aspoň 8 znaků")
    if not body.display_name.strip():
        raise HTTPException(400, "Vyplňte jméno")
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        raise HTTPException(409, f"Uživatel {username} už existuje")
    try:
        conn.execute("INSERT INTO users(username, display_name, password_hash, is_admin, active) VALUES (?,?,?,?,1)",
                     (username, body.display_name.strip(), hash_password(body.password), int(body.is_admin)))
    except __import__("sqlite3").IntegrityError:
        raise HTTPException(409, f"Uživatel {username} už existuje")
    return _users(conn)


class UserPatch(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    active: Optional[bool] = None


@app.patch("/api/admin/users/{uid}")
def admin_update(uid: int, body: UserPatch, user=Depends(admin_user), conn=Depends(db)):
    target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        raise HTTPException(404, "Uživatel neexistuje")
    if uid == user["id"] and (body.is_admin is False or body.active is False):
        raise HTTPException(400, "Sám sobě nemůžete odebrat admina ani deaktivovat účet")
    losing_admin = target["is_admin"] and target["active"] and (body.is_admin is False or body.active is False)
    if losing_admin and _active_admins(conn) <= 1:
        raise HTTPException(400, "Musí zůstat aspoň jeden aktivní admin")
    if body.display_name is not None:
        if not body.display_name.strip():
            raise HTTPException(400, "Vyplňte jméno")
        conn.execute("UPDATE users SET display_name=? WHERE id=?", (body.display_name.strip(), uid))
    if body.password is not None:
        if len(body.password) < 8:
            raise HTTPException(400, "Heslo musí mít aspoň 8 znaků")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.password), uid))
    if body.is_admin is not None:
        conn.execute("UPDATE users SET is_admin=? WHERE id=?", (int(body.is_admin), uid))
    if body.active is not None:
        conn.execute("UPDATE users SET active=? WHERE id=?", (int(body.active), uid))
        if not body.active:
            # rozpracované firmy deaktivovaného člověka se uvolní pro ostatní
            conn.execute("""UPDATE leads SET claimed_until=NULL,
                              owner_id=CASE WHEN status='claimed' THEN NULL ELSE owner_id END,
                              status=CASE WHEN status='claimed' THEN 'new' ELSE status END
                            WHERE owner_id=? AND status NOT IN ('won','lost','do_not_contact')""", (uid,))
    return _users(conn)


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/me/password")
def change_own_password(body: PasswordIn, user=Depends(current_user), conn=Depends(db)):
    row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(400, "Současné heslo nesouhlasí")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Nové heslo musí mít aspoň 8 znaků")
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user["id"]))
    return {"ok": True}


# ---------------------------------------------------------------- checklisty

def _cl_key(kind):
    return f"checklist_{kind}"


def _get_cl(conn, kind, user):
    text = get_meta(conn, _cl_key(kind)) or checklist_mod.DEFAULTS[kind]
    return {"kind": kind, "title": checklist_mod.KINDS[kind], "sections": checklist_mod.parse(text),
            "text": text if user["is_admin"] else None,
            "updated_at": get_meta(conn, _cl_key(kind) + "_at"), "updated_by": get_meta(conn, _cl_key(kind) + "_by"),
            "is_default": get_meta(conn, _cl_key(kind)) is None}


def _check_kind(kind):
    if kind not in checklist_mod.KINDS:
        raise HTTPException(404, "Neznámý checklist")


@app.get("/api/checklist/{kind}")
def get_checklist(kind: str, user=Depends(current_user), conn=Depends(db)):
    _check_kind(kind)
    return _get_cl(conn, kind, user)


class ChecklistIn(BaseModel):
    text: Optional[str] = None      # None = obnovit výchozí


@app.put("/api/checklist/{kind}")
def put_checklist(kind: str, body: ChecklistIn, user=Depends(admin_user), conn=Depends(db)):
    _check_kind(kind)
    if body.text is None:
        conn.execute("DELETE FROM meta WHERE key=?", (_cl_key(kind),))
    else:
        if len(body.text) > 50_000:
            raise HTTPException(400, "Checklist je příliš dlouhý")
        if not checklist_mod.parse(body.text):
            raise HTTPException(400, "Checklist je prázdný – sekce začínají „## “, položky „- “")
        set_meta(conn, _cl_key(kind), body.text)
    set_meta(conn, _cl_key(kind) + "_at", _iso(_now()))
    set_meta(conn, _cl_key(kind) + "_by", user["display_name"])
    return _get_cl(conn, kind, user)


# ---------------------------------------------------------------- produkty a ceník

def _products(conn, include_inactive=False):
    where = "" if include_inactive else "WHERE active=1"
    return [dict(r) for r in conn.execute(f"SELECT * FROM products {where} ORDER BY active DESC, sort, base_price, id")]


@app.get("/api/products")
def list_products(all: bool = False, user=Depends(current_user), conn=Depends(db)):
    return _products(conn, include_inactive=all and bool(user["is_admin"]))


class ProductIn(BaseModel):
    name: str
    description: Optional[str] = ""
    includes: Optional[str] = ""
    base_price: int = Field(0, ge=0, le=10_000_000)
    monthly_fee: int = Field(0, ge=0, le=1_000_000)
    active: bool = True
    sort: int = 0


def _clean_product(body: ProductIn):
    if not body.name.strip():
        raise HTTPException(400, "Vyplňte název produktu")
    return (body.name.strip(), (body.description or "").strip(), (body.includes or "").strip(),
            body.base_price, body.monthly_fee, int(body.active), body.sort, _iso(_now()))


@app.post("/api/products")
def create_product(body: ProductIn, user=Depends(admin_user), conn=Depends(db)):
    conn.execute("""INSERT INTO products(name, description, includes, base_price, monthly_fee, active, sort, updated_at)
                    VALUES (?,?,?,?,?,?,?,?)""", _clean_product(body))
    return _products(conn, include_inactive=True)


@app.put("/api/products/{pid}")
def update_product(pid: int, body: ProductIn, user=Depends(admin_user), conn=Depends(db)):
    n = conn.execute("""UPDATE products SET name=?, description=?, includes=?, base_price=?, monthly_fee=?,
                        active=?, sort=?, updated_at=? WHERE id=?""", (*_clean_product(body), pid)).rowcount
    if not n:
        raise HTTPException(404, "Produkt neexistuje")
    return _products(conn, include_inactive=True)


# ---------------------------------------------------------------- weby pro klienty

SITE_STATUS = {"draft": "Rozpracováno", "review": "Ke schválení", "approved": "Schváleno", "published": "Spuštěno"}


def _site_row(conn, sid):
    r = conn.execute("SELECT * FROM sites WHERE id=?", (sid,)).fetchone()
    if not r:
        raise HTTPException(404, "Web neexistuje")
    return r


def _site_payload(conn, r):
    raw = json.loads(r["data"])
    d = _merge(_merge(sites.empty_data(raw.get("type") if raw.get("type") in sites.TYPES else "kadernictvi"), raw), {})
    d["type"] = raw.get("type", d["type"])
    chk = sites.checks(d)
    names = {u["id"]: u["display_name"] for u in conn.execute("SELECT id, display_name FROM users")}
    return {"id": r["id"], "ico": r["ico"], "status": r["status"], "status_label": SITE_STATUS[r["status"]],
            "token": r["token"], "data": d, "checks": chk, "summary": sites.summary(chk),
            "created_by": names.get(r["created_by"]), "updated_by": names.get(r["updated_by"]),
            "updated_at": r["updated_at"], "types": {k: v["label"] for k, v in sites.TYPES.items()},
            "templates": sites.TEMPLATES,
            "ai": ai.enabled()}


@app.get("/api/sites")
def list_sites(user=Depends(current_user), conn=Depends(db)):
    out = []
    for r in conn.execute("""SELECT s.*, u.display_name author FROM sites s LEFT JOIN users u ON u.id = s.updated_by
                             ORDER BY s.updated_at DESC"""):
        d = json.loads(r["data"])
        sm = sites.summary(sites.checks(d))
        tpl = (d.get("theme") or {}).get("template") or "1"
        out.append({"id": r["id"], "ico": r["ico"], "name": d.get("name"),
                    "type": sites.TYPES[d["type"]]["label"] + f" · šablona {tpl}",
                    "status": r["status"], "status_label": SITE_STATUS[r["status"]], "summary": sm,
                    "updated_at": r["updated_at"], "author": r["author"], "token": r["token"]})
    return out


class SiteNew(BaseModel):
    ico: str


@app.post("/api/sites")
def create_site(body: SiteNew, user=Depends(current_user), conn=Depends(db)):
    existing = conn.execute("SELECT * FROM sites WHERE ico=? ORDER BY id DESC LIMIT 1", (body.ico,)).fetchone()
    if existing:
        return _site_payload(conn, existing)
    f = conn.execute("SELECT * FROM firms WHERE ico=?", (body.ico,)).fetchone()
    if not f:
        raise HTTPException(404, "Firma nenalezena")
    ares_d, _, google_d, _ = enrich.load_signals(conn, body.ico)
    d = sites.prefill(dict(f), ares_d, google_d)
    now = _iso(_now())
    cur = conn.execute("""INSERT INTO sites(ico, status, token, data, created_by, created_at, updated_by, updated_at)
                          VALUES (?, 'draft', ?, ?, ?, ?, ?, ?)""",
                       (body.ico, sites.new_token(), json.dumps(d, ensure_ascii=False), user["id"], now, user["id"], now))
    return _site_payload(conn, _site_row(conn, cur.lastrowid))


@app.get("/api/sites/{sid}")
def get_site(sid: int, user=Depends(current_user), conn=Depends(db)):
    return _site_payload(conn, _site_row(conn, sid))


class SiteData(BaseModel):
    data: dict


def _merge(base, new):
    """Převezme jen známé klíče (ochrana proti nesmyslům z klienta)."""
    out = dict(base)
    for k, v in new.items():
        if k not in base:
            continue
        if isinstance(base[k], dict) and isinstance(v, dict) and k not in ("images",):
            out[k] = _merge(base[k], v)
        else:
            out[k] = v
    return out


@app.put("/api/sites/{sid}")
def save_site(sid: int, body: SiteData, user=Depends(current_user), conn=Depends(db)):
    r = _site_row(conn, sid)
    old = json.loads(r["data"])
    kind = body.data.get("type") if body.data.get("type") in sites.TYPES else old["type"]
    base = _merge(sites.empty_data(kind), old)
    d = _merge(base, body.data)
    d["type"] = kind
    raw = json.dumps(d, ensure_ascii=False)
    if len(raw) > 400_000:
        raise HTTPException(400, "Příliš mnoho dat")
    # když prodejce upraví web čekající na schválení / schválený, vrací se do rozpracovaných
    status = r["status"]
    if status in ("review", "approved") and not user["is_admin"]:
        status = "draft"
    conn.execute("UPDATE sites SET data=?, status=?, updated_by=?, updated_at=? WHERE id=?",
                 (raw, status, user["id"], _iso(_now()), sid))
    return _site_payload(conn, _site_row(conn, sid))


class ImageIn(BaseModel):
    data_url: str
    w: Optional[int] = None
    h: Optional[int] = None
    bright: Optional[float] = None
    sharp: Optional[float] = None


@app.post("/api/sites/{sid}/images")
def upload_image(sid: int, body: ImageIn, user=Depends(current_user), conn=Depends(db)):
    r = _site_row(conn, sid)
    try:
        name = sites.save_image(sid, body.data_url)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    d = json.loads(r["data"])
    d.setdefault("images", {})[name] = {"w": body.w, "h": body.h, "bright": body.bright, "sharp": body.sharp}
    conn.execute("UPDATE sites SET data=?, updated_at=? WHERE id=?", (json.dumps(d, ensure_ascii=False), _iso(_now()), sid))
    return {"file": name, "meta": d["images"][name]}


@app.post("/api/sites/{sid}/video")
async def upload_video(sid: int, request: Request, user=Depends(current_user), conn=Depends(db)):
    r = _site_row(conn, sid)
    raw = await request.body()
    try:
        name = sites.save_video(sid, raw, (request.headers.get("content-type") or "").split(";")[0].strip())
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    d = json.loads(r["data"])
    d.setdefault("images", {})[name] = {"size": len(raw)}
    d.setdefault("hero", {})["video"] = name
    conn.execute("UPDATE sites SET data=?, updated_at=? WHERE id=?", (json.dumps(d, ensure_ascii=False), _iso(_now()), sid))
    return {"file": name, "meta": d["images"][name]}


@app.post("/api/sites/{sid}/ai")
async def site_ai(sid: int, user=Depends(current_user), conn=Depends(db)):
    d = json.loads(_site_row(conn, sid)["data"])
    try:
        return await ai.suggest(d)
    except Exception as ex:  # noqa: BLE001
        raise HTTPException(502, f"Návrh textů se nepovedl: {ex}")


class StatusIn(BaseModel):
    status: str


@app.post("/api/sites/{sid}/status")
def site_status(sid: int, body: StatusIn, user=Depends(current_user), conn=Depends(db)):
    r = _site_row(conn, sid)
    new = body.status
    if new not in SITE_STATUS:
        raise HTTPException(400, "Neplatný stav")
    if new in ("approved", "published") and not user["is_admin"]:
        raise HTTPException(403, "Schvaluje a spouští jen admin")
    if new in ("review", "approved", "published") and not sites.summary(sites.checks(json.loads(r["data"])))["ready"]:
        raise HTTPException(400, "Web ještě nesplňuje všechna povinná pravidla")
    conn.execute("UPDATE sites SET status=?, updated_by=?, updated_at=? WHERE id=?", (new, user["id"], _iso(_now()), sid))
    return _site_payload(conn, _site_row(conn, sid))


@app.get("/api/sites/{sid}/export")
def site_export(sid: int, user=Depends(admin_user), conn=Depends(db)):
    r = _site_row(conn, sid)
    d = json.loads(r["data"])
    slug = re.sub(r"[^a-z0-9]+", "-", strip_accents(d.get("name") or "web").lower()).strip("-") or "web"
    return Response(sites.export_zip(sid, d), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'})


# Veřejný náhled (bez přihlášení, jen s tajným odkazem) – na ukázku klientovi
def _site_by_token(conn, token):
    r = conn.execute("SELECT * FROM sites WHERE token=?", (token,)).fetchone()
    if not r:
        raise HTTPException(404, "Náhled neexistuje")
    return r


@app.get("/p/{token}", include_in_schema=False)
def preview_redirect(token: str):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/p/{token}/")


@app.get("/p/{token}/", response_class=HTMLResponse, include_in_schema=False)
def preview(token: str, conn=Depends(db)):
    r = _site_by_token(conn, token)
    raw = json.loads(r["data"])
    d = _merge(sites.empty_data(raw.get("type") if raw.get("type") in sites.TYPES else "kadernictvi"), raw)
    d["type"] = raw.get("type", d["type"])
    banner = "" if r["status"] == "published" else \
        '<div class="preview-bar">Ukázka webu od RM Lab – návrh, který ještě doladíme</div>'
    return HTMLResponse(sites.render(d, banner), headers={"X-Robots-Tag": "noindex"})


@app.get("/p/{token}/img/{name}", include_in_schema=False)
def preview_img(token: str, name: str, conn=Depends(db)):
    r = _site_by_token(conn, token)
    p = sites.brand_path(name) or sites.image_path(r["id"], name)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/p/{token}/logo-icon.svg", include_in_schema=False)
def preview_icon(token: str, conn=Depends(db)):
    d = json.loads(_site_by_token(conn, token)["data"])
    return Response(sites.icon_file(d), media_type="image/svg+xml")


@app.get("/api/sites/{sid}/img/{name}")
def site_img(sid: int, name: str, user=Depends(current_user)):
    p = sites.image_path(sid, name)
    if not p:
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- oficiální loga (Google, Facebook) – nahrává admin

@app.get("/api/brand")
def brand_list(user=Depends(current_user)):
    return sites.brand_files()


@app.post("/api/brand/{key}")
async def brand_upload(key: str, request: Request, user=Depends(admin_user)):
    try:
        sites.save_brand(key, await request.body(), (request.headers.get("content-type") or "").split(";")[0].strip())
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return sites.brand_files()


@app.get("/brand/{fname}", include_in_schema=False)
def brand_file(fname: str):
    p = sites.brand_path(fname)
    if not p:
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- poptávky z veřejného webu

class InquiryIn(BaseModel):
    name: str = Field("", max_length=120)
    company: str = Field("", max_length=160)
    contact: str = Field("", max_length=160)
    need: str = Field("", max_length=120)
    message: str = Field("", max_length=4000)
    web: str = ""          # past na roboty – skryté pole, člověk ho nevyplní


_INQ: dict = {}


@app.post("/api/public/inquiry")
def public_inquiry(body: InquiryIn, request: Request, conn=Depends(db)):
    if body.web.strip():                      # robot – tváříme se, že je vše v pořádku
        return {"ok": True}
    if not (body.name.strip() and body.company.strip() and body.contact.strip()):
        raise HTTPException(422, "Vyplňte prosím jméno, firmu a kontakt.")
    ip = _client_ip(request)
    now = dt.datetime.now().timestamp()
    recent = [t for t in _INQ.get(ip, []) if now - t < 3600]
    if len(recent) >= 5:
        raise HTTPException(429, "Poptávek bylo z této adresy odesláno už hodně. Zkuste to prosím později nebo zavolejte.")
    _INQ[ip] = recent + [now]
    q = {"name": body.name.strip(), "company": body.company.strip(), "contact": body.contact.strip(),
         "need": body.need.strip(), "message": body.message.strip()}
    conn.execute("INSERT INTO inquiries(created_at, name, company, contact, need, message, ip) VALUES (?,?,?,?,?,?,?)",
                 (_iso(_now()), q["name"], q["company"], q["contact"], q["need"], q["message"], ip))
    import threading
    from . import notify
    threading.Thread(target=notify.send_inquiry, args=(q,), daemon=True).start()
    return {"ok": True}


@app.get("/api/inquiries")
def list_inquiries(user=Depends(current_user), conn=Depends(db)):
    rows = conn.execute("""SELECT i.*, u.display_name handled_by_name FROM inquiries i
                           LEFT JOIN users u ON u.id = i.handled_by ORDER BY (i.status = 'new') DESC, i.id DESC LIMIT 300""")
    return [dict(r) for r in rows]


class InquiryUpdate(BaseModel):
    status: str
    note: str = Field("", max_length=2000)


@app.put("/api/inquiries/{iid}")
def update_inquiry(iid: int, body: InquiryUpdate, user=Depends(current_user), conn=Depends(db)):
    if body.status not in ("new", "done"):
        raise HTTPException(400, "Neplatný stav")
    n = conn.execute("UPDATE inquiries SET status=?, note=?, handled_by=?, handled_at=? WHERE id=?",
                     (body.status, body.note, user["id"] if body.status == "done" else None,
                      _iso(_now()) if body.status == "done" else None, iid)).rowcount
    if not n:
        raise HTTPException(404, "Poptávka neexistuje")
    return list_inquiries(user, conn)
