"""Gestão da base de dados vetorial (ChromaDB)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from langchain_community.vectorstores import Chroma
from langchain.embeddings.base import Embeddings

from . import config


def create_vector_store(documents: Iterable, embeddings: Embeddings, *, clear_existing: bool = False) -> Chroma:
    """Cria um índice Chroma a partir de documentos.

    Args:
        documents: Documentos/chunks a indexar.
        embeddings: Modelo de embeddings.
        clear_existing: Se True, remove o índice persistido antes de recriar.
    """
    config.ensure_directories()
    if clear_existing and config.CHROMA_DIR.exists():
        shutil.rmtree(config.CHROMA_DIR, ignore_errors=True)
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    vectorstore = Chroma.from_documents(
        documents=list(documents),
        embedding=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    )
    vectorstore.persist()
    return vectorstore


def load_vector_store(embeddings: Embeddings) -> Chroma:
    return Chroma(persist_directory=str(config.CHROMA_DIR), embedding_function=embeddings)
