#!/bin/bash
# Arranque do frontend React (Linux/macOS)
set -e
cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
  echo "[INFO] node_modules não encontrado. A instalar..."
  npm install
fi

npm run dev
