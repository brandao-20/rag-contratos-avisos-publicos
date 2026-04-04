#!/bin/bash
# Arranque da API FastAPI (Linux/macOS)
set -e
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
if [ -f ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

if ! $PYTHON -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "[ERRO] FastAPI/Uvicorn não estão instalados."
  echo "[INFO] Corre: pip install -r requirements-api.txt"
  exit 1
fi

$PYTHON -m uvicorn api:app --reload
