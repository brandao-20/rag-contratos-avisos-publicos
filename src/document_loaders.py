"""Carregamento de documentos de vários formatos com metadados enriquecidos."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

from langchain.schema import Document
from pypdf import PdfReader

_MANIFEST_CACHE: Dict[str, Dict[str, str]] | None = None


def _manifest_path() -> Path:
    return Path("data/manifests/sources_manifest.csv")


def _load_manifest() -> Dict[str, Dict[str, str]]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None:
        return _MANIFEST_CACHE
    manifest = _manifest_path()
    mapping: Dict[str, Dict[str, str]] = {}
    if manifest.exists():
        with manifest.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = (row.get("filename") or "").strip()
                if filename:
                    mapping[filename] = {k: (v or "").strip() for k, v in row.items()}
    _MANIFEST_CACHE = mapping
    return mapping


def _base_metadata(path: Path, *, page: int | None) -> Dict[str, Any]:
    manifest_row = _load_manifest().get(path.name, {})
    source_type = path.suffix.lower().lstrip(".")
    doc_type = manifest_row.get("document_type", "")
    category = (
        "contratacao_publica"
        if ("procedimento" in doc_type.lower() or "contrato" in doc_type.lower())
        else "aviso_publico"
    )
    return {
        "source_file": path.name,
        "source_path": str(path),
        "source_type": source_type,
        "source_url": manifest_row.get("url") or None,
        "entity": manifest_row.get("entity") or None,
        "category": category,
        "document_type": doc_type or None,
        "page": page,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def load_pdf(path: Path) -> List[Document]:
    docs: List[Document] = []
    if not path.exists() or path.stat().st_size == 0:
        return docs
    try:
        reader = PdfReader(str(path))
    except Exception:
        return docs
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not cleaned:
            continue
        docs.append(Document(page_content=cleaned, metadata=_base_metadata(path, page=page_number)))
    return docs


def load_text_file(path: Path) -> List[Document]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = "\n".join(line.rstrip() for line in content.splitlines() if line.strip())
    if not cleaned:
        return []
    return [Document(page_content=cleaned, metadata=_base_metadata(path, page=None))]


def load_documents_from_directory(directory: Path) -> List[Document]:
    all_docs: List[Document] = []
    if not directory.exists():
        return all_docs
    for file in sorted(directory.iterdir()):
        if file.is_dir():
            continue
        ext = file.suffix.lower()
        if ext == ".pdf":
            all_docs.extend(load_pdf(file))
        elif ext in {".txt", ".md"}:
            all_docs.extend(load_text_file(file))
    return all_docs
