"""Inicialização de embeddings com preferência por Ollama local."""

from __future__ import annotations

from langchain.embeddings.base import Embeddings

from . import config



def get_embeddings(model_name: str) -> Embeddings:
    try:
        from langchain_community.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(
            model=model_name,
            base_url=config.OLLAMA_BASE_URL,
            show_progress=False,
        )
    except Exception:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível inicializar embeddings. Confirmar Ollama e/ou sentence-transformers."
            ) from exc
