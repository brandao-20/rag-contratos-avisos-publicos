"""Pipeline de Recuperação Aumentada por Geração (RAG).

Este módulo reúne a lógica necessária para combinar a recuperação de contexto
através do índice vetorial com a geração de respostas por um LLM local via
Ollama. Fornece métodos para responder a perguntas e para extrair informação
estruturada, retornando também os documentos utilizados para que a interface
possa mostrar as citações.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

from langchain.schema import Document

from .config import TOP_K, get_model_names
from .prompts import QA_PROMPT_TEMPLATE, EXTRACTION_PROMPT_TEMPLATE


@dataclass
class RAGPipeline:
    """Pipeline RAG que integra vector store, LLM e prompts."""

    vectorstore: Any
    top_k: int = TOP_K

    def __post_init__(self) -> None:
        # Instanciar retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": self.top_k}
        )
        # Carregar nomes de modelos
        embedding_name, llm_name = get_model_names()
        # Instanciar LLM
        try:
            from langchain_community.chat_models import ChatOllama

            self.llm = ChatOllama(model=llm_name)
        except Exception:
            # Falha ao carregar ChatOllama (provavelmente Ollama não está instalado)
            self.llm = None

    def _get_context(self, question: str) -> Tuple[str, List[Document]]:
        """Recupera os `top_k` documentos mais relevantes e concatena os conteúdos.

        Args:
            question: Pergunta do utilizador.

        Returns:
            Uma string com o contexto concatenado e a lista de documentos.
        """
        if hasattr(self.retriever, "invoke"):
            docs: List[Document] = self.retriever.invoke(question)
        else:
            docs = self.retriever.get_relevant_documents(question)
        context = "\n\n".join([d.page_content for d in docs])
        return context, docs

    def answer_question(self, question: str) -> Tuple[str, List[Document]]:
        """Gera uma resposta para a pergunta baseada no contexto recuperado.

        Retorna a resposta do modelo e a lista de documentos utilizados para
        permitir a apresentação de citações ao utilizador. Se não houver
        contexto relevante ou o LLM não estiver disponível, devolve uma
        mensagem de fallback.

        Args:
            question: Pergunta formulada pelo utilizador.

        Returns:
            Tuple `(resposta, documentos)`.
        """
        context, docs = self._get_context(question)
        if not context.strip():
            return (
                "Não foi encontrada informação suficiente nos documentos carregados.",
                docs,
            )
        if self.llm is None:
            # LLM indisponível
            return (
                "O modelo de linguagem não está disponível. Certifique‑se de que o serviço Ollama está a correr e que o modelo foi instalado.",
                docs,
            )
        from langchain.prompts import PromptTemplate

        prompt = PromptTemplate.from_template(QA_PROMPT_TEMPLATE)
        prompt_text = prompt.format(context=context, question=question)
        result = self.llm.invoke(prompt_text)
        answer = getattr(result, "content", str(result))
        return answer.strip(), docs

    def extract_structured(self, docs: List[Document]) -> Dict[str, Any]:
        """Extrai campos estruturados a partir dos documentos fornecidos.

        Args:
            docs: Lista de documentos (chunks) a utilizar como contexto.

        Returns:
            Dicionário com campos extraídos. Pode estar vazio se o modelo não
            estiver disponível ou se não for possível interpretar a resposta.
        """
        context = "\n\n".join([d.page_content for d in docs])
        if not context.strip() or self.llm is None:
            return {}
        from langchain.prompts import PromptTemplate

        prompt = PromptTemplate.from_template(EXTRACTION_PROMPT_TEMPLATE)
        prompt_text = prompt.format(context=context)
        result = self.llm.invoke(prompt_text)
        text = getattr(result, "content", str(result)).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        # Tentar decodificar o JSON; se falhar, devolver dicionário vazio
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
