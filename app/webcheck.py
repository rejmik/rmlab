"""Vlastní detekce webu: odhad domén z názvu firmy a ověření, zda web patří firmě."""
import asyncio
import re
import socket
import unicodedata

import httpx
from rapidfuzz import fuzz

from .config import USER_AGENT

LEGAL_SUFFIX = re.compile(
    r"[,\s]+(spol\.?\s*s\s*r\.?\s*o\.?|s\.?\s*r\.?\s*o\.?|a\.\s*s\.?|v\.\s*o\.\s*s\.?|k\.\s*s\.?|"
    r"družstvo|z\.\s*s\.?|o\.\s*p\.\s*s\.?|z\.\s*ú\.?|se)(\s|,|$).*$",
    re.IGNORECASE,
)
STOPWORDS = {"a", "s", "spol", "the", "and", "cz", "czech", "v", "na", "pro", "likvidaci", "demo"}
PARKED_MARKERS = [
    "doména je na prodej", "domena je na prodej", "tato doména", "domain is for sale", "buy this domain",
    "parkovaná doména", "parked domain", "this domain may be for sale", "doména byla zaregistrována",
    "webhosting wedos", "stránka ve výstavbě", "page under construction", "coming soon",
]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def clean_name(name: str) -> str:
    name = re.sub(r"\[demo\]", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bv likvidaci\b", "", name, flags=re.IGNORECASE)
    return LEGAL_SUFFIX.sub("", name).strip(" ,-–")


def name_tokens(name: str):
    base = strip_accents(clean_name(name)).lower()
    base = base.replace("&", " a ")
    return [t for t in re.findall(r"[a-z0-9]+", base) if t not in STOPWORDS]


def candidate_domains(name: str):
    cleaned = clean_name(name)
    tokens = name_tokens(name)
    if not tokens:
        return []
    labels = []
    joined = "".join(tokens)
    labels.append(joined)
    if len(tokens) > 1:
        labels.append("-".join(tokens))
    # "Jan Novák - Instalatérství" → instalaterstvi-novak, část za pomlčkou
    parts = re.split(r"\s[-–]\s", cleaned)
    if len(parts) > 1:
        tail = [t for t in re.findall(r"[a-z0-9]+", strip_accents(parts[-1]).lower()) if t not in STOPWORDS]
        head = [t for t in re.findall(r"[a-z0-9]+", strip_accents(parts[0]).lower()) if t not in STOPWORDS]
        if tail:
            labels.append("".join(tail))
            if head:  # instalaterstvi-novak, instalaterstvinovak
                labels.append(f"{tail[0]}-{head[-1]}")
                labels.append(f"{tail[0]}{head[-1]}")
    if len(tokens) >= 2 and len(tokens[0]) >= 4:
        labels.append(tokens[0] + tokens[1])
    seen, domains = set(), []
    for lab in labels:
        lab = lab[:63].strip("-")
        if len(lab) < 3 or lab in seen:
            continue
        seen.add(lab)
        domains.append(f"{lab}.cz")
    if joined and len(joined) >= 4:
        domains += [f"{joined}.com", f"{joined}.eu"]
    return domains[:8]


async def _resolves(domain: str) -> bool:
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(loop.getaddrinfo(domain, 443, type=socket.SOCK_STREAM), timeout=4)
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _page_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


def _has_ico(text: str, ico: str) -> bool:
    digits = re.sub(r"[\s ]", "", text)
    return ico in digits


async def _fetch(client: httpx.AsyncClient, domain: str):
    for scheme in ("https", "http"):
        try:
            r = await client.get(f"{scheme}://{domain}/", timeout=8, follow_redirects=True)
            if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
                return str(r.url), r.text[:400_000]
        except httpx.HTTPError:
            continue
    return None, None


async def check(client: httpx.AsyncClient, ico: str, name: str) -> dict:
    """match: ico (web s IČO firmy), name (web odpovídá názvu), parked, other, none."""
    domains = candidate_domains(name)
    tried, best = [], {"url": None, "match": "none"}
    rank = {"none": 0, "other": 1, "parked": 2, "name": 3, "ico": 4}
    norm_name = " ".join(name_tokens(name))
    for domain in domains:
        if not await _resolves(domain):
            tried.append({"domain": domain, "dns": False})
            continue
        url, html = await _fetch(client, domain)
        if not html:
            tried.append({"domain": domain, "dns": True, "http": False})
            continue
        text = _page_text(html)
        low = strip_accents(text.lower())
        if _has_ico(text, ico):
            match = "ico"
        elif any(strip_accents(m) in low[:20000] for m in PARKED_MARKERS) and len(text) < 6000:
            match = "parked"
        elif norm_name and fuzz.partial_ratio(norm_name, low[:20000]) >= 90:
            match = "name"
        else:
            match = "other"
        tried.append({"domain": domain, "dns": True, "http": True, "match": match})
        if rank[match] > rank[best["match"]]:
            best = {"url": url, "match": match}
        if match == "ico":
            break
    best["tried"] = tried
    return best


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, verify=True)
