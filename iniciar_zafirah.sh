#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
else
  . .venv/bin/activate
fi
python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
