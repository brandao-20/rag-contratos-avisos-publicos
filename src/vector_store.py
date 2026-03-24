"""Operações sobre ChromaDB e retrieval com scoring adicional."""

from __future__ import annotations

import shutil
from typing import Iterable

from langchain.embeddings.base import Embeddings

try:  # pragma: no cover
    from langchain_chroma import Chroma  # type: ignore
except Exception:  # pragma: no cover
    from langchain_community.vectorstores import Chroma  # type: ignore

from . import config
from .source_registry import enrich_metadata


def create_vector_store(documents: Iterable, embeddings: Embeddings, *, clear_existing: bool = False) -> Chroma:
    config.ensure_directories()
    if clear_existing and config.CHROMA_DIR.exists():
        shutil.rmtree(config.CHROMA_DIR, ignore_errors=True)
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    docs = list(documents)
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(config.CHROMA_DIR),
        ids=[getattr(d, 'metadata', {}).get('chunk_uid') for d in docs],
    )
    return vectorstore


def load_vector_store(embeddings: Embeddings) -> Chroma:
    return Chroma(persist_directory=str(config.CHROMA_DIR), embedding_function=embeddings)


def query_vector_store(vectorstore: Chroma, query: str, *, k: int, category: str | None = None) -> list:
    where = None
    if category and category != "todos":
        where = {"category": category}
    results = vectorstore.similarity_search_with_score(query, k=k, filter=where)
    docs = []
    for doc, distance in results:
        meta = enrich_metadata(getattr(doc, "metadata", {}) or {})
        meta["distance"] = float(distance)
        doc.metadata = meta
        docs.append(doc)
    return docs
