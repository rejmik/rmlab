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

# --- provoz na veřejném serveru (Railway apod.) ---
# 1 = přihlašovací cookie jen přes HTTPS (na serveru zapnout, lokálně nechat 0)
HTTPS_ONLY = os.environ.get("LF_HTTPS", "0") == "1"
# Kam přesměrovat „/“ (např. /nase-crm/ na doméně CRM). Prázdné = na „/“ je veřejný web.
ROOT_REDIRECT = os.environ.get("LF_ROOT_REDIRECT", "")
# První admin – založí se při startu, pokud v databázi ještě nikdo není
ADMIN_USER = os.environ.get("LF_ADMIN_USER", "")
_raw_pw = os.environ.get("LF_ADMIN_PASSWORD", "")
# mezery a uvozovky kolem hesla vzniknou snadno při kopírování do nastavení serveru – odstraníme je
ADMIN_PASSWORD = _raw_pw.strip().strip('"').strip("'")
ADMIN_NAME = os.environ.get("LF_ADMIN_NAME", "")
# 1 = při startu nastavit adminovi heslo z LF_ADMIN_PASSWORD (když heslo nefunguje); pak proměnnou smazat
ADMIN_RESET = os.environ.get("LF_ADMIN_RESET", "0") == "1"
# 1 = když databáze nemá reálná data firem, stáhne a naimportuje RES + RÚIAN na pozadí
AUTO_IMPORT = os.environ.get("LF_AUTO_IMPORT", "0") == "1"
# Omezení pokusů o přihlášení: max. počet neúspěchů z jedné IP za 15 minut
LOGIN_MAX_FAILS = int(os.environ.get("LF_LOGIN_MAX_FAILS", "10"))

# --- poptávky z webu: upozornění e-mailem (nepovinné) ---
# Komu poslat upozornění na novou poptávku (víc adres oddělte čárkou)
NOTIFY_TO = os.environ.get("LF_NOTIFY_TO", "")
# Varianta A – Resend (https://resend.com), funguje i tam, kde hosting blokuje SMTP
RESEND_API_KEY = os.environ.get("LF_RESEND_API_KEY", "")
# Varianta B – vlastní SMTP server
SMTP_HOST = os.environ.get("LF_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("LF_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("LF_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("LF_SMTP_PASSWORD", "")
# Odesílatel; u Resend bez ověřené domény jde jen onboarding@resend.dev (a jen na e-mail účtu Resend)
MAIL_FROM = os.environ.get("LF_MAIL_FROM", "RM Lab <onboarding@resend.dev>")
# Adresa CRM do odkazu v e-mailu
PUBLIC_URL = os.environ.get("LF_PUBLIC_URL", "https://rmlab.rejmon.net")
