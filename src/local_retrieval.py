"""Fallback lexical retrieval over local raw documents.

Used when the vector backend or Ollama is unavailable. The goal is not to beat
semantic search, but to keep the product demonstrable and grounded instead of
failing with 503 for every question.
"""

from __future__ import annotations

from functools import lru_cache
import math
import re
from typing import Iterable

from langchain.schema import Document

from . import config
from .chunking import chunk_documents
from .document_loaders import load_documents_from_directory
from .query_analysis import QueryAnalysis, tokenize


_WORD_RE = re.compile(r"[\w%\-]{3,}")


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


@lru_cache(maxsize=1)
def load_local_chunks() -> tuple[Document, ...]:
    docs = load_documents_from_directory(config.RAW_DOCS_DIR)
    if not docs:
        return tuple()
    chunks = chunk_documents(docs, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    return tuple(chunks)


def clear_local_chunks_cache() -> None:
    load_local_chunks.cache_clear()


def _haystack(doc: Document) -> str:
    meta = getattr(doc, "metadata", {}) or {}
    return _norm(
        " \n".join(
            [
                getattr(doc, "page_content", "") or "",
                str(meta.get("source_title") or ""),
                str(meta.get("entity") or ""),
                str(meta.get("document_type") or ""),
                str(meta.get("source_file") or ""),
            ]
        )
    )


def lexical_search(
    query: str,
    analysis: QueryAnalysis,
    *,
    k: int,
    category: str | None = None,
    preferred_source_id: str | None = None,
) -> list[Document]:
    tokens = [tok for tok in tokenize(query) if len(tok) >= 3]
    must_terms = [_norm(item) for item in analysis.must_terms if item]
    preferred_terms = [_norm(item) for item in analysis.preferred_terms if item]
    if not tokens and not must_terms and not preferred_terms:
        return []

    scored: list[tuple[float, Document]] = []
    for doc in load_local_chunks():
        meta = dict(getattr(doc, "metadata", {}) or {})
        if category and category != "todos" and meta.get("category") != category:
            continue
        if preferred_source_id and str(meta.get("source_id") or "") != str(preferred_source_id):
            continue

        haystack = _haystack(doc)
        if not haystack:
            continue

        unique_hits = {tok for tok in tokens if tok in haystack}
        must_hits = [term for term in must_terms if term and term in haystack]
        preferred_hits = [term for term in preferred_terms if term and term in haystack]
        page_bonus = 0.15 if meta.get("page") == 1 else 0.0
        title_bonus = 0.22 if any(tok in _norm(str(meta.get("source_title") or "")) for tok in tokens[:4]) else 0.0
        dense_bonus = min(len(unique_hits) / max(1, len(tokens)), 1.0) * 0.6
        must_bonus = 0.85 * len(must_hits)
        preferred_bonus = 0.24 * min(len(preferred_hits), 4)
        lexical_score = len(unique_hits) + must_bonus + preferred_bonus + dense_bonus + title_bonus + page_bonus

        if lexical_score <= 0:
            continue

        next_doc = Document(page_content=doc.page_content, metadata=meta)
        next_doc.metadata["distance"] = round(1.0 / (1.0 + lexical_score), 6)
        next_doc.metadata["retrieval_backend"] = "lexical"
        next_doc.metadata["lexical_score"] = round(lexical_score, 4)
        scored.append((lexical_score, next_doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored[:k]]
