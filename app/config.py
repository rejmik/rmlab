"""Konfigurace z proměnných prostředí (nebo souboru .env)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

DB_PATH = Path(os.environ.get("LF_DB_PATH", BASE_DIR / "data" / "leadfinder.sqlite"))
SECRET_KEY = os.environ.get("LF_SECRET_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

# Rezervace leadu (dní) – po tu dobu ho ostatní vidí jako obsazený
CLAIM_DAYS = int(os.environ.get("LF_CLAIM_DAYS", "7"))
# Kolik firem maximálně obohatit jedním kliknutím
ENRICH_MAX = int(os.environ.get("LF_ENRICH_MAX", "200"))
# Cache veřejných dat (ARES, detekce domén) – dní
CACHE_DAYS = int(os.environ.get("LF_CACHE_DAYS", "30"))
# Paralelismus
ARES_CONCURRENCY = int(os.environ.get("LF_ARES_CONCURRENCY", "4"))
WEB_CONCURRENCY = int(os.environ.get("LF_WEB_CONCURRENCY", "16"))
GOOGLE_CONCURRENCY = int(os.environ.get("LF_GOOGLE_CONCURRENCY", "4"))
# Adresa s tolika a více firmami = pravděpodobně virtuální sídlo
MASS_ADDRESS_THRESHOLD = int(os.environ.get("LF_MASS_ADDRESS", "15"))

USER_AGENT = "RMLab/0.1 (internal tool)"  # HTTP hlavičky musí být ASCII
