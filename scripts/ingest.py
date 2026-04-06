"""Script de ingestão com batches, feedback de progresso e metadados do índice."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.chunking import chunk_documents
from src.document_loaders import load_documents_from_directory
from src.embeddings import get_embeddings, get_embeddings_status
from src.local_retrieval import clear_local_chunks_cache
from src.vector_store import create_vector_store



def main() -> None:
    config.ensure_directories()
    clear_local_chunks_cache()
    docs = load_documents_from_directory(config.RAW_DOCS_DIR)
    if not docs:
        print(f"Nenhum documento legível encontrado em {config.RAW_DOCS_DIR}.")
        return
    print(f"Lidos {len(docs)} documentos (após separação por páginas). A segmentar…")
    chunks = chunk_documents(docs, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    print(f"Gerados {len(chunks)} chunks. A calcular embeddings…")
    embedding_model_name, _ = config.get_model_names()
    status = get_embeddings_status(embedding_model_name)
    embeddings = get_embeddings(embedding_model_name)
    start = time.perf_counter()
    create_vector_store(chunks, embeddings, clear_existing=True)
    elapsed = time.perf_counter() - start
    config.INDEX_METADATA_FILE.write_text(
        json.dumps(
            {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "provider": status.get("provider"),
                "model": status.get("model") or embedding_model_name,
                "detail": status.get("detail"),
                "chunks": len(chunks),
                "documents": len(docs),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Índice criado com sucesso em {config.CHROMA_DIR}. Tempo de indexação: {elapsed:.1f}s")
    if status.get("provider") != "ollama":
        print("Nota: Ollama indisponível durante a ingestão; foi usado fallback de embeddings local.")


if __name__ == "__main__":
    main()
