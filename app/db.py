"""SQLite: schéma a připojení."""
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;

-- Firmy z RES (ČSÚ), jen aktivní a podnikatelské formy
CREATE TABLE IF NOT EXISTS firms (
    ico          TEXT PRIMARY KEY,
    rid          INTEGER UNIQUE NOT NULL,      -- číselné IČO pro R-tree
    nazev        TEXT NOT NULL,
    forma        TEXT,
    katpo        TEXT,
    nace         TEXT,
    datum_vzniku TEXT,
    kodadm       INTEGER,
    adresa       TEXT,
    obec         TEXT,
    psc          TEXT,
    lat          REAL,
    lon          REAL,
    addr_count   INTEGER DEFAULT 1             -- kolik firem sídlí na stejné adrese
);
CREATE INDEX IF NOT EXISTS ix_firms_kodadm ON firms(kodadm);
CREATE INDEX IF NOT EXISTS ix_firms_obec ON firms(obec);

CREATE VIRTUAL TABLE IF NOT EXISTS firm_geo USING rtree(
    id, min_lat, max_lat, min_lon, max_lon
);

-- Poptávky z formuláře na veřejném webu
CREATE TABLE IF NOT EXISTS inquiries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name       TEXT NOT NULL,
    company    TEXT NOT NULL,
    contact    TEXT NOT NULL,
    need       TEXT,
    message    TEXT,
    ip         TEXT,
    status     TEXT NOT NULL DEFAULT 'new',     -- new | done
    handled_by INTEGER,
    handled_at TEXT,
    note       TEXT,
    assigned_to INTEGER
);

-- Malá kopie polí potřebných pro filtrování při hledání (vejde se do paměti).
-- Velká tabulka firms se pak čte jen pro firmy, které projdou filtrem.
CREATE TABLE IF NOT EXISTS firm_mini (
    rid   INTEGER PRIMARY KEY,
    lat   REAL,
    lon   REAL,
    forma TEXT,
    nace  TEXT,
    katpo TEXT
);

-- Souřadnice adresních míst RÚIAN (jen ta, na kterých sídlí nějaká firma)
CREATE TABLE IF NOT EXISTS adm (
    kod INTEGER PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL
);

-- Cache veřejných dat z ARES (smí se ukládat)
CREATE TABLE IF NOT EXISTS ares_cache (
    ico        TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    data       TEXT NOT NULL
);

-- Výsledek vlastní detekce webu (kandidátní domény)
CREATE TABLE IF NOT EXISTS web_cache (
    ico        TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL,
    url        TEXT,
    match      TEXT NOT NULL,                   -- ico | name | parked | none
    detail     TEXT
);

-- Google: ukládáme JEN place_id (povoleno podmínkami), obsah se tahá živě
CREATE TABLE IF NOT EXISTS google_link (
    ico        TEXT PRIMARY KEY,
    place_id   TEXT,                            -- NULL = na Googlu nenalezeno
    matched_at TEXT NOT NULL,
    confidence REAL
);

-- Spočtené skóre (naše vlastní čísla)
CREATE TABLE IF NOT EXISTS scores (
    ico         TEXT PRIMARY KEY,
    p_noweb     REAL NOT NULL,
    vitality    REAL NOT NULL,
    priority    REAL NOT NULL,
    enriched    INTEGER NOT NULL DEFAULT 0,
    computed_at TEXT NOT NULL
);

-- Mini CRM
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leads (
    ico           TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'new',
    owner_id      INTEGER REFERENCES users(id),
    claimed_until TEXT,
    next_action   TEXT,
    contact_note  TEXT,                         -- kontakty získané obchodníkem
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_leads_owner ON leads(owner_id);

CREATE TABLE IF NOT EXISTS activities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ico         TEXT NOT NULL,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    ts          TEXT NOT NULL,
    channel     TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS ix_act_ico ON activities(ico);

-- Obce pro vyhledávání středu okruhu (počítá se při importu)
CREATE TABLE IF NOT EXISTS obce (
    name    TEXT PRIMARY KEY,
    name_ascii TEXT,
    lat     REAL,
    lon     REAL,
    n       INTEGER
);

-- Produkty / ceník (spravuje admin)
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    includes    TEXT,                           -- co je v ceně, jedna položka na řádek
    base_price  INTEGER NOT NULL DEFAULT 0,     -- jednorázově, Kč
    monthly_fee INTEGER NOT NULL DEFAULT 0,     -- měsíčně, Kč
    active      INTEGER NOT NULL DEFAULT 1,
    sort        INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT
);

-- Weby připravované pro klienty
CREATE TABLE IF NOT EXISTS sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ico         TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft | review | approved | published
    token       TEXT UNIQUE NOT NULL,           -- odkaz na náhled
    data        TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id),
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sites_ico ON sites(ico);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if "active" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    icols = {r["name"] for r in conn.execute("PRAGMA table_info(inquiries)")}
    if icols and "assigned_to" not in icols:
        conn.execute("ALTER TABLE inquiries ADD COLUMN assigned_to INTEGER")
    # Když ještě nikdo není admin, stane se jím první založený uživatel
    if not conn.execute("SELECT 1 FROM users WHERE is_admin=1 AND active=1").fetchone():
        conn.execute("UPDATE users SET is_admin=1 WHERE id=(SELECT MIN(id) FROM users WHERE active=1)")


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def rebuild_firm_mini(conn: sqlite3.Connection) -> int:
    """Přestaví malou tabulku pro rychlé hledání (po importu nebo při prvním startu)."""
    conn.execute("DELETE FROM firm_mini")
    conn.execute("INSERT INTO firm_mini SELECT rid, lat, lon, forma, nace, katpo FROM firms WHERE lat IS NOT NULL")
    n = conn.execute("SELECT COUNT(*) FROM firm_mini").fetchone()[0]
    set_meta(conn, "firm_mini_ok", "1")
    conn.commit()
    return n
