#!/bin/bash
# Spuštění RM Lab – stačí dvakrát kliknout ve Finderu
cd "$(dirname "$0")"
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Vytvářím virtuální prostředí…"
  python3 -m venv .venv && "$PY" -m pip install -q -r requirements.txt || { echo "Instalace selhala"; read -n1; exit 1; }
fi
PORT=8000
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo "RM Lab: web http://localhost:$PORT  ·  CRM http://localhost:$PORT/nase-crm/  (ukončíte Ctrl+C)"
( sleep 2; open "http://localhost:$PORT/nase-crm/" ) &
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port $PORT --reload --reload-dir app
echo "Server skončil. Stiskněte klávesu…"; read -n1
