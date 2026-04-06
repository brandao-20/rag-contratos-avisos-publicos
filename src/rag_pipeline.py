"""Pipeline RAG principal com retrieval híbrido e fallback lexical local."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain.prompts import PromptTemplate
from langchain.schema import Document

from . import config
from .answer_builder import AnswerPackage, build_grounded_answer, normalize_chunks
from .extractors import extract_structured_from_docs
from .local_retrieval import lexical_search, load_local_chunks
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
    procedural_steps: list[str]
    used_llm: bool
    analysis: QueryAnalysis
    retrieval_backend: str = "lexical"
    primary_source_id: str | None = None
    primary_source_title: str | None = None


class RAGPipeline:
    def __init__(self, vectorstore: Any | None, *, top_k: int = config.TOP_K, llm: Any | None = None) -> None:
        self.vectorstore = vectorstore
        self.top_k = top_k
        self.llm = llm
        self.default_backend = "vector" if vectorstore is not None else "lexical"

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        category: str | None = None,
        preferred_source_id: str | None = None,
    ) -> tuple[str, QueryAnalysis, list[Document], str]:
        analysis = analyze_query(query)
        retrieval_query = augment_query_for_retrieval(query, analysis)
        desired_k = top_k or self.top_k
        candidate_k = max(desired_k, config.RETRIEVAL_CANDIDATES)

        docs: list[Document] = []
        backend = "lexical"
        vector_error: Exception | None = None
        if self.vectorstore is not None:
            try:
                docs = query_vector_store(
                    self.vectorstore,
                    retrieval_query,
                    k=candidate_k,
                    category=category,
                    preferred_source_id=preferred_source_id,
                )
                backend = "vector"
            except Exception as exc:
                vector_error = exc

        normalized = normalize_chunks(query, docs, analysis.must_terms)
        if not normalized or vector_error is not None:
            docs = lexical_search(query, analysis, k=candidate_k, category=category, preferred_source_id=preferred_source_id)
            backend = "lexical"
            normalized = normalize_chunks(query, docs, analysis.must_terms)
            if vector_error is not None and normalized:
                for chunk in normalized[:4]:
                    chunk.meta.setdefault("vector_error", str(vector_error))

        ranked_docs: list[Document] = []
        for chunk in normalized[:desired_k]:
            meta = dict(chunk.meta)
            meta["retrieval_backend"] = backend
            ranked_docs.append(Document(page_content=chunk.text, metadata=meta))
        return retrieval_query, analysis, ranked_docs, backend

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

    @staticmethod
    def _pick_primary_source(chunks: list[Any], preferred_source_id: str | None = None) -> tuple[str | None, str | None]:
        if not chunks:
            return None, None

        preferred = str(preferred_source_id or '').strip() or None
        if preferred:
            for chunk in chunks:
                source_id = str(chunk.meta.get('source_id') or chunk.meta.get('source_file') or '').strip()
                if source_id == preferred:
                    return source_id, str(chunk.meta.get('source_title') or chunk.meta.get('entity') or source_id).strip() or source_id

        aggregate: dict[str, float] = {}
        labels: dict[str, str] = {}
        for index, chunk in enumerate(chunks[:12], start=1):
            source_id = str(chunk.meta.get('source_id') or chunk.meta.get('source_file') or '').strip()
            if not source_id:
                continue
            rank_bonus = max(0.0, 1.3 - (index - 1) * 0.12)
            aggregate[source_id] = aggregate.get(source_id, 0.0) + float(chunk.blended) + float(chunk.coverage) * 0.18 + rank_bonus
            labels.setdefault(source_id, str(chunk.meta.get('source_title') or chunk.meta.get('entity') or source_id).strip() or source_id)

        if not aggregate:
            return None, None

        source_id = max(aggregate.items(), key=lambda item: item[1])[0]
        return source_id, labels.get(source_id) or source_id

    @staticmethod
    def _filter_docs_by_source(docs: list[Document], source_id: str | None) -> list[Document]:
        if not source_id:
            return docs
        focused = [doc for doc in docs if str((doc.metadata or {}).get('source_id') or (doc.metadata or {}).get('source_file') or '').strip() == source_id]
        return focused or docs

    def ask(
        self,
        query: str,
        *,
        top_k: int | None = None,
        category: str | None = None,
        preferred_source_id: str | None = None,
    ) -> QAResult:
        start = time.perf_counter()
        retrieval_query, analysis, docs, retrieval_backend = self.retrieve(
            query,
            top_k=top_k,
            category=category,
            preferred_source_id=preferred_source_id,
        )
        normalized = normalize_chunks(query, docs, analysis.must_terms)
        primary_source_id, primary_source_title = self._pick_primary_source(normalized, preferred_source_id)
        focused_docs = self._filter_docs_by_source(docs, primary_source_id)
        focused_normalized = normalize_chunks(query, focused_docs, analysis.must_terms)

        context_docs = focused_docs[: max(1, min(len(focused_docs), top_k or self.top_k))]
        context = self._numbered_context(context_docs)
        prompt = PromptTemplate.from_template(QA_PROMPT_TEMPLATE)
        prompt_text = prompt.format(context=context, question=query)
        followups = config.FOLLOW_UP_BY_INTENT.get(analysis.intent, [])
        package: AnswerPackage = build_grounded_answer(
            query=query,
            analysis=analysis,
            chunks=focused_normalized,
            llm=self.llm,
            prompt_text=prompt_text,
            follow_ups=followups,
            retrieval_query=retrieval_query,
        )
        structured = self.extract_structured(context_docs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        grouped = group_documents_by_source(
            focused_docs,
            prioritized_source_ids=[primary_source_id] if primary_source_id else None,
        )
        return QAResult(
            query=query,
            answer_markdown=package.answer_markdown,
            documents=focused_docs,
            structured_data=structured,
            confidence_label=package.confidence.label,
            confidence_score=package.confidence.score,
            confidence_reasons=package.confidence.reasons,
            retrieval_query=package.retrieval_query,
            elapsed_ms=elapsed_ms,
            citations_count=len(package.cited_indexes),
            sources_grouped=grouped,
            follow_up_questions=package.follow_up_questions,
            procedural_steps=package.procedural_steps,
            used_llm=package.used_llm,
            analysis=analysis,
            retrieval_backend=retrieval_backend,
            primary_source_id=primary_source_id,
            primary_source_title=primary_source_title,
        )


__all__ = ["RAGPipeline", "QAResult"]
