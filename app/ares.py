"""ARES (Ministerstvo financí): DPH, insolvence, kontakty z ROS/NRPZS."""
import asyncio
import json

import httpx

from .config import USER_AGENT

BASE = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"


class AresUnavailable(Exception):
    """ARES neodpovídá – výsledek se nesmí uložit jako „nenalezeno“."""


async def _get(client: httpx.AsyncClient, path: str):
    last = None
    for attempt in range(3):
        try:
            r = await client.get(BASE + path, timeout=15)
        except httpx.HTTPError as e:
            last = e
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 403, 404):
            return None
        last = f"HTTP {r.status_code}"
        await asyncio.sleep(1.5 * (attempt + 1))  # 429 / 5xx
    raise AresUnavailable(f"ARES nedostupný ({last})")


def _first(*vals):
    for v in vals:
        if v:
            return v
    return None


async def fetch(client: httpx.AsyncClient, ico: str) -> dict:
    """Vrátí normalizovaný slovník s tím, co z ARES potřebujeme."""
    out = {"found": False, "dph": False, "insolvence": False, "likvidace": False,
           "phone": None, "email": None, "datova_schranka": None, "www": None}
    base = await _get(client, f"/ekonomicke-subjekty/{ico}")
    if not base:
        return out
    reg = base.get("seznamRegistraci") or {}
    nazev = base.get("obchodniJmeno") or ""
    out.update({
        "found": True,
        "nazev": nazev,
        "dic": base.get("dic"),
        "zanik": base.get("datumZaniku"),
        "dph": "AKTIVNI" in (reg.get("stavZdrojeDph"), reg.get("stavZdrojeSkDph")),
        "insolvence": "AKTIVNI" in (reg.get("stavZdrojeIr"), reg.get("stavZdrojeCeu")),
        "likvidace": "likvidaci" in nazev.lower(),
        "registry": {k.replace("stavZdroje", ""): v for k, v in reg.items() if v == "AKTIVNI"},
    })

    # Kontakty, které subjekt sám zveřejnil v registru osob (nemusí být vyplněné)
    if reg.get("stavZdrojeRos") == "AKTIVNI":
        try:
            ros = await _get(client, f"/ekonomicke-subjekty-ros/{ico}")
        except AresUnavailable:
            ros = None
        for z in (ros or {}).get("zaznamy", [])[:1]:
            k = z.get("kontaktniUdaje") or {}
            out["phone"] = _first(out["phone"], k.get("telefon"))
            out["email"] = _first(out["email"], k.get("email"))
            for ds in z.get("datoveSchranky") or []:
                if ds.get("identifikatorDs"):
                    out["datova_schranka"] = ds["identifikatorDs"]
                    break

    # Zdravotnická zařízení mají v NRPZS i web a e-mail
    if reg.get("stavZdrojeNrpzs") == "AKTIVNI":
        try:
            nr = await _get(client, f"/ekonomicke-subjekty-nrpzs/{ico}")
        except AresUnavailable:
            nr = None
        for z in (nr or {}).get("zaznamy", []):
            k = z.get("kontakty") or {}
            out["www"] = _first(out["www"], k.get("www"))
            out["email"] = _first(out["email"], k.get("email"))
            out["phone"] = _first(out["phone"], k.get("telefon"))
    return out


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept": "application/json"})


def dumps(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False)
