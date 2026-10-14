"""Import otevřených dat: RES (ČSÚ) a adresní místa RÚIAN (ČÚZK)."""
import csv
import datetime as dt
import io
import random
import sys
import zipfile
from pathlib import Path

from .db import connect, init_db, set_meta
from .geo import sjtsk_batch_to_wgs84
from .refdata import ALL_BUSINESS_FORMS

RES_URL = "https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv"
RUIAN_URL_TMPL = "https://vdp.cuzk.gov.cz/vymenny_format/csv/{date}_OB_ADR_csv.zip"

csv.field_size_limit(sys.maxsize)


def _log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- stažení

def _download(url: str, dest: Path, gzip: bool = False) -> None:
    import httpx
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Accept-Encoding": "gzip"} if gzip else {}
    _log(f"Stahuji {url}")
    with httpx.stream("GET", url, headers=headers, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            # iter_bytes() rozbalí gzip transportní kompresi
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                total += len(chunk)
                if total % (50 << 20) < (1 << 20):
                    _log(f"  … {total >> 20} MB")
    _log(f"Hotovo: {dest} ({total >> 20} MB)")


def download_res(raw_dir: Path) -> Path:
    dest = raw_dir / "res_data.csv"
    _download(RES_URL, dest, gzip=True)
    return dest


def download_ruian(raw_dir: Path) -> Path:
    """Soubor vzniká 1. den v měsíci s daty k poslednímu dni předchozího měsíce."""
    import httpx
    today = dt.date.today()
    last = today.replace(day=1) - dt.timedelta(days=1)
    for _ in range(3):
        url = RUIAN_URL_TMPL.format(date=last.strftime("%Y%m%d"))
        try:
            dest = raw_dir / f"{last:%Y%m%d}_OB_ADR_csv.zip"
            _download(url, dest)
            return dest
        except httpx.HTTPStatusError:
            _log(f"  {url} nenalezeno, zkouším předchozí měsíc")
            last = last.replace(day=1) - dt.timedelta(days=1)
    raise SystemExit("Soubor RÚIAN se nepodařilo stáhnout – stáhněte ho ručně z nahlizenidokn.cuzk.cz/StahniAdresniMistaRUIAN.aspx")


# ---------------------------------------------------------------- RES

def _format_address(row) -> str:
    if not row.get("KODADM"):
        return (row.get("TEXTADR") or "").strip()
    ulice = row.get("ULICE_TEXT") or row.get("COBCE_TEXT") or row.get("OBEC_TEXT") or ""
    cislo = row.get("CDOM") or ""
    if row.get("TYPCDOM") == "2" and cislo:  # číslo evidenční
        cislo = "č.ev. " + cislo
    if row.get("COR"):
        cislo = f"{cislo}/{row['COR']}" if cislo else row["COR"]
    parts = [f"{ulice} {cislo}".strip()]
    if row.get("COBCE_TEXT") and row.get("COBCE_TEXT") != row.get("OBEC_TEXT") and row.get("ULICE_TEXT"):
        parts.append(row["COBCE_TEXT"])
    psc = row.get("PSC") or ""
    if len(psc) == 5:
        psc = f"{psc[:3]} {psc[3:]}"
    parts.append(f"{psc} {row.get('OBEC_TEXT') or ''}".strip())
    return ", ".join(p for p in parts if p)


def import_res(path: Path) -> None:
    """Načte aktivní podnikatelské subjekty z res_data.csv."""
    init_db()
    conn = connect()
    _log(f"Import RES z {path}")
    conn.execute("DELETE FROM firms")
    conn.execute("DELETE FROM firm_geo")
    kept = skipped = no_adm = 0
    batch = []
    sql = """INSERT OR REPLACE INTO firms
             (ico, rid, nazev, forma, katpo, nace, datum_vzniku, kodadm, adresa, obec, psc)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)"""
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("DDATZAN") or row.get("FORMA") not in ALL_BUSINESS_FORMS:
                skipped += 1
                continue
            ico = (row.get("ICO") or "").strip().zfill(8)
            if not ico.isdigit():
                skipped += 1
                continue
            kodadm = row.get("KODADM") or None
            if not kodadm:
                no_adm += 1
            batch.append((
                ico, int(ico), (row.get("FIRMA") or "").strip(), row.get("FORMA"), row.get("KATPO"),
                row.get("NACE") or row.get("NACE2025"), row.get("DDATVZN"),
                int(kodadm) if kodadm else None, _format_address(row),
                row.get("OBEC_TEXT"), row.get("PSC"),
            ))
            kept += 1
            if len(batch) >= 20000:
                conn.executemany(sql, batch)
                batch.clear()
                _log(f"  … {kept:,} firem")
    if batch:
        conn.executemany(sql, batch)
    _log("Počítám firmy na stejné adrese (virtuální sídla)…")
    conn.execute("DROP TABLE IF EXISTS _addr_counts")
    conn.execute("CREATE TEMP TABLE _addr_counts AS SELECT kodadm, COUNT(*) n FROM firms WHERE kodadm IS NOT NULL GROUP BY kodadm")
    conn.execute("CREATE INDEX _ix_ac ON _addr_counts(kodadm)")
    conn.execute("UPDATE firms SET addr_count = (SELECT n FROM _addr_counts a WHERE a.kodadm = firms.kodadm) WHERE kodadm IS NOT NULL")
    set_meta(conn, "res_imported_at", dt.datetime.now().isoformat(timespec="seconds"))
    set_meta(conn, "res_count", str(kept))
    set_meta(conn, "demo", "0")
    conn.commit()
    _log(f"RES hotovo: {kept:,} aktivních podnikatelů, {no_adm:,} bez kódu adresy, {skipped:,} přeskočeno")
    # pokud už máme souřadnice z dřívějška, rovnou je připojíme
    _attach_coords(conn)
    conn.close()


# ---------------------------------------------------------------- RÚIAN

def _find_col(header, *needles):
    for i, h in enumerate(header):
        hl = h.strip().lower()
        if all(n in hl for n in needles):
            return i
    return None


def _iter_ruian_csv(zf: zipfile.ZipFile):
    for name in zf.namelist():
        if not name.lower().endswith(".csv"):
            continue
        raw = zf.read(name)
        for enc in ("cp1250", "utf-8"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        reader = csv.reader(io.StringIO(text), delimiter=";")
        header = next(reader, None)
        if not header:
            continue
        i_kod = _find_col(header, "kód adm")
        if i_kod is None:
            i_kod = _find_col(header, "kod adm")
        i_y = _find_col(header, "souřadnice y")
        i_x = _find_col(header, "souřadnice x")
        if i_kod is None or i_y is None or i_x is None:
            continue
        for row in reader:
            try:
                yield int(row[i_kod]), float(row[i_y].replace(",", ".")), float(row[i_x].replace(",", "."))
            except (ValueError, IndexError):
                continue


def import_ruian(path: Path) -> None:
    init_db()
    conn = connect()
    needed = {r[0] for r in conn.execute("SELECT DISTINCT kodadm FROM firms WHERE kodadm IS NOT NULL")}
    _log(f"Import RÚIAN z {path} – potřebuji souřadnice pro {len(needed):,} adres")
    if not needed:
        _log("Nejdřív importujte RES (python manage.py import-res).")
    conn.execute("DELETE FROM adm")
    found = 0
    buf_k, buf_y, buf_x = [], [], []

    def flush():
        nonlocal found
        if not buf_k:
            return
        lats, lons = sjtsk_batch_to_wgs84(buf_y, buf_x)
        conn.executemany("INSERT OR REPLACE INTO adm(kod, lat, lon) VALUES(?,?,?)", zip(buf_k, lats, lons))
        found += len(buf_k)
        buf_k.clear(); buf_y.clear(); buf_x.clear()

    with zipfile.ZipFile(path) as zf:
        for kod, y, x in _iter_ruian_csv(zf):
            if needed and kod not in needed:
                continue
            buf_k.append(kod); buf_y.append(y); buf_x.append(x)
            if len(buf_k) >= 50000:
                flush()
                _log(f"  … {found:,} adres")
    flush()
    set_meta(conn, "ruian_imported_at", dt.datetime.now().isoformat(timespec="seconds"))
    conn.commit()
    _log(f"RÚIAN hotovo: {found:,} adresních míst se souřadnicemi")
    _attach_coords(conn)
    conn.close()


def _attach_coords(conn) -> None:
    if not conn.execute("SELECT 1 FROM adm LIMIT 1").fetchone():
        return
    _log("Připojuji souřadnice k firmám a stavím prostorový index…")
    conn.execute("""UPDATE firms SET lat = (SELECT lat FROM adm WHERE adm.kod = firms.kodadm),
                                     lon = (SELECT lon FROM adm WHERE adm.kod = firms.kodadm)
                    WHERE kodadm IS NOT NULL""")
    conn.execute("DELETE FROM firm_geo")
    conn.execute("INSERT INTO firm_geo SELECT rid, lat, lat, lon, lon FROM firms WHERE lat IS NOT NULL")
    n = conn.execute("SELECT COUNT(*) FROM firm_geo").fetchone()[0]
    build_obce(conn)
    conn.commit()
    _log(f"Index hotov: {n:,} firem s polohou")


def build_obce(conn) -> None:
    from .webcheck import strip_accents
    conn.execute("DELETE FROM obce")
    rows = conn.execute("""SELECT obec, AVG(lat) lat, AVG(lon) lon, COUNT(*) n FROM firms
                           WHERE obec IS NOT NULL AND lat IS NOT NULL GROUP BY obec""").fetchall()
    conn.executemany("INSERT OR REPLACE INTO obce VALUES (?,?,?,?,?)",
                     [(r["obec"], strip_accents(r["obec"]).lower(), r["lat"], r["lon"], r["n"]) for r in rows])


# ---------------------------------------------------------------- demo data

DEMO_TRADES = [
    ("43", "Instalatérství"), ("43", "Elektroinstalace"), ("43", "Malířství a natěračství"), ("16", "Truhlářství"),
    ("45", "Autoservis"), ("96", "Kadeřnictví"), ("96", "Kosmetický salon"), ("56", "Hospoda"),
    ("56", "Bistro"), ("81", "Zahradnické služby"), ("41", "Stavby"), ("49", "Autodoprava"),
    ("25", "Zámečnictví"), ("95", "Opravy obuvi"), ("47", "Květinářství"), ("62", "Software"),
    ("10", "Pekařství"), ("86", "Fyzioterapie"), ("93", "Fitness"), ("33", "Servis kotlů"),
]
DEMO_SURNAMES = ["Novák", "Svoboda", "Dvořák", "Černý", "Procházka", "Kučera", "Veselý", "Horák",
                 "Němec", "Marek", "Pokorný", "Král", "Růžička", "Beneš", "Fiala", "Sedláček"]
DEMO_TOWNS = [("Čelákovice", 50.1604, 14.7501, "250 88"), ("Brandýs nad Labem", 50.1872, 14.6633, "250 01"),
              ("Lysá nad Labem", 50.2014, 14.8328, "289 22"), ("Úvaly", 50.0740, 14.7309, "250 82"),
              ("Mochov", 50.1415, 14.7953, "250 87"), ("Přerov nad Labem", 50.1598, 14.8247, "289 16"),
              ("Zeleneč", 50.1334, 14.6602, "250 91"), ("Nehvizdy", 50.1307, 14.7299, "250 81")]


def load_demo(n: int = 400, seed: int = 42) -> None:
    """Vygeneruje FIKTIVNÍ firmy kolem Čelákovic, aby šlo aplikaci vyzkoušet bez importu."""
    init_db()
    rnd = random.Random(seed)
    conn = connect()
    conn.execute("DELETE FROM firms"); conn.execute("DELETE FROM firm_geo")
    rows = []
    for i in range(n):
        nace, trade = rnd.choice(DEMO_TRADES)
        surname = rnd.choice(DEMO_SURNAMES)
        town, lat0, lon0, psc = rnd.choice(DEMO_TOWNS)
        is_fo = rnd.random() < 0.6
        forma = "101" if is_fo else rnd.choice(["112", "112", "112", "121"])
        nazev = f"[DEMO] {trade} {surname}" + ("" if is_fo else " s.r.o.")
        ico = f"9{i:07d}"  # fiktivní IČO, neexistují
        mass = rnd.random() < 0.06
        kodadm = 900000000 + (0 if mass else i)
        lat = lat0 + rnd.uniform(-0.012, 0.012)
        lon = lon0 + rnd.uniform(-0.018, 0.018)
        katpo = rnd.choice(["110", "110", "120", "120", "130", "210", "000"])
        vznik = (dt.date.today() - dt.timedelta(days=rnd.randint(60, 9000))).isoformat()
        street = rnd.choice(["Husova", "Palackého", "Nádražní", "Komenského", "Masarykova", "Zahradní"])
        rows.append((ico, int(ico), nazev, forma, katpo, nace + "000", vznik, kodadm,
                     f"{street} {rnd.randint(1, 1500)}, {psc} {town}", town, psc.replace(" ", ""), lat, lon))
    conn.executemany("""INSERT INTO firms (ico, rid, nazev, forma, katpo, nace, datum_vzniku, kodadm, adresa, obec, psc, lat, lon)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.execute("UPDATE firms SET addr_count = (SELECT COUNT(*) FROM firms f2 WHERE f2.kodadm = firms.kodadm)")
    conn.execute("INSERT INTO firm_geo SELECT rid, lat, lat, lon, lon FROM firms WHERE lat IS NOT NULL")
    build_obce(conn)
    set_meta(conn, "demo", "1")
    set_meta(conn, "res_imported_at", "DEMO")
    conn.commit(); conn.close()
    _log(f"Vygenerováno {n} fiktivních firem kolem Čelákovic (IČO 9xxxxxxx).")
