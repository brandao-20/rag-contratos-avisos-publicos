"""Descarrega fontes listadas em urls_dr.txt ou no manifesto."""

from __future__ import annotations

from pathlib import Path
import csv
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_docs"
URLS = ROOT / "data" / "manifests" / "urls_dr.txt"
MANIFEST = ROOT / "data" / "manifests" / "sources_manifest.csv"
RAW.mkdir(parents=True, exist_ok=True)

urls: list[str] = []
if URLS.exists():
    urls.extend([line.strip() for line in URLS.read_text(encoding="utf-8").splitlines() if line.strip()])
elif MANIFEST.exists():
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        urls.extend([(row.get("url") or "").strip() for row in reader if (row.get("url") or "").strip()])

session = requests.Session()
session.headers.update({"User-Agent": "public-docs-rag-fetch/1.0"})

for url in urls:
    name = Path(url).name
    out = RAW / name
    if out.exists() and out.stat().st_size > 0:
        print(f"Já existe: {name}")
        continue
    print(f"A descarregar {name} ...")
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        out.write_bytes(resp.content)
    except Exception as exc:
        print(f"Falhou {url}: {exc}")
