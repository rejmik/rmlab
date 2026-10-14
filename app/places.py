"""Google Places API (New) – hledání a živé detaily.

Podle podmínek Google se trvale ukládá jen place_id. Ostatní údaje (telefon, web,
hodnocení) držíme jen v paměti procesu s krátkou platností a dotahujeme je živě.
"""
import time
from typing import Optional

import httpx
from rapidfuzz import fuzz

from .config import GOOGLE_API_KEY
from .geo import haversine_km
from .webcheck import name_tokens

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{pid}"
FIELDS = ["id", "displayName", "formattedAddress", "location", "websiteUri", "nationalPhoneNumber",
          "internationalPhoneNumber", "businessStatus", "rating", "userRatingCount", "googleMapsUri",
          "regularOpeningHours.weekdayDescriptions"]

_TTL = 6 * 3600
_cache = {}  # place_id -> (ts, data)


def enabled() -> bool:
    return bool(GOOGLE_API_KEY)


def _remember(place: dict) -> dict:
    data = {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text"),
        "address": place.get("formattedAddress"),
        "website": place.get("websiteUri"),
        "phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
        "status": place.get("businessStatus"),
        "rating": place.get("rating"),
        "reviews": place.get("userRatingCount") or 0,
        "maps_url": place.get("googleMapsUri"),
        "hours": (place.get("regularOpeningHours") or {}).get("weekdayDescriptions"),
        "lat": (place.get("location") or {}).get("latitude"),
        "lon": (place.get("location") or {}).get("longitude"),
    }
    if data["place_id"]:
        _cache[data["place_id"]] = (time.time(), data)
    return data


def cached(place_id: str) -> Optional[dict]:
    hit = _cache.get(place_id)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    return None


def _headers(fields):
    return {"X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": ",".join(fields), "Content-Type": "application/json"}


async def find_match(client: httpx.AsyncClient, name: str, obec: str, lat, lon):
    """Najde podnik na Google a vrátí (data, confidence) nebo (None, 0)."""
    from .webcheck import clean_name
    body = {"textQuery": f"{clean_name(name)} {obec or ''}".strip(), "languageCode": "cs",
            "regionCode": "CZ", "pageSize": 5}
    if lat is not None:
        body["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 3000.0}}
    r = await client.post(SEARCH_URL, json=body, headers=_headers(["places." + f for f in FIELDS]), timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Google Places {r.status_code}: {r.text[:300]}")
    firm = " ".join(name_tokens(name))
    best, best_conf = None, 0.0
    for p in r.json().get("places", []):
        pname = " ".join(name_tokens((p.get("displayName") or {}).get("text", "")))
        sim = fuzz.token_set_ratio(firm, pname) / 100
        loc = p.get("location") or {}
        if lat is not None and loc:
            d = haversine_km(lat, lon, loc["latitude"], loc["longitude"])
            geo = 1.0 if d < 0.3 else 0.9 if d < 1.5 else 0.7 if d < 5 else 0.3
            if d < 0.06 and sim >= 0.45:  # stejná adresa, jiný (obchodní) název
                sim = max(sim, 0.75)
        else:
            geo = 0.7
        conf = sim * geo
        if conf > best_conf:
            best, best_conf = p, conf
    if best is None or best_conf < 0.6:
        return None, best_conf
    return _remember(best), round(best_conf, 2)


async def details(client: httpx.AsyncClient, place_id: str) -> Optional[dict]:
    hit = cached(place_id)
    if hit:
        return hit
    r = await client.get(DETAILS_URL.format(pid=place_id), headers=_headers(FIELDS), params={"languageCode": "cs"}, timeout=15)
    if r.status_code != 200:
        return None
    return _remember(r.json())


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()
