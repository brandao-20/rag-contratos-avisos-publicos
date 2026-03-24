"""Registo e enriquecimento de fontes a partir do manifesto."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from . import config


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    filename: str
    title: str
    url: Optional[str]
    entity: Optional[str]
    document_type: Optional[str]
    category: str
    notes: Optional[str]



def _derive_category(document_type: str | None, filename: str) -> str:
    text = ((document_type or "") + " " + filename).lower()
    if "cp_hora" in text or "contrato" in text or "procedimento" in text:
        return "contratacao_publica"
    if "aviso" in text or "2.ª série" in text or "2. serie" in text or "serie" in text:
        return "aviso_publico"
    return "documento_publico"


@lru_cache(maxsize=1)
def load_source_registry() -> dict[str, SourceRecord]:
    config.ensure_directories()
    manifest = config.MANIFEST_DIR / "sources_manifest.csv"
    records: dict[str, SourceRecord] = {}
    if not manifest.exists():
        return records
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = (row.get("filename") or "").strip()
            if not filename:
                continue
            source_id = Path(filename).stem
            doc_type = (row.get("document_type") or "").strip() or None
            category = _derive_category(doc_type, filename)
            entity = (row.get("entity") or "").strip() or None
            title = (row.get("title") or "").strip() or filename.replace("_", " ").replace(".pdf", "").replace(".txt", "").strip()
            records[source_id] = SourceRecord(
                source_id=source_id,
                filename=filename,
                title=title,
                url=(row.get("url") or "").strip() or None,
                entity=entity,
                document_type=doc_type,
                category=category,
                notes=(row.get("notes") or "").strip() or None,
            )
    return records


@lru_cache(maxsize=1024)
def get_source_by_filename(filename: str) -> Optional[SourceRecord]:
    source_id = Path(filename).stem
    return load_source_registry().get(source_id)


@lru_cache(maxsize=1024)
def get_source(source_id: str) -> Optional[SourceRecord]:
    return load_source_registry().get(source_id)



def enrich_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(meta or {})
    source = None
    if out.get("source_id"):
        source = get_source(str(out["source_id"]))
    elif out.get("source_file"):
        source = get_source_by_filename(str(out["source_file"]))
    if source:
        out.setdefault("source_id", source.source_id)
        out.setdefault("source_url", source.url)
        out.setdefault("entity", source.entity)
        out.setdefault("document_type", source.document_type)
        out.setdefault("category", source.category)
        out.setdefault("source_title", source.title)
    return out



def group_documents_by_source(docs: Iterable[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for idx, doc in enumerate(docs, start=1):
        meta = enrich_metadata(getattr(doc, "metadata", {}) or {})
        source_id = str(meta.get("source_id") or meta.get("source_file") or f"source_{idx}")
        group = grouped.setdefault(
            source_id,
            {
                "source_id": source_id,
                "title": meta.get("source_title") or meta.get("source_file") or source_id,
                "filename": meta.get("source_file"),
                "source_url": meta.get("source_url"),
                "entity": meta.get("entity"),
                "document_type": meta.get("document_type"),
                "pages": [],
                "citations": [],
                "count": 0,
            },
        )
        page = meta.get("page")
        if page is not None and page not in group["pages"]:
            group["pages"].append(page)
        group["citations"].append({
            "index": idx,
            "page": page,
            "chunk_id": meta.get("chunk_id"),
            "excerpt": getattr(doc, "page_content", ""),
        })
        group["count"] += 1
    out = list(grouped.values())
    for item in out:
        item["pages"] = sorted([p for p in item["pages"] if p is not None])
        item["primary_excerpt"] = item["citations"][0]["excerpt"] if item["citations"] else ""
    return out
