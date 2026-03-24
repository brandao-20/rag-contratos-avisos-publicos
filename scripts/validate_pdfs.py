"""Valida PDFs do corpus e gera relatório CSV/JSON simples."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_docs"
OUT_JSON = ROOT / "data" / "manifests" / "pdf_quality_report.json"
OUT_CSV = ROOT / "data" / "manifests" / "pdf_quality_report.csv"

rows = []
for pdf in sorted(RAW.glob("*.pdf")):
    info = {"filename": pdf.name, "size_bytes": pdf.stat().st_size, "ok": False, "pages": None, "encrypted": None, "error": None}
    try:
        reader = PdfReader(str(pdf))
        encrypted = bool(getattr(reader, "is_encrypted", False))
        if encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
        info["encrypted"] = encrypted
        info["pages"] = len(reader.pages)
        info["ok"] = True
    except Exception as exc:
        info["error"] = str(exc)
    rows.append(info)

OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["filename", "size_bytes", "ok", "pages", "encrypted", "error"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Relatórios gerados em {OUT_JSON} e {OUT_CSV}")
