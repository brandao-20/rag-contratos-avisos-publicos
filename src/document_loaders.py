"""Carregamento robusto de PDFs/TXT/MD com metadados enriquecidos."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.schema import Document
from pypdf import PdfReader

from . import config
from .source_registry import get_source_by_filename, load_source_registry


def _base_metadata(path: Path, *, page: int | None) -> dict[str, Any]:
    source = get_source_by_filename(path.name)
    source_id = path.stem
    category = source.category if source else ("contratacao_publica" if source_id.isdigit() and len(source_id) >= 8 else "documento_publico")
    return {
        "source_id": source.source_id if source else source_id,
        "source_file": path.name,
        "source_title": source.title if source else path.stem,
        "source_path": str(path),
        "source_type": path.suffix.lower().lstrip("."),
        "source_url": source.url if source else None,
        "entity": source.entity if source else None,
        "document_type": source.document_type if source else None,
        "category": category,
        "page": page,
        "locator": f"p.{page}" if page is not None else None,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }



def load_pdf(path: Path) -> list[Document]:
    docs: list[Document] = []
    if not path.exists() or path.stat().st_size == 0:
        return docs
    try:
        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                return docs
    except Exception:
        return docs
    try:
        pages = reader.pages
    except Exception:
        return docs
    for page_number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not cleaned:
            continue
        docs.append(Document(page_content=cleaned, metadata=_base_metadata(path, page=page_number)))
    return docs



def load_text_file(path: Path) -> list[Document]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    cleaned = "\n".join(line.rstrip() for line in content.splitlines() if line.strip())
    if not cleaned:
        return []
    return [Document(page_content=cleaned, metadata=_base_metadata(path, page=None))]



def _allowed_filenames_from_manifest() -> set[str] | None:
    registry = load_source_registry()
    if not registry:
        return None
    filenames = {record.filename for record in registry.values() if record.filename}
    return filenames or None



def load_documents_from_directory(directory: Path) -> list[Document]:
    all_docs: list[Document] = []
    if not directory.exists():
        return all_docs

    allowed_filenames = _allowed_filenames_from_manifest()
    if allowed_filenames is not None:
        files = [directory / name for name in sorted(allowed_filenames) if (directory / name).exists()]
    else:
        files = sorted(directory.iterdir())

    for file in files:
        if file.is_dir():
            continue
        ext = file.suffix.lower()
        if ext == ".pdf":
            all_docs.extend(load_pdf(file))
        elif ext in {".txt", ".md"}:
            all_docs.extend(load_text_file(file))
    return all_docs
