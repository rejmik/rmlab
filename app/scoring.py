"""Skóre: pravděpodobnost, že firma nemá web, a „živost“ (není mrtvá schránka).

Model je záměrně jednoduchý a čitelný: sčítají se váhy v log-odds a každý signál
se vypíše jako důvod. Váhy upravte podle toho, co se osvědčí v praxi.
"""
import datetime as dt
import math
from urllib.parse import urlparse

from .config import MASS_ADDRESS_THRESHOLD
from .refdata import DEFAULT_PRIOR, FO_FORMS, NACE_DIVISIONS, katpo_rank, nace_division

SOCIAL_HOSTS = ("facebook.com", "instagram.com", "fb.com", "linktr.ee", "booking.com", "firmy.cz",
                "google.com", "business.site", "wixsite.com", "webnode", "estranky")


def _logit(p):
    p = min(max(p, 0.01), 0.99)
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def _is_social(url: str) -> bool:
    host = (urlparse(url).hostname or url).lower()
    return any(s in host for s in SOCIAL_HOSTS)


def score(firm: dict, ares=None, web=None, google=None, google_checked=False):
    """firm: řádek z tabulky firms. Vrací dict s p_noweb, vitality, priority a důvody."""
    reasons = []

    def add(kind, text, weight):
        reasons.append({"kind": kind, "text": text, "w": round(weight, 2)})

    # ---------------- pravděpodobnost, že nemá web
    div = nace_division(firm.get("nace"))
    prior = NACE_DIVISIONS.get(div, (None, DEFAULT_PRIOR))[1]
    x = _logit(prior)
    add("web", f"obor: výchozí odhad {round(prior * 100)} %", 0)

    forma = firm.get("forma") or ""
    if forma in FO_FORMS:
        x += 0.4; add("web", "OSVČ – web mívají méně často", 0.4)
    elif forma == "121":
        x -= 0.6; add("web", "akciová společnost", -0.6)

    rank = katpo_rank(firm.get("katpo"))
    if rank == 4:
        x -= 0.5; add("web", "10–49 zaměstnanců", -0.5)
    elif rank == 5:
        x -= 1.2; add("web", "50+ zaměstnanců", -1.2)

    if web:
        m = web.get("match")
        if m == "ico":
            x -= 4.0; add("web", f"nalezen web s IČO firmy ({web.get('url')})", -4.0)
        elif m == "name":
            x -= 2.2; add("web", f"nalezen web odpovídající názvu ({web.get('url')})", -2.2)
        elif m == "parked":
            x += 0.4; add("web", "doména existuje, ale je zaparkovaná / ve výstavbě", 0.4)
        elif m == "other":
            x += 0.1; add("web", "odhadnutá doména patří někomu jinému", 0.1)
        else:
            x += 0.6; add("web", "žádná odhadnutá doména neexistuje", 0.6)

    if ares and ares.get("www"):
        x -= 2.5; add("web", f"web uvedený v registru ({ares['www']})", -2.5)

    if google:
        site = google.get("website")
        if site and not _is_social(site):
            x -= 2.5; add("web", f"Google profil má web ({site})", -2.5)
        elif site:
            x += 0.5; add("web", f"Google profil odkazuje jen na sociální síť/katalog ({site})", 0.5)
        else:
            x += 1.3; add("web", "Google profil nemá uvedený web", 1.3)
    elif google_checked:
        x += 0.2; add("web", "na Google Mapách nenalezeno", 0.2)

    p_noweb = _sigmoid(x)

    # ---------------- živost (0–100)
    v = 40.0
    if ares:
        if not ares.get("found"):
            v -= 30; add("vital", "v ARES nenalezeno", -30)
        if ares.get("dph"):
            v += 25; add("vital", "plátce DPH (obrat nad limit pro povinnou registraci)", 25)
        if ares.get("insolvence"):
            v -= 50; add("vital", "záznam v insolvenčním rejstříku / evidenci úpadců", -50)
        if ares.get("likvidace"):
            v -= 60; add("vital", "v likvidaci", -60)

    if google:
        status = google.get("status")
        if status == "CLOSED_PERMANENTLY":
            v -= 60; add("vital", "Google: trvale zavřeno", -60)
        elif status == "OPERATIONAL":
            v += 10; add("vital", "Google: v provozu", 10)
        reviews = google.get("reviews") or 0
        if reviews >= 30:
            v += 15; add("vital", f"{reviews} recenzí na Googlu", 15)
        elif reviews >= 5:
            v += 10; add("vital", f"{reviews} recenzí na Googlu", 10)
        if google.get("hours"):
            v += 5; add("vital", "vyplněná otevírací doba", 5)

    if rank in (2, 3):
        v += 10; add("vital", "má zaměstnance (1–9)", 10)
    elif rank >= 4:
        v += 15; add("vital", "10+ zaměstnanců", 15)
    elif rank == 0:
        v -= 5; add("vital", "počet zaměstnanců neuveden", -5)

    try:
        age_days = (dt.date.today() - dt.date.fromisoformat(firm.get("datum_vzniku") or "")).days
    except ValueError:
        age_days = None
    if age_days is not None:
        if age_days < 365:
            add("vital", "nová firma (méně než rok) – typicky web teprve řeší", 0)
        elif age_days > 3 * 365:
            v += 8; add("vital", "funguje déle než 3 roky", 8)
        else:
            v += 5; add("vital", "funguje 1–3 roky", 5)

    if (firm.get("addr_count") or 1) >= MASS_ADDRESS_THRESHOLD:
        v -= 20; add("vital", f"na adrese sídlí {firm['addr_count']} firem (pravděpodobně virtuální sídlo)", -20)

    vitality = max(0.0, min(100.0, v))
    return {
        "p_noweb": round(p_noweb, 3),
        "vitality": round(vitality, 1),
        "priority": round(p_noweb * vitality, 1),
        "reasons": reasons,
    }
