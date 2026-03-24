"""Script de ingestão com batches e feedback de progresso."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.chunking import chunk_documents
from src.document_loaders import load_documents_from_directory
from src.embeddings import get_embeddings
from src.vector_store import create_vector_store



def main() -> None:
    config.ensure_directories()
    docs = load_documents_from_directory(config.RAW_DOCS_DIR)
    if not docs:
        print(f"Nenhum documento legível encontrado em {config.RAW_DOCS_DIR}.")
        return
    print(f"Lidos {len(docs)} documentos (após separação por páginas). A segmentar…")
    chunks = chunk_documents(docs, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    print(f"Gerados {len(chunks)} chunks. A calcular embeddings…")
    embedding_model_name, _ = config.get_model_names()
    embeddings = get_embeddings(embedding_model_name)
    start = time.perf_counter()
    create_vector_store(chunks, embeddings, clear_existing=True)
    elapsed = time.perf_counter() - start
    print(f"Índice criado com sucesso em {config.CHROMA_DIR}. Tempo de indexação: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
