"""Obohacení firem (ARES, detekce webu, Google) a výpočet skóre. Běží jako úloha na pozadí."""
import asyncio
import datetime as dt
import json
import random
import uuid

from . import ares, places, webcheck
from .config import ARES_CONCURRENCY, CACHE_DAYS, GOOGLE_CONCURRENCY, WEB_CONCURRENCY
from .db import connect, get_meta
from .scoring import score

JOBS = {}


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def _fresh(ts: str) -> bool:
    try:
        return dt.datetime.now() - dt.datetime.fromisoformat(ts) < dt.timedelta(days=CACHE_DAYS)
    except (TypeError, ValueError):
        return False


def is_demo(conn) -> bool:
    return get_meta(conn, "demo") == "1"


# ---------------------------------------------------------------- načtení uložených signálů

def load_signals(conn, ico: str):
    a = conn.execute("SELECT data, fetched_at FROM ares_cache WHERE ico=?", (ico,)).fetchone()
    w = conn.execute("SELECT url, match, detail, checked_at FROM web_cache WHERE ico=?", (ico,)).fetchone()
    g = conn.execute("SELECT place_id, matched_at, confidence FROM google_link WHERE ico=?", (ico,)).fetchone()
    ares_d = json.loads(a["data"]) if a else None
    web_d = {"url": w["url"], "match": w["match"], "tried": json.loads(w["detail"] or "[]")} if w else None
    google_d = places.cached(g["place_id"]) if g and g["place_id"] else None
    if g and g["place_id"] and not google_d and g["place_id"].startswith("demo-"):
        firm = conn.execute("SELECT * FROM firms WHERE ico=?", (ico,)).fetchone()
        if firm:
            google_d = _demo_signals(dict(firm))[2]
    return ares_d, web_d, google_d, g


def rescore(conn, firm: dict, enriched=None):
    ares_d, web_d, google_d, glink = load_signals(conn, firm["ico"])
    s = score(firm, ares_d, web_d, google_d, google_checked=bool(glink))
    if enriched is None:
        row = conn.execute("SELECT enriched FROM scores WHERE ico=?", (firm["ico"],)).fetchone()
        enriched = row["enriched"] if row else 0
    conn.execute(
        """INSERT INTO scores(ico, p_noweb, vitality, priority, enriched, computed_at) VALUES (?,?,?,?,?,?)
           ON CONFLICT(ico) DO UPDATE SET p_noweb=excluded.p_noweb, vitality=excluded.vitality,
           priority=excluded.priority, enriched=excluded.enriched, computed_at=excluded.computed_at""",
        (firm["ico"], s["p_noweb"], s["vitality"], s["priority"], int(enriched), _now()),
    )
    return s


# ---------------------------------------------------------------- demo (bez sítě)

def _demo_signals(firm):
    rnd = random.Random(int(firm["ico"]))
    has_web = rnd.random() < 0.35
    ares_d = {"found": True, "nazev": firm["nazev"], "dph": rnd.random() < 0.45,
              "insolvence": rnd.random() < 0.03, "likvidace": False,
              "phone": None, "email": None, "datova_schranka": None, "www": None}
    if rnd.random() < 0.15:
        ares_d["email"] = "info@example.cz"
    slug = "".join(webcheck.name_tokens(firm["nazev"]))
    web_d = {"url": f"https://{slug}.cz/", "match": rnd.choice(["ico", "name"])} if has_web and rnd.random() < 0.6 \
        else {"url": None, "match": rnd.choice(["none", "none", "parked", "other"])}
    google_d = None
    if rnd.random() < 0.7:
        google_d = places._remember({
            "id": f"demo-{firm['ico']}",
            "displayName": {"text": webcheck.clean_name(firm["nazev"]).replace("[DEMO] ", "")},
            "formattedAddress": firm["adresa"],
            "websiteUri": (f"https://{slug}.cz/" if has_web else (None if rnd.random() < 0.7 else "https://facebook.com/demo")),
            "nationalPhoneNumber": f"7{rnd.randint(10, 99)} {rnd.randint(100, 999)} {rnd.randint(100, 999)}",
            "businessStatus": "OPERATIONAL" if rnd.random() < 0.95 else "CLOSED_PERMANENTLY",
            "rating": round(rnd.uniform(3.6, 5.0), 1), "userRatingCount": rnd.choice([0, 2, 7, 15, 48, 120]),
            "googleMapsUri": f"https://www.google.com/maps/search/?api=1&query={firm['lat']},{firm['lon']}",
            "regularOpeningHours": {"weekdayDescriptions": ["Po–Pá 8:00–17:00"]} if rnd.random() < 0.6 else None,
            "location": {"latitude": firm["lat"], "longitude": firm["lon"]},
        })
    return ares_d, web_d, google_d


# ---------------------------------------------------------------- úloha

async def _enrich_one(ico, job, clients, sems, demo):
    conn = connect()
    try:
        firm = conn.execute("SELECT * FROM firms WHERE ico=?", (ico,)).fetchone()
        if not firm:
            return
        firm = dict(firm)
        if demo:
            await asyncio.sleep(0.01)
            ares_d, web_d, google_d = _demo_signals(firm)
            conn.execute("INSERT OR REPLACE INTO ares_cache VALUES (?,?,?)", (ico, _now(), ares.dumps(ares_d)))
            conn.execute("INSERT OR REPLACE INTO web_cache VALUES (?,?,?,?,?)", (ico, _now(), web_d["url"], web_d["match"], "[]"))
            conn.execute("INSERT OR REPLACE INTO google_link VALUES (?,?,?,?)",
                         (ico, google_d["place_id"] if google_d else None, _now(), 0.9 if google_d else 0))
        else:
            # ARES
            row = conn.execute("SELECT fetched_at FROM ares_cache WHERE ico=?", (ico,)).fetchone()
            if not row or not _fresh(row["fetched_at"]):
                async with sems["ares"]:
                    d = await ares.fetch(clients["ares"], ico)
                conn.execute("INSERT OR REPLACE INTO ares_cache VALUES (?,?,?)", (ico, _now(), ares.dumps(d)))
            # Detekce domén
            row = conn.execute("SELECT checked_at FROM web_cache WHERE ico=?", (ico,)).fetchone()
            if job.get("dns_ok") and (not row or not _fresh(row["checked_at"])):
                async with sems["web"]:
                    w = await webcheck.check(clients["web"], ico, firm["nazev"])
                conn.execute("INSERT OR REPLACE INTO web_cache VALUES (?,?,?,?,?)",
                             (ico, _now(), w["url"], w["match"], json.dumps(w.get("tried", []))))
            # Google
            if places.enabled():
                link = conn.execute("SELECT place_id, matched_at FROM google_link WHERE ico=?", (ico,)).fetchone()
                async with sems["google"]:
                    if link and link["place_id"]:
                        await places.details(clients["google"], link["place_id"])
                    elif not link or not _fresh(link["matched_at"]):
                        g, conf = await places.find_match(clients["google"], firm["nazev"], firm["obec"], firm["lat"], firm["lon"])
                        conn.execute("INSERT OR REPLACE INTO google_link VALUES (?,?,?,?)",
                                     (ico, g["place_id"] if g else None, _now(), conf))
        rescore(conn, firm, enriched=True)
        conn.commit()
    except Exception as e:  # jedna firma nesmí shodit celou úlohu
        job["errors"].append(f"{ico}: {e}")
    finally:
        conn.close()
        job["done"] += 1


async def _run(job_id, icos):
    job = JOBS[job_id]
    conn = connect()
    demo = is_demo(conn)
    conn.close()
    clients = {}
    try:
        clients = {"ares": ares.new_client(), "web": webcheck.new_client(), "google": places.new_client()}
        sems = {"ares": asyncio.Semaphore(ARES_CONCURRENCY), "web": asyncio.Semaphore(WEB_CONCURRENCY),
                "google": asyncio.Semaphore(GOOGLE_CONCURRENCY)}
        if not demo:
            # Bez funkčního DNS by detekce webu hlásila „žádná doména“ – to by zkreslilo skóre
            job["dns_ok"] = await webcheck._resolves("seznam.cz") or await webcheck._resolves("google.com")
            if not job["dns_ok"]:
                job["errors"].append("DNS nefunguje – detekce webu přeskočena")
        await asyncio.gather(*(_enrich_one(i, job, clients, sems, demo) for i in icos))
    except Exception as e:  # noqa: BLE001
        job["errors"].append(f"úloha selhala: {e}")
    finally:
        for c in clients.values():
            await c.aclose()
        job["status"] = "done"
        job["finished_at"] = _now()


def start_job(icos, user):
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"id": job_id, "total": len(icos), "done": 0, "errors": [], "status": "running",
                    "started_by": user, "started_at": _now()}
    asyncio.get_running_loop().create_task(_run(job_id, icos))
    return JOBS[job_id]
