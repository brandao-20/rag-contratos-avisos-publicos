"""Reconstrói sources_manifest.csv a partir de urls_dr.txt e ficheiros locais."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_docs"
URLS = ROOT / "data" / "manifests" / "urls_dr.txt"
OUT = ROOT / "data" / "manifests" / "sources_manifest.csv"

mapping = {}
if URLS.exists():
    for line in URLS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        mapping[Path(line).name] = line

rows = []
for pdf in sorted(RAW.glob("*.pdf")):
    url = mapping.get(pdf.name)
    doc_type = "Contratos Públicos (cp_hora)" if url and "/cp_hora/" in url else "Diário da República 2.ª série"
    title = pdf.stem.replace("_", " ").strip()
    rows.append({
        "filename": pdf.name,
        "title": title,
        "url": url or "",
        "entity": "Diário da República",
        "date_collected": date.today().isoformat(),
        "document_type": doc_type,
        "notes": "PDF oficial do Diário da República; validar textualidade quando aplicável.",
    })

with OUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["filename", "title", "url", "entity", "date_collected", "document_type", "notes"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Manifesto reconstruído: {OUT}")
