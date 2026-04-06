"""Registo e agrupamento de fontes documentais."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

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


def _humanize_title(raw_title: str | None, filename: str, document_type: str | None) -> str:
    raw = (raw_title or '').strip()
    source_id = Path(filename).stem
    if raw and not raw.isdigit():
        return raw
    label = (document_type or '').strip()
    if 'cp_hora' in (label.lower() + ' ' + filename.lower()):
        return f'Procedimento {source_id}'
    if '2.ª série' in label.lower() or '2. serie' in label.lower() or 'serie' in label.lower():
        return f'Aviso DR {source_id}'
    if label:
        return f'{label} · {source_id}'
    return f'Documento {source_id}'


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
            title = _humanize_title(
                (row.get("title") or "").strip()
                or filename.replace("_", " ").replace(".pdf", "").replace(".txt", "").strip(),
                filename,
                doc_type,
            )
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



def clear_registry_cache() -> None:
    load_source_registry.cache_clear()
    get_source.cache_clear()
    get_source_by_filename.cache_clear()


@lru_cache(maxsize=1024)
def get_source_by_filename(filename: str) -> Optional[SourceRecord]:
    source_id = Path(filename).stem
    return load_source_registry().get(source_id)


@lru_cache(maxsize=1024)
def get_source(source_id: str) -> Optional[SourceRecord]:
    return load_source_registry().get(source_id)



def list_sources() -> list[SourceRecord]:
    return list(load_source_registry().values())



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



def group_documents_by_source(docs: Iterable[Any], prioritized_source_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    priority = {str(item) for item in (prioritized_source_ids or []) if item}
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
                "priority": source_id in priority,
            },
        )
        page = meta.get("page")
        if page is not None and page not in group["pages"]:
            group["pages"].append(page)
        group["citations"].append(
            {
                "index": idx,
                "page": page,
                "chunk_id": meta.get("chunk_id") or meta.get("chunk_uid"),
                "excerpt": getattr(doc, "page_content", ""),
            }
        )
        group["count"] += 1
    out = list(grouped.values())
    for item in out:
        item["pages"] = sorted([p for p in item["pages"] if p is not None])
        item["primary_excerpt"] = item["citations"][0]["excerpt"] if item["citations"] else ""
    out.sort(key=lambda row: (not bool(row.get("priority")), -int(row.get("count") or 0), str(row.get("title") or "")))
    for item in out:
        item.pop("priority", None)
    return out
