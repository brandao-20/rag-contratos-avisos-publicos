"""Wrapper para obtenção de trechos relevantes a partir do índice.

Este módulo expõe uma função de conveniência para criar um objecto retriever
a partir de um índice Chroma, definindo o número de documentos a recuperar
(top_k). O retriever será utilizado pelo pipeline RAG para obter contexto.
"""

from __future__ import annotations

from langchain_community.vectorstores import Chroma


def get_retriever(vectorstore: Chroma, *, top_k: int) -> any:
    """Constrói um objecto retriever a partir do vector store.

    Args:
        vectorstore: Instância de `Chroma` previamente criada ou carregada.
        top_k: Número máximo de documentos (chunks) a recuperar.

    Returns:
        Objecto retriever configurado.
    """
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": top_k})
