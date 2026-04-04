#!/bin/bash
# Reindexação de documentos
set -e
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
if [ -f ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

echo "A reindexar documentos…"
$PYTHON scripts/ingest.py
echo "Reindexação concluída."
