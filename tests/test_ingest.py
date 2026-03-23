"""Testes básicos (smoke tests) para ingestão, chunking e retrieval.

Nota: usam embeddings falsos para evitar dependência de Ollama durante os testes.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.document_loaders import load_documents_from_directory
from src.chunking import chunk_documents
from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores import Chroma


class FakeEmbeddings(Embeddings):
    """Embeddings determinísticos simples para testes."""

    def _embed(self, text: str) -> list[float]:
        base = sum(ord(c) for c in text)
        return [float((base + i * 17) % 997) / 997.0 for i in range(16)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class TestIngest(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_dir = PROJECT_ROOT / "data" / "raw_docs"

    def test_document_loading(self) -> None:
        docs = load_documents_from_directory(self.raw_dir)
        self.assertGreater(len(docs), 0, "Nenhum documento legível foi carregado.")
        # Garantir que PDFs vazios não causam crash e que pelo menos há metadata base
        self.assertIn("source_file", docs[0].metadata)

    def test_chunking(self) -> None:
        docs = load_documents_from_directory(self.raw_dir)
        chunks = chunk_documents(docs, chunk_size=500, chunk_overlap=50)
        self.assertGreaterEqual(len(chunks), len(docs))
        self.assertIn("chunk_id", chunks[0].metadata)

    def test_vector_store_creation_and_retrieval(self) -> None:
        docs = load_documents_from_directory(self.raw_dir)
        chunks = chunk_documents(docs, chunk_size=500, chunk_overlap=50)
        tmpdir = tempfile.mkdtemp(prefix="chroma_test_")
        try:
            vector_store = Chroma.from_documents(
                chunks,
                FakeEmbeddings(),
                persist_directory=tmpdir,
            )
            retriever = vector_store.as_retriever(search_kwargs={"k": 1})
            # Compatibilidade com versões diferentes da LangChain
            if hasattr(retriever, "invoke"):
                results = retriever.invoke("objeto")
            else:
                results = retriever.get_relevant_documents("objeto")
            self.assertTrue(len(results) > 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
