"""Script opcional para descarregar automaticamente as fontes listadas.

Lê `data/manifests/sources_manifest.csv` e tenta descarregar cada URL para
`data/raw_docs/`. Alguns sites oficiais bloqueiam downloads automatizados;
nesses casos o script informa o utilizador para proceder manualmente.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PublicDocsRAG/1.0; +local-demo)",
}


def download_file(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=30, headers=HEADERS)
        if r.status_code != 200:
            return False
        dest.write_bytes(r.content)
        return True
    except Exception:
        return False


def main() -> None:
    manifest_path = PROJECT_ROOT / "data" / "manifests" / "sources_manifest.csv"
    if not manifest_path.exists():
        print(f"Manifesto não encontrado: {manifest_path}")
        return
    config.ensure_directories()
    with manifest_path.open(encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            filename = (row.get("filename") or Path(url).name).strip()
            dest = PROJECT_ROOT / config.RAW_DOCS_DIR / filename
            if dest.exists() and dest.stat().st_size > 0:
                print(f"{filename} já existe; a saltar.")
                continue
            print(f"A descarregar {url}…")
            success = download_file(url, dest)
            if not success:
                print(
                    f"Falhou download de {url}. Faça download manualmente e coloque em {dest}."
                )


if __name__ == "__main__":
    main()
