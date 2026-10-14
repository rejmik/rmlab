"""Generátor webů pro provozovny (kadeřnictví, kavárny, restaurace).

Kluci vyplní brief, systém z něj vyrobí jednostránkový mobilní web podle šablony
a hlídá pravidla z checklistu „Jak má vypadat správný web“.
"""
import base64
import html
import io
import json
import re
import secrets
import zipfile
from pathlib import Path

from .config import DB_PATH

SITES_DIR = DB_PATH.parent / "sites"
BRAND_DIR = DB_PATH.parent / "brand"
BRAND_KEYS = ("google", "facebook")
BRAND_TYPES = {"image/svg+xml": "svg", "image/png": "png", "image/webp": "webp"}


def brand_files() -> dict:
    """Oficiální loga nahraná adminem: {"google": "brand-google.svg", ...}."""
    out = {}
    if BRAND_DIR.exists():
        for k in BRAND_KEYS:
            for ext in ("svg", "png", "webp"):
                if (BRAND_DIR / f"{k}.{ext}").exists():
                    out[k] = f"brand-{k}.{ext}"
                    break
    return out


def brand_path(fname: str):
    m = re.fullmatch(r"brand-(google|facebook)\.(svg|png|webp)", fname or "")
    if not m:
        return None
    p = BRAND_DIR / f"{m.group(1)}.{m.group(2)}"
    return p if p.exists() else None


def save_brand(key: str, raw: bytes, content_type: str) -> str:
    if key not in BRAND_KEYS:
        raise ValueError("Neznámé logo")
    ext = BRAND_TYPES.get(content_type)
    if not ext:
        raise ValueError("Logo nahrajte jako SVG, PNG nebo WebP")
    if len(raw) > 300 * 1024:
        raise ValueError("Soubor loga je příliš velký (max. 300 kB)")
    if ext == "svg" and b"<svg" not in raw[:2000].lower():
        raise ValueError("Soubor není platné SVG")
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for old in BRAND_DIR.glob(f"{key}.*"):
        old.unlink()
    (BRAND_DIR / f"{key}.{ext}").write_bytes(raw)
    return f"brand-{key}.{ext}"
DAYS = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]

# ---------------------------------------------------------------- typy provozoven

TEMPLATES = {"1": "Šablona 1 – rovné linie", "2": "Šablona 2 – oblé prvky", "3": "Šablona 3 – vizitka",
             "4": "Šablona 4 – pop (pro mladé)", "5": "Šablona 5 – luxus (čistý bílý)",
             "6": "Šablona 6 – urban (žlutočerná)",
             "7": "Šablona 7 – barevný štětec"}

# Šablona 2: stejná struktura, všechny prvky se zaoblením
ROUND_CSS = """
body.t-round {{ --r:22px; }}
.t-round .btn, .t-round .hnav a, .t-round .live, .t-round .rchip, .t-round .soc, .t-round .arr, .t-round .vbtn,
.t-round .lb-close, .t-round .chips a, .t-round .facts a {{ border-radius:999px; }}
.t-round .brand .badge, .t-round .foot-brand .badge, .t-round .usp-i, .t-round .person img {{ border-radius:50%; }}
.t-round .blogo {{ border-radius:6px; }}
.t-round .facts {{ border-top:none; gap:8px; }}
.t-round .facts a {{ border:none; background:rgba(255,255,255,.12); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); padding:10px 18px; }}
.t-round .bar .badge {{ border-radius:50%; }}
.t-round .dock {{ left:12px; right:12px; bottom:calc(12px + env(safe-area-inset-bottom)); border-radius:24px; padding:6px; gap:6px; box-shadow:0 12px 30px rgba(0,0,0,.3); }}
.t-round .dock a {{ border-radius:18px; border:none; min-height:50px; }}
.t-round .usp-grid {{ gap:10px; padding-top:20px; padding-bottom:20px; }}
.t-round .usp {{ border:none; background:rgba(255,255,255,.1); border-radius:18px; padding:20px; }}
.t-round .about-img, .t-round .shot, .t-round .video, .t-round .rev {{ border-radius:var(--r); overflow:hidden; }}
.t-round .about-img {{ margin-left:0; margin-right:0; }}
.t-round .about-text ul {{ border-top:none; }}
.t-round .about-text li {{ border-bottom:none; background:var(--surface); border-radius:14px; margin:8px 0; padding:12px 16px 12px 40px; }}
.t-round .about-text li::before {{ left:16px; top:50%; width:10px; height:10px; border-radius:50%; margin-top:-5px; }}
.t-round .chips {{ border-bottom:none; gap:8px; padding-top:10px; padding-bottom:10px; background:color-mix(in srgb, var(--surface) 92%, transparent); }}
.t-round .chips a {{ border:1px solid var(--line); padding:9px 16px; }}
.t-round .chips a:hover, .t-round .chips a.on {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.t-round .menu-cols {{ background:var(--bg); border-radius:var(--r); padding:22px 20px; }}
.t-round .og h3 {{ border-bottom-width:1px; }}
.t-round .rev {{ border:none; background:rgba(255,255,255,.07); }}
.t-round .rev footer {{ border-top:none; padding-top:0; }}
.t-round .rsum {{ border:none; background:rgba(255,255,255,.07); border-radius:var(--r); padding:0 22px; margin:0 var(--pad) 32px; }}
.t-round .progress, .t-round .progress span {{ border-radius:2px; }}
.t-round .contact {{ border-top:none; gap:12px; }}
.t-round .cbox {{ background:var(--surface); border-radius:var(--r); padding:24px; border-bottom:none; }}
.t-round .hours tr:last-child th, .t-round .hours tr:last-child td {{ border-bottom:none; }}
.t-round footer.foot {{ border-radius:32px 32px 0 0; overflow:hidden; margin-top:-8px; }}
.t-round .lb-track img {{ border-radius:16px; }}
@media (min-width: 900px) {{
  .t-round .usp-grid {{ padding-top:40px; padding-bottom:40px; }}
  .t-round .usp {{ border-left:none; padding:28px; }}
  .t-round .usp:first-child {{ padding-left:28px; }}
  .t-round .usp-grid {{ gap:14px; }}
  .t-round .facts {{ grid-template-columns:repeat(3, max-content); }}
  .t-round .facts a, .t-round .facts a + a {{ border-left:none; padding:12px 22px; }}
  .t-round .menu-cols {{ padding:40px 44px; }}
  .t-round .rbig + .rbig {{ border-left:1px solid rgba(255,255,255,.15); }}
  .t-round .rsum {{ max-width:calc(var(--max) - 2 * var(--pad)); margin:0 auto 32px; }}
  .t-round .cbox {{ padding:32px; }}
  .t-round .contact {{ column-gap:16px; }}
}}
"""

TYPES = {
    "kadernictvi": {
        "label": "Kadeřnictví / salon",
        "schema": "HairSalon",
        "icon": "scissors",
        "offer_title": "Služby a ceník",
        "offer_nav": "Ceník",
        "booking": "Objednávky telefonicky",
        "theme": {"bg": "#EEEBF2", "surface": "#FFFFFF", "ink": "#1E1A24", "muted": "#6A6372",
                  "accent": "#6B2D5C", "accent2": "#E9C9D3"},
        "fonts": {"display": "Bricolage Grotesque", "display_w": "600;800", "body": "Figtree"},
        "usp_examples": ["Stříháme i bez objednání", "4 kadeřnice najednou – čekáte max. 30 minut",
                         "Parkování přímo před salonem"],
        "offer_examples": [("Dámský střih", "mytí, střih, foukaná", "od 450 Kč"),
                           ("Pánský střih", "", "300 Kč"), ("Barvení", "včetně střihu", "od 900 Kč")],
    },
    "kavarna": {
        "label": "Kavárna / cukrárna",
        "schema": "CafeOrCoffeeShop",
        "icon": "cup",
        "offer_title": "Co u nás ochutnáte",
        "offer_nav": "Nabídka",
        "booking": "Rezervace stolu telefonicky",
        "theme": {"bg": "#E6EBE3", "surface": "#FBFCFA", "ink": "#1F2A22", "muted": "#5E6B61",
                  "accent": "#5A3825", "accent2": "#C8A27A"},
        "fonts": {"display": "Instrument Serif", "display_w": "400", "body": "Figtree"},
        "usp_examples": ["Káva z lokální pražírny", "Domácí dorty pečeme každé ráno", "Dětský koutek a zahrádka"],
        "offer_examples": [("Espresso", "", "55 Kč"), ("Cappuccino", "", "75 Kč"), ("Domácí dort", "dle denní nabídky", "85 Kč")],
    },
    "restaurace": {
        "label": "Restaurace / bistro",
        "schema": "Restaurant",
        "icon": "plate",
        "offer_title": "Menu",
        "offer_nav": "Menu",
        "booking": "Rezervace telefonicky",
        "theme": {"bg": "#FBFAF7", "surface": "#FFFFFF", "ink": "#18211D", "muted": "#5B655F",
                  "accent": "#1F5B45", "accent2": "#E0B54A"},
        "fonts": {"display": "DM Serif Display", "display_w": "400", "body": "Figtree"},
        "usp_examples": ["Polední menu každý všední den", "Vaříme z čerstvých surovin od místních farmářů",
                         "Salonek pro 30 hostů na oslavy"],
        "offer_examples": [("Polévka dne", "", "55 Kč"), ("Svíčková na smetaně", "houskový knedlík", "189 Kč"),
                           ("Smažený sýr", "hranolky, tatarka", "169 Kč")],
    },
}

ICONS = {
    "scissors": '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.1 15.9 19 3M15.9 15.9 5 3"/>',
    "cup": '<path d="M4 9h12v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16"/>'
           '<path d="M8 3c0 1.5 1.5 1.5 1.5 3M12 3c0 1.5 1.5 1.5 1.5 3"/>',
    "plate": '<path d="M5 3v5a2 2 0 0 0 4 0V3M7 10v11"/><path d="M18 3c-2 2-2.5 5-2.5 8H18v10"/>',
    "leaf": '<path d="M5 19C5 10 10 5 20 4c-1 10-6 15-15 15z"/><path d="M5 19 13 11"/>',
    "star": '<path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/>',
}


def guess_type(nace: str) -> str:
    n = nace or ""
    if n.startswith("9602"):
        return "kadernictvi"
    if n.startswith("563"):
        return "kavarna"
    if n.startswith("56"):
        return "restaurace"
    return "kadernictvi"


# ---------------------------------------------------------------- data

def empty_data(kind: str) -> dict:
    t = TYPES[kind]
    return {
        "type": kind,
        "name": "",
        "logo": {"text": "", "icon": t["icon"]},
        "theme": {"template": "1", "accent": "", "font_display": "", "font_display_w": "", "font_body": ""},
        "hero": {"title": "", "subtitle": "", "image": "", "alt": "", "video": ""},
        "notes": "",
        "about": "",
        "usps": [],
        "offer_title": t["offer_title"],
        "offer": [],
        "gallery": [],
        "video": "",
        "reviews": [],
        "reviews_link": "",
        "contact": {"person": "", "role": "", "photo": "", "photo_alt": "", "phone": "", "email": "",
                    "address": "", "lat": None, "lon": None},
        "hours": [{"day": d, "value": ""} for d in DAYS],
        "hours_note": "",
        "booking_note": t["booking"],
        "social": {"facebook": "", "instagram": "", "tiktok": ""},
        "ratings": {"google": {"value": "", "count": "", "url": ""},
                    "facebook": {"value": "", "count": "", "url": ""}},
        "seo": {"title": "", "description": ""},
        "company": {"ico": "", "legal_name": "", "address": ""},
        "domain": "",
        "images": {},
        "extra": {"intro_title": ""},
        "stats": [],
    }


_GOOGLE_DAY = {"pondělí": 0, "úterý": 1, "středa": 2, "čtvrtek": 3, "pátek": 4, "sobota": 5, "neděle": 6,
               "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def prefill(firm: dict, ares: dict = None, google: dict = None) -> dict:
    from .webcheck import clean_name
    kind = guess_type(firm.get("nace"))
    d = empty_data(kind)
    name = clean_name(firm["nazev"]).replace("[DEMO] ", "")
    if google and google.get("name"):
        name = google["name"]
    d["name"] = name
    d["logo"]["text"] = name
    d["company"] = {"ico": firm["ico"], "legal_name": firm["nazev"], "address": firm.get("adresa") or ""}
    c = d["contact"]
    c["address"] = (google or {}).get("address") or firm.get("adresa") or ""
    c["lat"], c["lon"] = firm.get("lat"), firm.get("lon")
    c["phone"] = (google or {}).get("phone") or (ares or {}).get("phone") or ""
    c["email"] = (ares or {}).get("email") or ""
    if google and google.get("maps_url"):
        d["reviews_link"] = google["maps_url"]
    for line in (google or {}).get("hours") or []:
        if ":" not in line:
            continue
        day, val = line.split(":", 1)
        idx = _GOOGLE_DAY.get(day.strip().lower())
        if idx is not None:
            v = val.strip()
            d["hours"][idx]["value"] = "Zavřeno" if v.lower() in ("zavřeno", "closed") else v
    return d


def new_token() -> str:
    return secrets.token_urlsafe(12)


# ---------------------------------------------------------------- obrázky

MAX_IMAGE = 6 * 1024 * 1024


def site_dir(site_id: int) -> Path:
    p = SITES_DIR / str(site_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_image(site_id: int, data_url: str) -> str:
    m = re.match(r"^data:image/(jpeg|png|webp);base64,(.+)$", data_url or "", re.S)
    if not m:
        raise ValueError("Podporované formáty jsou JPG, PNG a WebP")
    raw = base64.b64decode(m.group(2), validate=False)
    if len(raw) > MAX_IMAGE:
        raise ValueError("Obrázek je příliš velký (max. 6 MB)")
    sig = {"jpeg": b"\xff\xd8", "png": b"\x89PNG", "webp": b"RIFF"}[m.group(1)]
    if not raw.startswith(sig):
        raise ValueError("Soubor není platný obrázek")
    ext = {"jpeg": "jpg", "png": "png", "webp": "webp"}[m.group(1)]
    name = f"{secrets.token_hex(5)}.{ext}"
    (site_dir(site_id) / name).write_bytes(raw)
    return name


MAX_VIDEO = 40 * 1024 * 1024


def save_video(site_id: int, raw: bytes, content_type: str) -> str:
    if len(raw) > MAX_VIDEO:
        raise ValueError("Video je příliš velké (max. 40 MB). Zkraťte ho nebo zmenšete rozlišení.")
    if content_type == "video/mp4" and raw[4:8] == b"ftyp":
        ext = "mp4"
    elif content_type == "video/webm" and raw[:4] == b"\x1a\x45\xdf\xa3":
        ext = "webm"
    else:
        raise ValueError("Podporované formáty videa jsou MP4 a WebM")
    name = f"{secrets.token_hex(5)}.{ext}"
    (site_dir(site_id) / name).write_bytes(raw)
    return name


def image_path(site_id: int, name: str):
    if not re.fullmatch(r"[0-9a-f]{10}\.(jpg|png|webp|mp4|webm)", name or ""):
        return None
    p = SITES_DIR / str(site_id) / name
    return p if p.exists() else None


# ---------------------------------------------------------------- kontrola kvality

def _len(s):
    return len((s or "").strip())


def checks(d: dict) -> list:
    """Pravidla z checklistu „Jak má vypadat správný web“. level: error = brání schválení, warn = doporučení."""
    out = []

    def add(group, label, ok, level="error", hint=""):
        out.append({"group": group, "label": label, "ok": bool(ok), "level": level, "hint": hint})

    obec = ""
    m = re.search(r"\d{3}\s?\d{2}\s+(.+)$", d["contact"].get("address") or "")
    if m:
        obec = m.group(1).split(",")[0].strip()
    stem = obec[:5].lower() if obec else ""

    h1 = d["hero"]["title"]
    add("Jednoduchost", "Hlavní nadpis (H1) má 10–70 znaků", 10 <= _len(h1) <= 70, hint=f"teď {_len(h1)}")
    add("Jednoduchost", "Logo – název vyplněn", _len(d["logo"]["text"]) >= 2)
    add("Jednoduchost", "Podnadpis pod hlavním nadpisem", _len(d["hero"]["subtitle"]) >= 10, "warn")

    add("Informace a SEO", "Text o firmě má aspoň 300 znaků", _len(d["about"]) >= 300, hint=f"teď {_len(d['about'])}")
    add("Informace a SEO", "Text je členěný (odstavce nebo odrážky)",
        "\n\n" in (d["about"] or "") or "\n- " in (d["about"] or ""), "warn")
    offer = [o for o in d["offer"] if _len(o.get("name")) >= 2]
    add("Informace a SEO", "Nabídka / ceník: aspoň 3 položky", len(offer) >= 3, hint=f"teď {len(offer)}")
    add("Informace a SEO", "U všech položek nabídky je cena", offer and all(_len(o.get("price")) for o in offer), "warn")
    st, sd = d["seo"]["title"], d["seo"]["description"]
    add("Informace a SEO", "SEO titulek má 30–60 znaků", 30 <= _len(st) <= 60, hint=f"teď {_len(st)}")
    add("Informace a SEO", "SEO titulek obsahuje obec", not stem or stem in (st or "").lower(), "warn",
        hint=obec)
    add("Informace a SEO", "SEO popisek má 70–160 znaků", 70 <= _len(sd) <= 160, hint=f"teď {_len(sd)}")

    imgs = [g for g in d["gallery"] if g.get("file")]
    add("Fotky a video", "Hlavní fotka nahoře" + (" (i jako náhled videa)" if d["hero"].get("video") else ""), bool(d["hero"]["image"]))
    vmeta = (d.get("images") or {}).get(d["hero"].get("video") or "") or {}
    if d["hero"].get("video"):
        add("Fotky a video", "Video v úvodu má do 15 MB (rychlé načítání)", (vmeta.get("size") or 0) <= 15 * 1024 * 1024, "warn",
            hint=f"{round((vmeta.get('size') or 0) / 1048576, 1)} MB")
    tpl = str((d.get("theme") or {}).get("template") or "1")
    if tpl == "3":
        add("Fotky a video", "Galerie: pár vlastních fotek (u vizitky stačí 3)", len(imgs) >= 3, "warn", hint=f"teď {len(imgs)}")
    else:
        add("Fotky a video", "Galerie: aspoň 3 vlastní fotky", len(imgs) >= 3, hint=f"teď {len(imgs)}")
    if tpl == "7":
        stats7 = [x for x in d.get("stats") or [] if _len(x.get("value"))]
        add("Jednoduchost", "Štětec: 2–4 čísla pod úvodem (např. 15 let / 4 kadeřnice)", len(stats7) >= 2, "warn",
            hint="jinak se použije hodnocení a čas otevření")
    if tpl == "5":
        add("Fotky a video", "Luxus: aspoň 6 fotek (karusel, dlaždice, mozaika)", len(imgs) >= 6, "warn", hint=f"teď {len(imgs)}")
        stats = [x for x in d.get("stats") or [] if _len(x.get("value"))]
        add("Jednoduchost", "Luxus: velká čísla do dlaždic (např. 4,9 ★ / 7:00 / 30)", stats, "warn",
            hint="jinak se použije hodnocení a čas otevření")
        add("Jednoduchost", "Luxus: krátký úderný nadpis (do 30 znaků)", _len(h1) <= 30, "warn", hint=f"teď {_len(h1)}")
    if tpl in ("4", "6", "7"):
        add("Jednoduchost", "Výrazná šablona: krátký nadpis do 30 znaků (název firmy patří do loga)", _len(h1) <= 30, "warn",
            hint=f"teď {_len(h1)}")
    if tpl in ("4", "6"):
        add("Jednoduchost", ("Pop" if tpl == "4" else "Urban") + ": zvýrazněné slovo v nadpisu (**slovo**)", "**" in (h1 or ""), "warn")
    add("Fotky a video", "Každá fotka má popisek (alt)", all(_len(g.get("alt")) >= 5 for g in imgs)
        and (not d["contact"]["photo"] or _len(d["contact"]["photo_alt"]) >= 5))
    meta0 = d.get("images") or {}
    wide = [i for i, g in enumerate(imgs, 1) if (meta0.get(g["file"]) or {}).get("w") and
            meta0[g["file"]]["w"] / max(1, meta0[g["file"]].get("h") or 1) > 1.15]
    add("Fotky a video", "Fotky v galerii na výšku 4:5 nebo čtverec (formát sociálních sítí)", not wide, "warn",
        hint=("na šířku: " + ", ".join(f"fotka {i}" for i in wide) + " – oříznou se") if wide else "")
    add("Fotky a video", "Video (nepovinné, ale pomáhá)", bool(d.get("video")), "warn")
    if d.get("video"):
        add("Fotky a video", "Odkaz na video je z YouTube", bool(_yt(d["video"])))
    # kvalita fotek – měří prohlížeč při nahrání (rozlišení, jas, ostrost)
    meta = d.get("images") or {}

    def qual(name, min_w):
        q = meta.get(name) or {}
        probs = []
        if q.get("w") and max(q["w"], q.get("h") or 0) < min_w:
            probs.append(f"malé rozlišení ({q['w']}×{q.get('h')})")
        if q.get("bright") is not None and q["bright"] < 70:
            probs.append("tmavá")
        if q.get("bright") is not None and q["bright"] > 215:
            probs.append("přesvícená")
        if q.get("sharp") is not None and q["sharp"] < 60:
            probs.append("rozmazaná")
        return probs

    bad = []
    if d["hero"]["image"]:
        bad += [f"hlavní fotka: {p}" for p in qual(d["hero"]["image"], 1200)]
    for i, g in enumerate(imgs, 1):
        bad += [f"fotka {i}: {p}" for p in qual(g["file"], 900)]
    if d["contact"]["photo"]:
        bad += [f"kontaktní fotka: {p}" for p in qual(d["contact"]["photo"], 300)]
    add("Fotky a video", "Fotky jsou ostré, dobře osvětlené a dost velké", not bad, "warn", hint="; ".join(bad[:4]))

    usps = [u for u in d["usps"] if _len(u.get("title")) >= 3]
    add("Čím se liší (USP)", "Aspoň 3 výhody, kterými se firma liší", len(usps) >= 3, hint=f"teď {len(usps)}")

    revs = [r for r in d["reviews"] if _len(r.get("text")) >= 10]
    add("Recenze", "Aspoň 1 recenze zákazníka", len(revs) >= 1)
    add("Recenze", "Všechny recenze mají souhlas zákazníka", all(r.get("consent") for r in revs))
    add("Recenze", "Recenze se jménem autora", revs and all(_len(r.get("author")) for r in revs), "warn")

    rt = d.get("ratings") or {}
    has_rating = any(_rating(rt.get(k)) for k in ("google", "facebook"))
    add("Recenze", "Hodnocení z Googlu nebo Facebooku (hvězdičky)", has_rating, "warn")
    bad_r = [k for k in ("google", "facebook") if (rt.get(k) or {}).get("value") and not _rating(rt.get(k))]
    add("Recenze", "Hodnocení je číslo 1–5 (např. 4,8)", not bad_r, hint=", ".join(bad_r))
    soc = d.get("social") or {}
    add("Kontakt", "Odkaz na sociální sítě", any((soc.get(k) or "").startswith("http") for k in soc), "warn")
    bad_s = [k for k, v in soc.items() if v and not v.startswith("http")]
    add("Kontakt", "Odkazy na sítě začínají https://", not bad_s, hint=", ".join(bad_s))

    c = d["contact"]
    add("Kontakt", "Telefon", _len(c["phone"]) >= 9)
    add("Kontakt", "Adresa", _len(c["address"]) >= 5)
    add("Kontakt", "E-mail", "@" in (c["email"] or ""), "warn")
    add("Kontakt", "Fotka a jméno kontaktní osoby", bool(c["photo"]) and _len(c["person"]) >= 2)
    add("Kontakt", "Otevírací doba vyplněná pro všechny dny", all(_len(h["value"]) for h in d["hours"]))
    add("Kontakt", "IČO v patičce", bool(re.fullmatch(r"\d{8}", d["company"]["ico"] or "")))

    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("notes", "images", "company"):
                    yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
    left = [m for s_ in strings(d) for m in re.findall(r"\[(?:doplnit|ověřit)[^\]]*\]", s_)]
    add("Dokončení", "Žádná místa k doplnění ([doplnit…], [ověřit…])", not left,
        hint=", ".join(left[:3]))
    return out


def _rating(r):
    """Vrátí (hodnota, počet) nebo None."""
    if not r:
        return None
    try:
        v = float(str(r.get("value") or "").replace(",", ".").strip())
    except ValueError:
        return None
    if not 1 <= v <= 5:
        return None
    return v, str(r.get("count") or "").strip()


def summary(chk: list) -> dict:
    errs = [c for c in chk if not c["ok"] and c["level"] == "error"]
    warns = [c for c in chk if not c["ok"] and c["level"] == "warn"]
    return {"errors": len(errs), "warnings": len(warns), "total": len(chk),
            "passed": sum(1 for c in chk if c["ok"]), "ready": not errs}


# ---------------------------------------------------------------- vykreslení

def js(o) -> str:
    """JSON bezpečný pro vložení do <script> (nejde ukončit tag)."""
    return json.dumps(o, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _inline(s: str) -> str:
    s = e(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((#[a-z-]+|https?://[^\s)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def rich(text: str) -> str:
    """Mini-markdown: odstavce, odrážky „- “, **tučně**, [odkaz](#kontakt), ### podnadpis."""
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l.strip().startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{_inline(l.strip()[2:])}</li>" for l in lines) + "</ul>")
        elif lines[0].startswith("### "):
            out.append(f"<h3>{_inline(lines[0][4:])}</h3>")
            if lines[1:]:
                out.append(f"<p>{_inline(' '.join(lines[1:]))}</p>")
        else:
            out.append(f"<p>{_inline(' '.join(l.strip() for l in lines))}</p>")
    return "\n".join(out)


def icon_svg(name: str, size=24, cls="ico") -> str:
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS.get(name, ICONS["star"])}</svg>')


def logo_svg(d: dict, theme: dict) -> str:
    text = e(d["logo"]["text"] or d["name"])
    w = max(220, 70 + int(len(d["logo"]["text"] or d["name"]) * 15))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="64" viewBox="0 0 {w} 64">'
            f'<circle cx="32" cy="32" r="28" fill="{theme["accent"]}"/>'
            f'<g transform="translate(18 18) scale(1.17)" fill="none" stroke="#fff" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS.get(d["logo"]["icon"], ICONS["star"])}</g>'
            f'<text x="72" y="41" font-family="Georgia, serif" font-size="26" fill="{theme["ink"]}">{text}</text></svg>')


def _yt(url: str):
    m = re.search(r"(?:youtu\.be/|v=|embed/|shorts/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def _hours_ld(hours):
    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    spec = []
    for i, h in enumerate(hours):
        for part in re.split(r"[,;]", h.get("value") or ""):
            m = re.search(r"(\d{1,2})[:.](\d{2})\s*[–-]\s*(\d{1,2})[:.](\d{2})", part)
            if m:
                spec.append(f"{days[i]} {int(m.group(1)):02d}:{m.group(2)}-{int(m.group(3)):02d}:{m.group(4)}")
    return spec


def _dots(color, opacity=0.16, size=14):
    from urllib.parse import quote
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}'>"
           f"<circle cx='1.5' cy='1.5' r='1.1' fill='{color}' opacity='{opacity}'/></svg>")
    return "url(\"data:image/svg+xml," + quote(svg) + "\")"


ARROW_L = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 5l-7 7 7 7"/></svg>'
ARROW_R = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5l7 7-7 7"/></svg>'


def _stars(v: float, size=16) -> str:
    """5 hvězd s částečným vyplněním podle hodnocení."""
    pct = max(0.0, min(1.0, v / 5)) * 100
    star = ('<path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.5L12 17.3l-5.9 3.2 1.3-6.5L2.5 9.4l6.6-.8z"/>')
    row = "".join(f'<svg x="{i * 24}" width="24" height="24" viewBox="0 0 24 24">{star}</svg>' for i in range(5))
    return (f'<span class="stars" style="--w:{size * 5}px;--h:{size}px" role="img" aria-label="Hodnocení {v:.1f} z 5">'
            f'<svg class="s-bg" viewBox="0 0 120 24" width="{size * 5}" height="{size}">{row}</svg>'
            f'<span class="s-fg" style="width:{pct:.0f}%"><svg viewBox="0 0 120 24" width="{size * 5}" height="{size}">{row}</svg></span></span>')


def _cz(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _count(text):
    """Samotné číslo doplní o „recenzí“, jakýkoli jiný text (např. „přes 100 recenzí“) nechá, jak je."""
    t = (text or "").strip()
    if not t.isdigit():
        return t
    n = int(t)
    w = "recenze" if n == 1 or (2 <= n % 100 <= 4 and not 12 <= n % 100 <= 14) else "recenzí"
    return f"{n} {w}"


RATING_LABEL = {"google": "Google", "facebook": "Facebook"}


def _fmt(d, name):
    """Formát fotky pro sociální sítě: čtverec (1:1), jinak na výšku 4:5."""
    q = (d.get("images") or {}).get(name) or {}
    w, h = q.get("w"), q.get("h")
    return "sq" if w and h and w / h >= 0.9 else "p45"


WEIGHTS = {"300", "400", "500", "600", "700", "800", "900"}


def _font_ok(name) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ]{1,48}", (name or "").strip()))


def _font_links(family: str, weights) -> str:
    """Každá tloušťka zvlášť – když ji písmo nemá, selže jen ten jeden odkaz a zbytek se načte."""
    fam = family.strip().replace(" ", "+")
    return "".join(f'<link href="https://fonts.googleapis.com/css2?family={fam}:wght@{w}&display=swap" rel="stylesheet">\n'
                   for w in weights)


def _carousel_controls(name):
    return (f'<div class="ctrl" data-for="{name}"><div class="progress"><span></span></div>'
            f'<button class="arr prev" aria-label="Předchozí">{ARROW_L}</button>'
            f'<button class="arr next" aria-label="Další">{ARROW_R}</button></div>')


def render(d: dict, preview_banner: str = "") -> str:
    tpl_ = (d.get("theme") or {}).get("template")
    if tpl_ in ("3", "4", "5", "6", "7"):
        from . import templates_more
        return templates_more.render(tpl_, d, preview_banner)
    kind = d["type"]
    t = TYPES[kind]
    theme = dict(t["theme"])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", d["theme"].get("accent") or ""):
        theme["accent"] = d["theme"]["accent"]
    f = t["fonts"]
    c = d["contact"]
    name = d["name"] or d["logo"]["text"]
    tel = re.sub(r"[^\d+]", "", c["phone"] or "")
    maps = (f"https://www.google.com/maps/search/?api=1&query={c['lat']},{c['lon']}" if c.get("lat")
            else f"https://www.google.com/maps/search/?api=1&query={html.escape(c['address'] or name)}")
    hero_img = f"img/{d['hero']['image']}" if d["hero"]["image"] else ""
    gallery = [g for g in d["gallery"] if g.get("file")]
    usps = [u for u in d["usps"] if (u.get("title") or "").strip()]
    offer = [o for o in d["offer"] if (o.get("name") or "").strip()]
    reviews = [r for r in d["reviews"] if (r.get("text") or "").strip() and r.get("consent")]
    icon = d["logo"]["icon"]
    groups = []
    for o in offer:
        g = (o.get("group") or "").strip()
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append(o)

    nav = [("o-nas", "O nás")]
    if offer:
        nav.append(("nabidka", t["offer_nav"]))
    if gallery:
        nav.append(("fotky", "Fotky"))
    if reviews:
        nav.append(("recenze", "Recenze"))
    nav.append(("kontakt", "Kontakt"))
    nav_html = "".join(f'<a href="#{a}">{e(l)}</a>' for a, l in nav)

    ratings = []
    for key in ("google", "facebook"):
        r = (d.get("ratings") or {}).get(key) or {}
        rv = _rating(r)
        if rv:
            url = r.get("url") if (r.get("url") or "").startswith("http") else (d.get("reviews_link") if key == "google" else "")
            ratings.append({"key": key, "label": RATING_LABEL[key], "value": rv[0], "count": rv[1], "url": url or ""})

    brands = brand_files()

    def brand(r, h=16):
        f_ = brands.get(r["key"])
        return (f'<img class="blogo" src="img/{f_}" alt="{e(r["label"])}" height="{h}">' if f_ else e(r["label"]))

    def rating_chip(r, cls="rchip"):
        sep = " · " if r["count"] else ""
        inner = (f'{_stars(r["value"], 14)}<b>{_cz(r["value"])}</b><span class="rsrc">{brand(r)}'
                 + (f'<span>{sep.strip()} {e(_count(r["count"]))}</span>' if r["count"] else "") + "</span>")
        return (f'<a class="{cls}" href="{e(r["url"])}" target="_blank" rel="noopener">{inner}</a>' if r["url"]
                else f'<span class="{cls}">{inner}</span>')

    hero_ratings = "".join(rating_chip(r) for r in ratings)
    socials = [(lbl, (d.get("social") or {}).get(k)) for k, lbl in (("facebook", "Facebook"), ("instagram", "Instagram"), ("tiktok", "TikTok"))]
    socials = [(lbl, u) for lbl, u in socials if (u or "").startswith("http")]
    social_html = "".join(f'<a class="soc" href="{e(u)}" rel="noopener" target="_blank">{e(lbl)}</a>' for lbl, u in socials)

    ld = {"@context": "https://schema.org", "@type": t["schema"], "name": name,
          "address": c["address"], "telephone": c["phone"] or None, "email": c["email"] or None,
          "image": hero_img or None, "url": f"https://{d['domain']}/" if d.get("domain") else None,
          "openingHours": _hours_ld(d["hours"]) or None}
    if c.get("lat"):
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": c["lat"], "longitude": c["lon"]}
    ld = {k: v for k, v in ld.items() if v}
    th = d.get("theme") or {}
    f = dict(f)
    if _font_ok(th.get("font_display")):
        f["display"] = th["font_display"].strip()
        f["display_w"] = th.get("font_display_w") if str(th.get("font_display_w") or "") in WEIGHTS else "400"
    elif str(th.get("font_display_w") or "") in WEIGHTS:
        f["display_w"] = th["font_display_w"]
    if _font_ok(th.get("font_body")):
        f["body"] = th["font_body"].strip()
    dw = f["display_w"].split(";")[-1]
    tpl = th.get("template") if th.get("template") in TEMPLATES else "1"
    body_cls = "t-round" if tpl == "2" else "t-straight"
    round_css = ROUND_CSS.replace("{{", "{").replace("}}", "}") if tpl == "2" else ""
    font_links = _font_links(f["display"], sorted({"400", dw})) + _font_links(f["body"], ["400", "500", "600", "700"])
    dots_dark = _dots(theme["ink"])
    dots_light = _dots("#ffffff", 0.18)

    h1_plain = re.sub(r"[*][*](.+?)[*][*]", r"\1", d["hero"]["title"] or "")
    hero_bg = (f'<img class="hero-img" src="{e(hero_img)}" alt="{e(d["hero"].get("alt") or name)}" fetchpriority="high">'
               if hero_img else "")
    hero_video = d["hero"].get("video") or ""
    if re.fullmatch(r"[0-9a-f]{10}\.(mp4|webm)", hero_video):
        vtype = "video/mp4" if hero_video.endswith("mp4") else "video/webm"
        hero_bg = (f'<video class="hero-img" id="hero-video" autoplay muted loop playsinline preload="metadata"'
                   + (f' poster="{e(hero_img)}"' if hero_img else "") + f' aria-label="{e(d["hero"].get("alt") or name)}">'
                   f'<source src="img/{hero_video}" type="{vtype}"></video>'
                   '<button class="vbtn" id="vbtn" aria-label="Zastavit video">❚❚</button>')
    facts = []
    if c["address"]:
        facts.append(f'<a href="{e(maps)}" target="_blank" rel="noopener"><small>Adresa</small>{e(c["address"])}</a>')
    facts.append('<a href="#kontakt"><small>Dnes</small><span id="hero-today">–</span></a>')
    if tel:
        facts.append(f'<a href="tel:{tel}"><small>Telefon</small>{e(c["phone"])}</a>')

    usp_html = "" if not usps else '''
  <section class="usps" aria-label="Proč k nám"><div class="wrap usp-grid">''' + "".join(
        f'<article class="usp"><span class="usp-i">{icon_svg(icon, 20)}</span><h3>{e(u["title"])}</h3>'
        + (f"<p>{e(u.get('text'))}</p>" if u.get("text") else "") + "</article>" for u in usps) + "</div></section>"

    about_img = ""
    if gallery:
        g = gallery[0]
        about_img = f'<figure class="about-img"><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy"></figure>'
    about_html = f'''
  <section id="o-nas" class="sec">
    <div class="wrap about {'has-img' if about_img else ''}">
      <div class="about-text"><h2>O nás</h2>{rich(d["about"])}</div>
      {about_img}
    </div>
  </section>'''

    offer_html = ""
    if offer:
        chips = ""
        if len(groups) > 1:
            chips = '<nav class="chips" aria-label="Části nabídky">' + "".join(
                f'<a href="#g{i}">{e(g or "Ostatní")}</a>' for i, (g, _) in enumerate(groups)) + "</nav>"
        body = ""
        for i, (g, items) in enumerate(groups):
            body += f'<div class="og" id="g{i}">' + (f'<h3>{e(g)}</h3>' if g else "") + "<ul class='menu'>"
            for o in items:
                body += (f'<li><div class="mrow"><span class="mname">{e(o["name"])}</span><span class="dots"></span>'
                         f'<span class="mprice">{e(o.get("price"))}</span></div>'
                         + (f'<p class="mdesc">{e(o.get("desc"))}</p>' if o.get("desc") else "") + "</li>")
            body += "</ul></div>"
        offer_html = f'''
  <section id="nabidka" class="sec sec-tint">
    <div class="wrap">
      <div class="sec-head"><h2>{e(d.get("offer_title") or t["offer_title"])}</h2>
        {f'<p class="sec-note">{e(d.get("booking_note"))}</p>' if d.get("booking_note") else ""}</div>
      {chips}
      <div class="menu-cols">{body}</div>
    </div>
  </section>'''

    gal_html = "" if not gallery else f'''
  <section id="fotky" class="sec">
    <div class="wrap sec-head"><h2>Fotky</h2>{_carousel_controls("gal")}</div>
    <div class="bleed" id="gal">''' + "".join(
        f'<button class="shot {_fmt(d, g["file"])}" data-i="{i}" aria-label="Zvětšit: {e(g.get("alt"))}"><img src="img/{e(g["file"])}" '
        f'alt="{e(g.get("alt"))}" loading="lazy" draggable="false"></button>' for i, g in enumerate(gallery)) + '''</div>
  </section>
  <dialog class="lightbox" aria-label="Galerie"><div class="lb-track">''' + "".join(
        f'<figure><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy"><figcaption>{e(g.get("alt"))}</figcaption></figure>'
        for g in gallery) + '</div><button class="lb-close" aria-label="Zavřít">×</button></dialog>'

    yt = _yt(d.get("video"))
    video_html = "" if not yt else (
        f'<section class="sec"><div class="wrap"><div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{yt}" '
        f'title="Video – {e(name)}" loading="lazy" allowfullscreen></iframe></div></div></section>')

    summary_html = "" if not ratings else '<div class="wrap rsum">' + "".join(
        (f'<a class="rbig" href="{e(r["url"])}" target="_blank" rel="noopener">' if r["url"] else '<div class="rbig">')
        + f'<b>{_cz(r["value"])}</b><div>{_stars(r["value"], 20)}<span class="rsrc">{brand(r, 18)}'
        + (f'<span>· {e(_count(r["count"]))}</span>' if r["count"] else "") + "</span></div>" + ("</a>" if r["url"] else "</div>")
        for r in ratings) + "</div>"
    rev_html = "" if not (reviews or ratings) else f'''
  <section id="recenze" class="sec sec-dark">
    <div class="wrap sec-head"><h2>Co o nás říkají</h2>{_carousel_controls("rev") if len(reviews) > 1 else ""}</div>
    {summary_html}
    <div class="bleed" id="rev">''' + "".join(
        f'<blockquote class="rev"><p>„{e(r["text"])}“</p><footer>{e(r.get("author"))}'
        + (f'<span>{e(r.get("source"))}</span>' if r.get("source") else "") + "</footer></blockquote>"
        for r in reviews) + "</div>" + (
        f'<div class="wrap"><a class="more" href="{e(d["reviews_link"])}" rel="noopener" target="_blank">Všechny recenze na Googlu</a></div>'
        if d.get("reviews_link") else "") + "</section>"

    hours_rows = "".join(f'<tr data-d="{i}"><th>{e(h["day"])}</th><td>{e(h["value"] or "–")}</td></tr>'
                         for i, h in enumerate(d["hours"]))
    hours_js = js([h["value"] for h in d["hours"]])
    person = ""
    if c["person"] or c["photo"]:
        person = ('<div class="person">' + (f'<img src="img/{e(c["photo"])}" alt="{e(c["photo_alt"])}" loading="lazy">' if c["photo"] else "")
                  + f'<div><strong>{e(c["person"])}</strong><span>{e(c["role"])}</span></div></div>')
    map_html = ""
    if c.get("lat"):
        lat, lon = float(c["lat"]), float(c["lon"])
        bbox = f"{lon - 0.006},{lat - 0.0035},{lon + 0.006},{lat + 0.0035}"
        map_html = (f'<iframe class="map" title="Mapa – {e(name)}" loading="lazy" '
                    f'src="https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={lat},{lon}"></iframe>')

    return f'''<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(d["seo"]["title"] or name)}</title>
<meta name="description" content="{e(d["seo"]["description"])}">
<meta property="og:title" content="{e(d["seo"]["title"] or name)}">
<meta property="og:description" content="{e(d["seo"]["description"])}">
{f'<meta property="og:image" content="img/{e(d["hero"]["image"])}">' if d["hero"]["image"] else ""}
{f'<link rel="canonical" href="https://{e(d["domain"])}/">' if d.get("domain") else ""}
<meta name="theme-color" content="{theme["ink"]}">
<link rel="icon" href="logo-icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{font_links}
<script type="application/ld+json">{js(ld)}</script>
<style>
:root {{ --bg:{theme["bg"]}; --surface:{theme["surface"]}; --ink:{theme["ink"]}; --muted:{theme["muted"]};
  --accent:{theme["accent"]}; --accent2:{theme["accent2"]}; --display:"{f["display"]}", Georgia, serif;
  --body:"{f["body"]}", system-ui, sans-serif; --pad:20px; --max:1240px;
  --gut:max(var(--pad), calc((100vw - var(--max)) / 2 + var(--pad)));
  --line:color-mix(in srgb, var(--ink) 14%, transparent); --dots:{dots_dark}; --dots-light:{dots_light}; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; scroll-padding-top:72px; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 var(--body); overflow-x:hidden; -webkit-font-smoothing:antialiased; }}
img {{ display:block; max-width:100%; }}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:3px; }}
h1, h2, h3 {{ font-family:var(--display); font-weight:{dw}; line-height:1.02; margin:0 0 .4em; letter-spacing:-.02em; }}
h2 {{ font-size:clamp(36px, 8vw, 64px); }}
h3 {{ font-size:22px; }}
p {{ margin:0 0 1em; }}
.wrap {{ max-width:var(--max); margin:0 auto; padding:0 var(--pad); }}
.preview-bar {{ position:relative; z-index:50; background:#000; color:#fff; font:13px var(--body); text-align:center; padding:6px 10px; }}
.btn {{ display:inline-flex; align-items:center; justify-content:center; gap:10px; min-height:52px; padding:0 26px; font:700 16px var(--body);
  text-decoration:none; background:var(--accent); color:#fff; border:none; cursor:pointer; transition:background .2s, color .2s; }}
.btn:hover {{ background:var(--ink); }}
.btn.line {{ background:transparent; color:#fff; box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.7); }}
.btn.line:hover {{ background:#fff; color:var(--ink); }}

/* ---------- HERO přes celou šířku s menu ---------- */
.hero {{ position:relative; max-width:2560px; margin:0 auto; min-height:100svh; display:flex; flex-direction:column; color:#fff; overflow:hidden;
  background:linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 40%, var(--ink))); }}
.hero::before {{ content:""; position:absolute; inset:0; background:var(--dots-light); z-index:0; }}
.hero-img {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; z-index:0; }}
.hero::after {{ content:""; position:absolute; inset:0; z-index:1;
  background:linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 28%, rgba(0,0,0,.15) 50%, rgba(0,0,0,.78) 100%),
             linear-gradient(90deg, color-mix(in srgb, var(--ink) 55%, transparent), transparent 70%); }}
.hero > :not(.hero-img):not(.vbtn) {{ position:relative; z-index:2; }}
.vbtn {{ position:absolute; z-index:3; right:var(--gut); bottom:20px; width:40px; height:40px; border:1px solid rgba(255,255,255,.5);
  background:rgba(0,0,0,.35); color:#fff; font-size:12px; cursor:pointer; backdrop-filter:blur(6px); }}
.hero-head {{ padding:18px var(--gut) 0; }}
.hbar {{ display:flex; align-items:center; }}
.brand {{ display:flex; align-items:center; gap:12px; text-decoration:none; font:700 18px/1.1 var(--body); min-width:0; }}
.brand .badge {{ width:42px; height:42px; flex:none; display:grid; place-items:center; background:var(--accent); color:#fff; }}
.hero .brand .badge {{ background:rgba(255,255,255,.14); box-shadow:inset 0 0 0 1px rgba(255,255,255,.35); }}
.hnav {{ display:flex; gap:6px; overflow-x:auto; scrollbar-width:none; margin:16px calc(-1 * var(--gut)) 0; padding:0 var(--gut); }}
.hnav::-webkit-scrollbar {{ display:none; }}
.hnav a {{ flex:none; text-decoration:none; font-weight:600; font-size:14px; padding:9px 14px; border:1px solid rgba(255,255,255,.35);
  background:rgba(255,255,255,.08); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); }}
.hnav a:hover {{ background:#fff; color:var(--ink); }}
.hbar .call {{ display:none; margin-left:auto; }}
.hero-body {{ margin-top:auto; padding:0 var(--gut) 28px; max-width:calc(var(--max) + 2 * var(--gut)); }}
.live {{ display:inline-flex; align-items:center; gap:10px; font-size:14px; font-weight:600; padding:8px 14px; margin-bottom:18px;
  background:rgba(0,0,0,.35); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); }}
.live i {{ width:8px; height:8px; border-radius:50%; background:#c9c9c9; }}
.live.open i {{ background:#3ddc84; box-shadow:0 0 0 0 rgba(61,220,132,.7); animation:pulse 2s infinite; }}
@keyframes pulse {{ 70% {{ box-shadow:0 0 0 10px rgba(61,220,132,0); }} 100% {{ box-shadow:0 0 0 0 rgba(61,220,132,0); }} }}
.hero h1 {{ font-size:clamp(48px, 13vw, 128px); max-width:14ch; margin-bottom:.25em; text-wrap:balance; }}
.hero-sub {{ font-size:clamp(18px, 2.2vw, 22px); max-width:40ch; opacity:.92; }}
.hero .btns {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }}
.facts {{ display:grid; grid-template-columns:1fr; border-top:1px solid rgba(255,255,255,.28); margin-top:28px; }}
.facts a {{ text-decoration:none; padding:12px 0; border-bottom:1px solid rgba(255,255,255,.18); font-weight:600; }}
.facts a:nth-child(3) {{ display:none; }}
.facts small {{ display:block; font-weight:500; font-size:12px; opacity:.7; letter-spacing:.02em; }}

.hero-meta {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }}
.hero-meta .live {{ margin:0; }}
.rchip {{ display:inline-flex; align-items:center; gap:8px; padding:8px 14px; font-size:14px; text-decoration:none; color:#fff;
  background:rgba(0,0,0,.35); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); }}
.rchip b {{ font-weight:700; }}
.rchip span {{ opacity:.85; }}
a.rchip:hover {{ background:rgba(0,0,0,.55); }}
.rsrc {{ display:inline-flex; align-items:center; gap:6px; }}
.blogo {{ display:inline-block; width:auto; vertical-align:middle; }}
.rchip .blogo, .sec-dark .blogo {{ background:#fff; padding:3px 6px; box-sizing:content-box; }}
.stars {{ position:relative; display:inline-block; width:var(--w); height:var(--h); flex:none; }}
.stars svg {{ display:block; }}
.stars .s-bg {{ fill:currentColor; opacity:.3; }}
.stars .s-fg {{ position:absolute; inset:0 auto 0 0; overflow:hidden; }}
.stars .s-fg svg {{ fill:#f5b301; }}
.rsum {{ display:flex; flex-wrap:wrap; gap:0; margin-bottom:32px; border-top:1px solid rgba(255,255,255,.18); border-bottom:1px solid rgba(255,255,255,.18); }}
.rbig {{ display:flex; align-items:center; gap:16px; padding:18px 28px 18px 0; text-decoration:none; color:inherit; }}
.rsum {{ flex-direction:column; }}
.rbig + .rbig {{ border-top:1px solid rgba(255,255,255,.18); }}
.rbig b {{ font:{dw} 56px/1 var(--display); }}
.rbig .rsrc {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:14px; margin-top:6px; }}
.rbig .rsrc span {{ opacity:.75; }}
a.rbig:hover b {{ color:var(--accent2); }}
.socs {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
.soc {{ display:inline-flex; align-items:center; min-height:40px; padding:0 16px; border:1px solid var(--line); text-decoration:none; font-weight:600; font-size:14px; }}
.soc:hover {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.foot .soc {{ border-color:rgba(255,255,255,.25); color:var(--bg); }}
.foot .soc:hover {{ background:var(--bg); color:var(--ink); }}

/* kompaktní lišta po odscrollování */
.bar {{ position:fixed; top:0; left:0; right:0; z-index:40; display:flex; align-items:center; gap:16px; padding:10px var(--gut);
  background:color-mix(in srgb, var(--bg) 90%, transparent); backdrop-filter:blur(14px) saturate(1.3); -webkit-backdrop-filter:blur(14px) saturate(1.3);
  border-bottom:1px solid var(--line); transform:translateY(-110%); transition:transform .3s ease; }}
.bar.show {{ transform:none; }}
.bar nav {{ display:none; gap:22px; margin-left:auto; }}
.bar nav a {{ text-decoration:none; font-weight:600; font-size:15px; }}
.bar nav a:hover {{ color:var(--accent); }}
.bar .btn {{ min-height:42px; padding:0 18px; margin-left:auto; }}

/* ---------- sekce ---------- */
.sec {{ padding:72px 0; }}
.sec-tint {{ background:var(--dots), var(--surface); }}
.sec-dark {{ background:linear-gradient(160deg, var(--ink), color-mix(in srgb, var(--ink) 75%, var(--accent))); color:var(--bg); }}
.sec-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:20px; flex-wrap:wrap; margin-bottom:28px; }}
.sec-head h2 {{ margin:0; }}
.sec-note {{ margin:0; color:var(--muted); }}

/* výhody: pás s přechodem, rovné dělicí linky */
.usps {{ background:linear-gradient(120deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--ink))); color:#fff; position:relative; }}
.usps::before {{ content:""; position:absolute; inset:0; background:var(--dots-light); }}
.usp-grid {{ position:relative; display:grid; grid-template-columns:1fr; }}
.usp {{ padding:26px 0; border-bottom:1px solid rgba(255,255,255,.22); display:grid; grid-template-columns:44px 1fr; gap:4px 16px; align-items:start; }}
.usp:last-child {{ border-bottom:none; }}
.usp-i {{ grid-row:span 2; width:44px; height:44px; display:grid; place-items:center; border:1px solid rgba(255,255,255,.45); }}
.usp h3 {{ font-family:var(--body); font-weight:700; font-size:19px; line-height:1.3; margin:0; }}
.usp p {{ margin:4px 0 0; opacity:.82; font-size:15px; }}

/* o nás */
.about-text p, .about-text li {{ max-width:60ch; font-size:17px; }}
.about-text ul {{ list-style:none; padding:0; margin:0 0 1em; border-top:1px solid var(--line); }}
.about-text li {{ padding:12px 0 12px 30px; border-bottom:1px solid var(--line); position:relative; }}
.about-text li::before {{ content:""; position:absolute; left:0; top:21px; width:14px; height:2px; background:var(--accent); }}
.about-img {{ margin:28px calc(-1 * var(--pad)) 0; aspect-ratio:4/5; overflow:hidden; }}
.about-img img {{ width:100%; height:100%; object-fit:cover; }}

/* nabídka */
.chips {{ position:sticky; top:62px; z-index:5; display:flex; gap:0; overflow-x:auto; scrollbar-width:none; margin:0 calc(-1 * var(--pad)) 24px;
  padding:0 var(--pad); background:var(--surface); border-bottom:1px solid var(--line); }}
.chips::-webkit-scrollbar {{ display:none; }}
.chips a {{ flex:none; text-decoration:none; font-weight:600; padding:14px 16px; border-bottom:2px solid transparent; }}
.chips a:hover, .chips a.on {{ border-color:var(--accent); color:var(--accent); }}
.og {{ margin-bottom:28px; }}
.og h3 {{ font-size:28px; padding-bottom:10px; border-bottom:2px solid var(--ink); }}
.menu {{ list-style:none; margin:0; padding:0; }}
.menu li {{ padding:14px 0; border-bottom:1px solid var(--line); }}
.mrow {{ display:flex; align-items:baseline; gap:10px; }}
.mname {{ font-weight:600; font-size:17px; }}
.dots {{ flex:1; border-bottom:1px dotted color-mix(in srgb, var(--ink) 35%, transparent); transform:translateY(-5px); min-width:16px; }}
.mprice {{ font-weight:700; color:var(--accent); white-space:nowrap; font-variant-numeric:tabular-nums; }}
.mdesc {{ margin:3px 0 0; color:var(--muted); font-size:14px; }}

/* ---------- carousely vyjíždějící doprava ---------- */
.bleed {{ display:flex; gap:14px; overflow-x:auto; scroll-snap-type:x mandatory; scroll-padding-left:var(--gut);
  padding:0 var(--pad) 8px var(--gut); scrollbar-width:none; overscroll-behavior-x:contain; cursor:grab; }}
.bleed::-webkit-scrollbar {{ display:none; }}
.bleed.drag {{ cursor:grabbing; scroll-snap-type:none; }}
.bleed > * {{ flex:none; scroll-snap-align:start; }}
.shot {{ width:min(78vw, 420px); aspect-ratio:4/5; align-self:flex-start; padding:0; border:none; overflow:hidden; cursor:zoom-in; background:var(--surface); }}
.shot img {{ width:100%; height:100%; object-fit:cover; transition:transform .6s cubic-bezier(.2,.7,.2,1); user-select:none; }}
.shot:hover img {{ transform:scale(1.05); }}
.shot.sq {{ aspect-ratio:1/1; }}
.ctrl {{ display:flex; align-items:center; gap:8px; }}
.progress {{ width:120px; height:2px; background:var(--line); margin-right:10px; position:relative; overflow:hidden; }}
.sec-dark .progress {{ background:rgba(255,255,255,.2); }}
.progress span {{ position:absolute; left:0; top:0; bottom:0; width:30%; background:currentColor; transition:transform .15s linear, width .15s; }}
.arr {{ width:46px; height:46px; display:grid; place-items:center; background:transparent; color:inherit; border:1px solid currentColor; cursor:pointer; opacity:.85; }}
.arr:hover {{ background:var(--accent); border-color:var(--accent); color:#fff; opacity:1; }}
.arr:disabled {{ opacity:.25; cursor:default; background:transparent; color:inherit; border-color:currentColor; }}
.rev {{ width:min(84vw, 460px); margin:0; padding:30px 28px; border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.04); display:flex; flex-direction:column; }}
.rev p {{ font-family:var(--display); font-size:clamp(22px, 2.6vw, 28px); line-height:1.3; margin:0 0 24px; }}
.rev footer {{ margin-top:auto; font-weight:700; padding-top:16px; border-top:1px solid rgba(255,255,255,.18); display:flex; justify-content:space-between; gap:10px; }}
.rev footer span {{ opacity:.6; font-weight:500; }}
.more {{ display:inline-block; margin-top:24px; font-weight:700; text-underline-offset:4px; }}
.lightbox {{ border:none; padding:0; width:100vw; height:100dvh; max-width:none; max-height:none; background:#000; }}
.lightbox::backdrop {{ background:#000; }}
.lb-track {{ display:flex; height:100%; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; }}
.lb-track::-webkit-scrollbar {{ display:none; }}
.lb-track figure {{ flex:none; width:100vw; height:100%; margin:0; scroll-snap-align:center; display:flex; flex-direction:column; justify-content:center; }}
.lb-track img {{ max-height:86dvh; margin:0 auto; object-fit:contain; }}
.lb-track figcaption {{ color:#bbb; text-align:center; padding:12px 20px; font-size:14px; }}
.lb-close {{ position:fixed; top:14px; right:14px; width:48px; height:48px; border:1px solid rgba(255,255,255,.4); background:rgba(0,0,0,.4); color:#fff; font-size:26px; cursor:pointer; }}
.video {{ aspect-ratio:16/9; background:#000; }}
.video iframe {{ width:100%; height:100%; border:0; }}

/* ---------- kontakt ---------- */
.contact-sec {{ padding-bottom:0; }}
.contact {{ display:grid; grid-template-columns:1fr; border-top:2px solid var(--ink); }}
.cbox {{ padding:26px 0; border-bottom:1px solid var(--line); }}
.cbox h3 {{ font-family:var(--body); font-weight:700; font-size:13px; letter-spacing:.06em; color:var(--muted); margin-bottom:14px; }}
.person {{ display:flex; align-items:center; gap:16px; margin-bottom:18px; }}
.person img {{ width:84px; height:84px; object-fit:cover; }}
.person span {{ display:block; color:var(--muted); font-size:14px; }}
.big-link {{ display:block; font:{dw} clamp(26px, 6vw, 34px)/1.15 var(--display); text-decoration:none; margin-bottom:6px; overflow-wrap:anywhere; }}
.big-link:hover {{ color:var(--accent); }}
.addr {{ margin:14px 0 0; }}
.addr a {{ font-weight:700; color:var(--accent); }}
.hours {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }}
.hours th, .hours td {{ text-align:left; padding:9px 0; border-bottom:1px solid var(--line); font-weight:400; }}
.hours td {{ text-align:right; }}
.hours tr.now th, .hours tr.now td {{ font-weight:700; color:var(--accent); }}
.note {{ color:var(--muted); font-size:14px; margin:12px 0 0; }}
.map {{ display:block; width:100%; height:320px; border:0; filter:grayscale(.35) contrast(1.05); }}
.contact-sec {{ padding-bottom:56px; }}

footer.foot {{ background:var(--ink); color:color-mix(in srgb, var(--bg) 70%, transparent); padding:0 0 calc(90px + env(safe-area-inset-bottom)); font-size:14px; }}
.foot-in {{ display:grid; gap:24px; padding-top:40px; }}
.foot-links {{ display:flex; flex-direction:column; gap:6px; align-items:flex-start; }}
.foot-links > a {{ color:var(--bg); font-weight:700; text-decoration:none; }}
.foot-links .socs {{ margin-top:10px; }}
.foot-brand {{ display:flex; align-items:center; gap:12px; color:var(--bg); font:{dw} 32px/1.1 var(--display); margin-bottom:18px; }}
.foot-brand .badge {{ width:44px; height:44px; display:grid; place-items:center; background:var(--accent); color:#fff; }}


/* spodní dok (mobil) – objeví se po odscrollování z úvodu */
.dock {{ position:fixed; left:0; right:0; bottom:0; z-index:30; display:grid; grid-template-columns:1.4fr 1fr 1fr;
  background:var(--ink); padding-bottom:env(safe-area-inset-bottom); transform:translateY(110%); transition:transform .3s ease; }}
.dock.show {{ transform:none; }}
.dock a {{ display:flex; align-items:center; justify-content:center; min-height:58px; color:var(--bg); text-decoration:none; font-weight:700; font-size:15px; border-left:1px solid rgba(255,255,255,.12); }}
.dock a:first-child {{ background:var(--accent); color:#fff; border:none; font-size:16px; }}

@media (prefers-reduced-motion: no-preference) {{
  .hero h1, .hero-sub, .hero .btns, .live {{ animation:rise .9s cubic-bezier(.2,.7,.2,1) both; }}
  .hero-sub {{ animation-delay:.08s; }} .hero .btns {{ animation-delay:.16s; }}
  img.hero-img {{ animation:zoom 14s ease-out both; }}
  @keyframes rise {{ from {{ opacity:0; transform:translateY(24px); }} }}
  @keyframes zoom {{ from {{ transform:scale(1.08); }} }}
}}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior:auto; }} .live.open i {{ animation:none; }} }}

/* ---------- desktop ---------- */
@media (min-width: 900px) {{
  :root {{ --pad:40px; }}
  .dock {{ display:none; }}
  .hero {{ min-height:min(100svh, 980px); }}
  .hero-head {{ display:flex; align-items:center; padding-top:26px; }}
  .hnav {{ padding:0; margin:0 0 0 auto; gap:2px; overflow:visible; }}
  .hnav a {{ border:none; background:none; backdrop-filter:none; font-size:15px; padding:10px 14px; position:relative; }}
  .hnav a::after {{ content:""; position:absolute; left:14px; right:14px; bottom:4px; height:1.5px; background:#fff; transform:scaleX(0); transition:transform .25s; transform-origin:left; }}
  .hnav a:hover {{ background:none; color:#fff; }}
  .hnav a:hover::after {{ transform:none; }}
  .hbar .call {{ display:inline-flex; margin-left:12px; min-height:46px; }}
  .hero-body {{ padding-bottom:48px; width:100%; }}
  .facts {{ grid-template-columns:repeat(3, minmax(0, 1fr)); max-width:var(--max); }}
  .facts a {{ border-bottom:none; padding:16px 24px 0 0; }}
  .facts a:nth-child(3) {{ display:block; }}
  .facts a + a {{ padding-left:24px; border-left:1px solid rgba(255,255,255,.22); }}
  .bar nav {{ display:flex; }}
  .rsum {{ flex-direction:row; }}
  .rbig + .rbig {{ border-top:none; padding-left:28px; border-left:1px solid rgba(255,255,255,.18); }}
  .bar .btn {{ margin-left:0; }}
  .sec {{ padding:110px 0; }}
  .usp-grid {{ grid-template-columns:repeat(auto-fit, minmax(0, 1fr)); }}
  .usp {{ border-bottom:none; border-left:1px solid rgba(255,255,255,.22); padding:44px 32px; grid-template-columns:1fr; }}
  .usp:first-child {{ border-left:none; padding-left:0; }}
  .usp-i {{ grid-row:auto; margin-bottom:18px; }}
  .about.has-img {{ display:grid; grid-template-columns:1fr 1fr; gap:80px; align-items:center; }}
  .about-img {{ margin:0; aspect-ratio:4/5; }}
  .chips {{ margin:0 0 36px; padding:0; top:66px; }}
  .menu-cols {{ columns:2; column-gap:80px; }}
  .og {{ break-inside:avoid; }}
  .shot {{ width:400px; }}
  .contact {{ grid-template-columns:1fr 1fr; column-gap:80px; }}
  .cbox {{ border-bottom:none; }}
  .map {{ height:400px; }}
  .contact-sec {{ padding-bottom:96px; }}
  footer.foot {{ padding-bottom:40px; }}
  .foot-in {{ grid-template-columns:1fr auto; align-items:end; padding-top:48px; }}
  .foot-links {{ align-items:flex-end; text-align:right; }}
}}
@media (min-width: 1500px) {{ .shot {{ width:460px; }} }}
{round_css}
</style>
</head>
<body class="{body_cls}">
{preview_banner}
<header class="hero" id="top">
  {hero_bg}
  <div class="hero-head">
    <div class="hbar">
      <a class="brand" href="#top"><span class="badge">{icon_svg(icon, 20)}</span><span>{e(d["logo"]["text"] or name)}</span></a>
    </div>
    <nav class="hnav" aria-label="Menu">{nav_html}</nav>
    {f'<div class="hbar"><a class="btn call" href="tel:{tel}">Zavolat</a></div>' if tel else ""}
  </div>
  <div class="hero-body">
    <div class="hero-meta"><div class="live" id="live"><i></i><span id="live-txt">Otevírací doba</span></div>{hero_ratings}</div>
    <h1>{e(h1_plain or name)}</h1>
    {f"<p class='hero-sub'>{e(d['hero']['subtitle'])}</p>" if d["hero"]["subtitle"] else ""}
    <div class="btns">
      {f'<a class="btn" href="tel:{tel}">Zavolat {e(c["phone"])}</a>' if tel else ""}
      <a class="btn line" href="#kontakt">Kde nás najdete</a>
    </div>
    <div class="facts">{"".join(facts)}</div>
  </div>
</header>

<div class="bar" id="bar">
  <a class="brand" href="#top"><span class="badge">{icon_svg(icon, 18)}</span><span>{e(d["logo"]["text"] or name)}</span></a>
  <nav aria-label="Menu">{nav_html}</nav>
  {f'<a class="btn" href="tel:{tel}">Zavolat</a>' if tel else ""}
</div>

<main>
  {usp_html}
  {about_html}
  {offer_html}
  {gal_html}
  {video_html}
  {rev_html}

  <section id="kontakt" class="sec contact-sec">
    <div class="wrap">
      <div class="sec-head"><h2>Kontakt</h2></div>
      <div class="contact">
        <div class="cbox">
          <h3>Ozvěte se</h3>
          {person}
          {f'<a class="big-link" href="tel:{tel}">{e(c["phone"])}</a>' if tel else ""}
          {f'<a class="big-link" href="mailto:{e(c["email"])}">{e(c["email"])}</a>' if c["email"] else ""}
          <p class="addr">{e(c["address"])} · <a href="{e(maps)}" target="_blank" rel="noopener">Navigovat</a></p>
          {f'<div class="socs">{social_html}</div>' if social_html else ""}
        </div>
        <div class="cbox">
          <h3>Otevírací doba</h3>
          <table class="hours" aria-label="Otevírací doba">{hours_rows}</table>
          {f'<p class="note">{e(d["hours_note"])}</p>' if d.get("hours_note") else ""}
          {f'<p class="note">{e(d["booking_note"])}</p>' if d.get("booking_note") else ""}
        </div>
      </div>
    </div>
  </section>
</main>

<footer class="foot">
  {map_html}
  <div class="wrap foot-in">
    <div>
      <div class="foot-brand"><span class="badge">{icon_svg(icon, 22)}</span>{e(d["logo"]["text"] or name)}</div>
      <p>{e(d["company"]["legal_name"])} · IČO {e(d["company"]["ico"])}<br>{e(d["company"]["address"])}</p>
    </div>
    <div class="foot-links">
      {f'<a href="tel:{tel}">{e(c["phone"])}</a>' if tel else ""}
      <a href="{e(maps)}" target="_blank" rel="noopener">Navigovat</a>
      {f'<div class="socs">{social_html}</div>' if social_html else ""}
    </div>
  </div>
</footer>

<nav class="dock" id="dock" aria-label="Rychlé akce">
  {f'<a href="tel:{tel}">Zavolat</a>' if tel else '<a href="#kontakt">Kontakt</a>'}
  <a href="{e(maps)}" target="_blank" rel="noopener">Trasa</a>
  <a href="#kontakt">Hodiny</a>
</nav>

<script>
(function () {{
  // otevírací doba dnes
  var H = {hours_js};
  var i = (new Date().getDay() + 6) % 7, v = H[i] || "";
  var row = document.querySelector('.hours tr[data-d="' + i + '"]'); if (row) row.className = "now";
  var live = document.getElementById("live"), lt = document.getElementById("live-txt"), ht = document.getElementById("hero-today");
  if (ht) ht.textContent = v || "–";
  if (/zavřeno/i.test(v)) {{ lt.textContent = "Dnes zavřeno"; }}
  else if (v) {{
    var m = v.match(/(\\d{{1,2}})[:.](\\d{{2}})\\s*[–-]\\s*(\\d{{1,2}})[:.](\\d{{2}})/), now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
    var open = m && mins >= (+m[1]) * 60 + (+m[2]) && mins < (+m[3]) * 60 + (+m[4]);
    if (open) {{ live.classList.add("open"); lt.textContent = "Teď otevřeno do " + m[3] + ":" + m[4]; }}
    else lt.textContent = "Dnes " + v;
  }}

  // video v úvodu: tlačítko zastavit/přehrát, při vypnutých animacích jen náhled
  var hv = document.getElementById("hero-video"), vb = document.getElementById("vbtn");
  if (hv && vb) {{
    var setBtn = function () {{ vb.textContent = hv.paused ? "▶" : "❚❚"; vb.setAttribute("aria-label", hv.paused ? "Přehrát video" : "Zastavit video"); }};
    vb.addEventListener("click", function () {{ hv.paused ? hv.play() : hv.pause(); setBtn(); }});
    if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) {{ hv.removeAttribute("autoplay"); hv.pause(); }}
    hv.addEventListener("play", setBtn); hv.addEventListener("pause", setBtn); setBtn();
  }}

  // lišta a dok se objeví po odscrollování z úvodu
  var bar = document.getElementById("bar"), dock = document.getElementById("dock"), hero = document.getElementById("top");
  if ("IntersectionObserver" in window) {{
    new IntersectionObserver(function (es) {{
      var out = !es[0].isIntersecting; bar.classList.toggle("show", out); dock.classList.toggle("show", out);
    }}, {{ rootMargin: "-120px 0px 0px 0px" }}).observe(hero);
  }} else {{ bar.classList.add("show"); dock.classList.add("show"); }}

  // carousely: táhnutí myší, šipky, ukazatel posunu
  document.querySelectorAll(".bleed").forEach(function (el) {{
    var ctrl = document.querySelector('.ctrl[data-for="' + el.id + '"]');
    var bar = ctrl && ctrl.querySelector(".progress span"), prev = ctrl && ctrl.querySelector(".prev"), next = ctrl && ctrl.querySelector(".next");
    function upd() {{
      var max = el.scrollWidth - el.clientWidth, p = max > 0 ? el.scrollLeft / max : 1, w = Math.max(.15, el.clientWidth / el.scrollWidth);
      if (bar) {{ bar.style.width = (w * 100) + "%"; bar.style.transform = "translateX(" + (p * (1 / w - 1) * 100) + "%)"; }}
      if (prev) prev.disabled = el.scrollLeft < 4;
      if (next) next.disabled = el.scrollLeft > max - 4;
      if (ctrl) ctrl.style.visibility = max > 4 ? "visible" : "hidden";
    }}
    function step() {{ var it = el.firstElementChild; return it ? it.getBoundingClientRect().width + 14 : 300; }}
    if (prev) prev.addEventListener("click", function () {{ el.scrollBy({{ left: -step(), behavior: "smooth" }}); }});
    if (next) next.addEventListener("click", function () {{ el.scrollBy({{ left: step(), behavior: "smooth" }}); }});
    el.addEventListener("scroll", upd, {{ passive: true }}); window.addEventListener("resize", upd); upd();
    var down = false, sx = 0, sl = 0, moved = false;
    el.addEventListener("pointerdown", function (ev) {{ if (ev.pointerType !== "mouse") return; down = true; moved = false; sx = ev.clientX; sl = el.scrollLeft; }});
    window.addEventListener("pointermove", function (ev) {{ if (!down) return; var dx = ev.clientX - sx; if (Math.abs(dx) > 5) {{ moved = true; el.classList.add("drag"); }} el.scrollLeft = sl - dx; }});
    window.addEventListener("pointerup", function () {{ if (!down) return; down = false; el.classList.remove("drag"); }});
    el.addEventListener("click", function (ev) {{ if (moved) {{ ev.preventDefault(); ev.stopPropagation(); moved = false; }} }}, true);
  }});

  // aktivní záložka v nabídce
  var chips = document.querySelectorAll(".chips a");
  if (chips.length && "IntersectionObserver" in window) {{
    var io = new IntersectionObserver(function (es) {{
      es.forEach(function (x) {{ if (x.isIntersecting) chips.forEach(function (a) {{ a.classList.toggle("on", a.getAttribute("href") === "#" + x.target.id); }}); }});
    }}, {{ rootMargin: "-40% 0px -55% 0px" }});
    document.querySelectorAll(".og").forEach(function (g) {{ io.observe(g); }});
  }}

  // galerie na celou obrazovku
  var lb = document.querySelector(".lightbox");
  if (lb) {{
    var track = lb.querySelector(".lb-track");
    document.querySelectorAll(".shot").forEach(function (b) {{
      b.addEventListener("click", function () {{ lb.showModal(); track.scrollLeft = track.clientWidth * (+b.dataset.i); }});
    }});
    lb.querySelector(".lb-close").addEventListener("click", function () {{ lb.close(); }});
  }}
}})();
</script>
</body>
</html>'''


def icon_file(d: dict) -> str:
    theme = TYPES[d["type"]]["theme"]
    accent = d["theme"].get("accent") if re.fullmatch(r"#[0-9a-fA-F]{6}", d["theme"].get("accent") or "") else theme["accent"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="32" fill="{accent}"/>'
            f'<g transform="translate(14 14) scale(1.5)" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS.get(d["logo"]["icon"], ICONS["star"])}</g></svg>')


def export_zip(site_id: int, d: dict) -> bytes:
    theme = dict(TYPES[d["type"]]["theme"])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", d["theme"].get("accent") or ""):
        theme["accent"] = d["theme"]["accent"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", render(d))
        z.writestr("logo.svg", logo_svg(d, theme))
        z.writestr("logo-icon.svg", icon_file(d))
        used = {d["hero"]["image"], d["hero"].get("video"), d["contact"]["photo"], *[g.get("file") for g in d["gallery"]]}
        for name in filter(None, used):
            p = image_path(site_id, name)
            if p:
                z.write(p, f"img/{name}")
        for fname in brand_files().values():
            bp = brand_path(fname)
            if bp:
                z.write(bp, f"img/{fname}")
        dom = (d.get("domain") or "").strip()
        z.writestr("robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: https://{dom}/sitemap.xml\n" if dom else ""))
        if dom:
            z.writestr("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                      f'<url><loc>https://{dom}/</loc></url></urlset>\n')
    return buf.getvalue()
