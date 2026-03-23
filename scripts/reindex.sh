#!/bin/bash
# Script de conveniência para reindexar documentos.
set -e
echo "A reindexar documentos…"
python3 "$(dirname "$0")/ingest.py"
echo "Reindexação concluída."