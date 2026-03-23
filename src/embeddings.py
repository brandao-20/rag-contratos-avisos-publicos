"""Inicialização do modelo de embeddings.

Este módulo encapsula a lógica para seleccionar o modelo de embeddings. O
objectivo é utilizar `OllamaEmbeddings` quando a biblioteca `ollama` estiver
disponível e um modelo adequado estiver instalado. Caso contrário, é
apresentado um aviso e utiliza-se um modelo alternativo baseado em
`sentence-transformers` para garantir que o pipeline continua funcional.
"""

from __future__ import annotations

from typing import Any

from langchain.embeddings.base import Embeddings


def get_embeddings(model_name: str) -> Embeddings:
    """Cria uma instância de embeddings apropriada.

    Args:
        model_name: Nome do modelo a utilizar com Ollama. Ignorado se
            `OllamaEmbeddings` não estiver disponível.

    Returns:
        Objecto de embeddings que pode gerar vectores a partir de texto.
    """
    # Tentar usar OllamaEmbeddings se estiver disponível
    try:
        from langchain_community.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(model=model_name)
    except Exception:
        # Fallback para um modelo genérico baseado em sentence-transformers
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            # Modelo leve adequado para máquinas sem aceleração GPU
            return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível inicializar nenhum modelo de embeddings. "
                "Certifique-se de que instalou o pacote 'langchain-community' e, "
                "se pretender usar Ollama, que o serviço está disponível."
            ) from exc
