"""Inicialização de embeddings com seleção explícita do provider."""

from __future__ import annotations

import requests
from langchain.embeddings.base import Embeddings

from . import config


class EmbeddingsStatus(dict):
    pass


HF_FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _ollama_tags() -> dict:
    response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=2)
    response.raise_for_status()
    payload = response.json() or {}
    return payload



def ollama_available(model_name: str | None = None) -> bool:
    try:
        payload = _ollama_tags()
    except Exception:
        return False
    if not model_name:
        return True
    names = {str(item.get("name") or "").split(":")[0] for item in payload.get("models", []) if isinstance(item, dict)}
    return model_name.split(":")[0] in names



def _is_huggingface_model(model_name: str | None) -> bool:
    if not model_name:
        return False
    raw = model_name.strip().lower()
    return "/" in raw or raw.startswith("sentence-transformers") or raw.startswith("all-")



def _build_hf_status(model_name: str) -> EmbeddingsStatus:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401

        return EmbeddingsStatus(
            provider="huggingface",
            ready=True,
            model=model_name,
            detail="Embeddings locais via sentence-transformers. Ingestão mais rápida e sem dependência do endpoint de embeddings do Ollama.",
        )
    except Exception as exc:
        return EmbeddingsStatus(provider="none", ready=False, model=None, detail=str(exc))



def get_embeddings_status(model_name: str) -> EmbeddingsStatus:
    if _is_huggingface_model(model_name):
        return _build_hf_status(model_name)

    if ollama_available(model_name):
        return EmbeddingsStatus(provider="ollama", ready=True, model=model_name, detail=None)

    return _build_hf_status(HF_FALLBACK_MODEL)



def get_embeddings(model_name: str) -> Embeddings:
    if _is_huggingface_model(model_name):
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 64},
        )

    if ollama_available(model_name):
        from langchain_community.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(
            model=model_name,
            base_url=config.OLLAMA_BASE_URL,
            show_progress=False,
        )

    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=HF_FALLBACK_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 64},
        )
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível inicializar embeddings. Confirmar sentence-transformers e/ou Ollama."
        ) from exc
