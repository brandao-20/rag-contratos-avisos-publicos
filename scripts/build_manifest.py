"""Reconstrói sources_manifest.csv a partir de urls_dr.txt e do corpus curado."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_docs"
URLS = ROOT / "data" / "manifests" / "urls_dr.txt"
OUT = ROOT / "data" / "manifests" / "sources_manifest.csv"


def parse_title_and_entity(pdf: Path) -> tuple[str, str]:
    try:
        text = " ".join(((PdfReader(str(pdf)).pages[0].extract_text() or "")).split())
    except Exception:
        return pdf.stem, "Diário da República"

    entity_match = re.search(r"Designação da entidade adjudicante:\s*(.+?)\s+NIPC:", text, flags=re.IGNORECASE)
    design_match = re.search(r"Designação do contrato:\s*(.+?)\s+(?:Descrição:|Tipo de Contrato|Tipo de contrato)", text, flags=re.IGNORECASE)

    entity = entity_match.group(1).strip() if entity_match else "Diário da República"
    if entity_match and design_match:
        title = f"{entity} — {design_match.group(1).strip()}"
    elif design_match:
        title = design_match.group(1).strip()
    elif entity_match:
        title = f"{entity} — procedimento {pdf.stem}"
    else:
        title = pdf.stem
    return title, entity


mapping: dict[str, str] = {}
if URLS.exists():
    for line in URLS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        mapping[Path(line).name] = line

rows = []
for pdf in sorted(RAW.glob("*.pdf")):
    url = mapping.get(pdf.name)
    if not url:
        continue
    title, entity = parse_title_and_entity(pdf)
    rows.append({
        "filename": pdf.name,
        "title": title,
        "url": url,
        "entity": entity,
        "date_collected": "2026-04-06",
        "document_type": "Contratos Públicos (Anúncio de procedimento)",
        "notes": "Documento Parte L | Contratos Públicos, adequado para perguntas sobre objeto, preço base, prazo, requisitos, caução, CPV, lotes, local e entidade adjudicante.",
    })

with OUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["filename", "title", "url", "entity", "date_collected", "document_type", "notes"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Manifesto reconstruído com {len(rows)} fontes: {OUT}")
