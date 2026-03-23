"""Script para ingestão de documentos e criação do índice.

Uso:
    python scripts/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.document_loaders import load_documents_from_directory
from src.chunking import chunk_documents
from src.embeddings import get_embeddings
from src.vector_store import create_vector_store


def main() -> None:
    config.ensure_directories()
    raw_dir = config.RAW_DOCS_DIR
    docs = load_documents_from_directory(raw_dir)
    if not docs:
        print(f"Nenhum documento legível encontrado em {raw_dir}. Coloque ficheiros válidos e volte a executar.")
        return
    print(f"Lidos {len(docs)} documentos (após separação por páginas). A segmentar…")
    chunked = chunk_documents(
        docs,
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    print(f"Gerados {len(chunked)} chunks. A calcular embeddings…")
    embedding_model_name, _ = config.get_model_names()
    embeddings = get_embeddings(embedding_model_name)
    create_vector_store(chunked, embeddings, clear_existing=True)
    print(f"Índice criado com sucesso em {config.CHROMA_DIR}.")


if __name__ == "__main__":
    main()
