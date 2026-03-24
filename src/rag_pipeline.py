"""Pipeline RAG principal com retrieval, guardrails, confiança e output para UI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain.prompts import PromptTemplate
from langchain.schema import Document

from . import config
from .answer_builder import AnswerPackage, build_grounded_answer, normalize_chunks
from .extractors import extract_structured_from_docs
from .prompts import QA_PROMPT_TEMPLATE
from .query_analysis import QueryAnalysis, analyze_query, augment_query_for_retrieval
from .source_registry import group_documents_by_source
from .vector_store import query_vector_store


@dataclass
class QAResult:
    query: str
    answer_markdown: str
    documents: list[Document]
    structured_data: dict[str, Any]
    confidence_label: str
    confidence_score: float
    confidence_reasons: list[str]
    retrieval_query: str
    elapsed_ms: int
    citations_count: int
    sources_grouped: list[dict[str, Any]]
    follow_up_questions: list[str]
    used_llm: bool
    analysis: QueryAnalysis


class RAGPipeline:
    def __init__(self, vectorstore: Any, *, top_k: int = config.TOP_K) -> None:
        self.vectorstore = vectorstore
        self.top_k = top_k
        _, llm_name = config.get_model_names()
        try:
            from langchain_community.chat_models import ChatOllama

            self.llm = ChatOllama(
                model=llm_name,
                base_url=config.OLLAMA_BASE_URL,
                temperature=0.05,
                num_predict=260,
                timeout=config.OLLAMA_REQUEST_TIMEOUT,
            )
        except Exception:
            self.llm = None

    def retrieve(self, query: str, *, top_k: int | None = None, category: str | None = None) -> tuple[str, QueryAnalysis, list[Document]]:
        analysis = analyze_query(query)
        retrieval_query = augment_query_for_retrieval(query, analysis)
        desired_k = top_k or self.top_k
        candidate_k = max(desired_k, config.RETRIEVAL_CANDIDATES)
        docs = query_vector_store(
            self.vectorstore,
            retrieval_query,
            k=candidate_k,
            category=category,
        )
        normalized = normalize_chunks(query, docs, analysis.must_terms)
        ranked_docs: list[Document] = []
        for ch in normalized[:desired_k]:
            pseudo = Document(page_content=ch.text, metadata=ch.meta)
            ranked_docs.append(pseudo)
        return retrieval_query, analysis, ranked_docs

    def _numbered_context(self, docs: list[Document]) -> str:
        parts: list[str] = []
        for idx, doc in enumerate(docs, start=1):
            meta = doc.metadata or {}
            title = meta.get("source_title") or meta.get("source_file") or f"Documento {idx}"
            page = meta.get("page")
            loc = f"p.{page}" if page is not None else "texto"
            parts.append(f"[{idx}] {title} ({loc})\n{doc.page_content}")
        return "\n\n".join(parts)

    def extract_structured(self, docs: list[Document]) -> dict[str, Any]:
        return extract_structured_from_docs(docs)

    def ask(self, query: str, *, top_k: int | None = None, category: str | None = None) -> QAResult:
        start = time.perf_counter()
        retrieval_query, analysis, docs = self.retrieve(query, top_k=top_k, category=category)
        normalized = normalize_chunks(query, docs, analysis.must_terms)
        context_docs = docs[: max(1, min(len(docs), min(4, top_k or self.top_k)))]
        context = self._numbered_context(context_docs)
        prompt = PromptTemplate.from_template(QA_PROMPT_TEMPLATE)
        prompt_text = prompt.format(context=context, question=query)
        followups = config.FOLLOW_UP_BY_INTENT.get(analysis.intent, [])
        package: AnswerPackage = build_grounded_answer(
            query=query,
            analysis=analysis,
            chunks=normalized,
            llm=self.llm,
            prompt_text=prompt_text,
            follow_ups=followups,
            retrieval_query=retrieval_query,
        )
        structured = self.extract_structured(context_docs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        grouped = group_documents_by_source(docs)
        return QAResult(
            query=query,
            answer_markdown=package.answer_markdown,
            documents=docs,
            structured_data=structured,
            confidence_label=package.confidence.label,
            confidence_score=package.confidence.score,
            confidence_reasons=package.confidence.reasons,
            retrieval_query=package.retrieval_query,
            elapsed_ms=elapsed_ms,
            citations_count=len(package.cited_indexes),
            sources_grouped=grouped,
            follow_up_questions=package.follow_up_questions,
            used_llm=package.used_llm,
            analysis=analysis,
        )
