#!/usr/bin/env python3
"""Správa RM Lab.

  python manage.py init                      # vytvoří databázi
  python manage.py adduser lukas "Lukáš"     # přidá uživatele (zeptá se na heslo)
  python manage.py passwd lukas              # změní heslo
  python manage.py make-admin lukas          # udělá z uživatele admina (správa týmu v aplikaci)
  python manage.py demo                      # fiktivní firmy kolem Čelákovic na vyzkoušení
  python manage.py download                  # stáhne RES (ČSÚ) a adresní místa RÚIAN (ČÚZK)
  python manage.py import-res data/raw/res_data.csv
  python manage.py import-ruian data/raw/20260930_OB_ADR_csv.zip
  python manage.py update                    # download + oba importy (např. 1× měsíčně z cronu)
"""
import argparse
import getpass
import sys
from pathlib import Path

from app.auth import hash_password
from app.config import BASE_DIR
from app.db import connect, init_db
from app import importers

RAW = BASE_DIR / "data" / "raw"


def _ask_password():
    pw = getpass.getpass("Heslo: ")
    if len(pw) < 8:
        sys.exit("Heslo musí mít aspoň 8 znaků.")
    if pw != getpass.getpass("Heslo znovu: "):
        sys.exit("Hesla se neshodují.")
    return pw


def main():
    p = argparse.ArgumentParser(description="RM Lab – správa")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("adduser"); a.add_argument("username"); a.add_argument("display_name", nargs="?")
    a.add_argument("--password", help="heslo (jinak se zeptá)")
    w = sub.add_parser("passwd"); w.add_argument("username")
    ma = sub.add_parser("make-admin"); ma.add_argument("username")
    d = sub.add_parser("demo"); d.add_argument("--n", type=int, default=400)
    sub.add_parser("download")
    r = sub.add_parser("import-res"); r.add_argument("path", nargs="?", default=str(RAW / "res_data.csv"))
    u = sub.add_parser("import-ruian"); u.add_argument("path", nargs="?")
    sub.add_parser("update")
    args = p.parse_args()

    init_db()
    if args.cmd == "init":
        print("Databáze připravena.")
    elif args.cmd == "adduser":
        pw = args.password or _ask_password()
        with connect() as conn:
            conn.execute("INSERT INTO users(username, display_name, password_hash) VALUES (?,?,?)",
                         (args.username.lower(), args.display_name or args.username, hash_password(pw)))
        print(f"Uživatel {args.username} přidán.")
    elif args.cmd == "passwd":
        pw = _ask_password()
        with connect() as conn:
            n = conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                             (hash_password(pw), args.username.lower())).rowcount
        print("Heslo změněno." if n else "Uživatel neexistuje.")
    elif args.cmd == "make-admin":
        with connect() as conn:
            n = conn.execute("UPDATE users SET is_admin=1, active=1 WHERE username=?", (args.username.lower(),)).rowcount
        print("Hotovo." if n else "Uživatel neexistuje.")
    elif args.cmd == "demo":
        importers.load_demo(args.n)
    elif args.cmd == "download":
        importers.download_res(RAW)
        importers.download_ruian(RAW)
    elif args.cmd == "import-res":
        importers.import_res(Path(args.path))
    elif args.cmd == "import-ruian":
        path = Path(args.path) if args.path else max(RAW.glob("*_OB_ADR_csv.zip"), default=None)
        if not path:
            sys.exit("Chybí soubor RÚIAN – spusťte nejdřív: python manage.py download")
        importers.import_ruian(path)
    elif args.cmd == "update":
        res = importers.download_res(RAW)
        ruian = importers.download_ruian(RAW)
        importers.import_res(res)
        importers.import_ruian(ruian)


if __name__ == "__main__":
    main()
