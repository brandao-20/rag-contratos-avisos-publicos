"""API FastAPI para o produto RAG de contratos/avisos públicos."""

from __future__ import annotations

from functools import lru_cache
from datetime import datetime
from typing import Any, Literal


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import config
from src.catalog import build_corpus_overview, get_glossary_entries
from src.query_analysis import analyze_query
from src.session_store import (
    create_session, delete_session, get_session, list_sessions, upsert_session,
    list_saved_responses, add_saved_response, remove_saved_response,
)
from src.source_registry import load_source_registry

import logging
import json as _json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_log = logging.getLogger("rag_api")



ALLOWED_CATEGORIES = [
    {"id": "todos", "label": "Todos os documentos"},
    {"id": "contratacao_publica", "label": "Contratação pública"},
]


class SessionCreateRequest(BaseModel):
    title: str = Field(default="Nova sessão", max_length=120)


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class AskRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=12)
    category: Literal["todos", "contratacao_publica"] = "todos"
    preferred_source_id: str | None = Field(default=None, max_length=120)


class SessionMessageModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str | None = None
    qa_result: dict[str, Any] | None = None


class SessionSummaryModel(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages_count: int
    last_message_preview: str | None = None


class SessionDetailModel(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    active_source_id: str | None = None
    active_source_title: str | None = None
    messages: list[SessionMessageModel]


class SourceCitationModel(BaseModel):
    index: int
    page: int | None = None
    locator: str | None = None
    chunk_id: str | None = None
    excerpt: str


class SourceCardModel(BaseModel):
    source_id: str
    title: str
    filename: str | None = None
    source_url: str | None = None
    entity: str | None = None
    document_type: str | None = None
    pages: list[int] = Field(default_factory=list)
    pages_label: str | None = None
    primary_locator: str | None = None
    primary_excerpt: str = ""
    citations: list[SourceCitationModel] = Field(default_factory=list)
    count: int = 0


class AnswerMetaModel(BaseModel):
    markdown: str
    intent: str
    retrieval_query: str
    elapsed_ms: int
    citations_count: int
    used_llm: bool
    response_mode: str
    llm_label: str | None = None
    retrieval_backend: str | None = None
    primary_source_id: str | None = None
    primary_source_title: str | None = None


class ConfidenceModel(BaseModel):
    label: str
    score: float
    reasons: list[str]


class BootstrapModel(BaseModel):
    api_version: str
    product_title: str
    question_suggestions: list[str]
    categories: list[dict[str, str]]
    default_category: str
    sessions_enabled: bool
    rag_backend_ready: bool
    rag_backend_error: str | None = None
    rag_backend_mode: str = "offline"
    rag_backend_message: str | None = None
    recommended_frontend: str = "react"


class CorpusSourceModel(BaseModel):
    source_id: str
    title: str
    entity: str | None = None
    document_type: str | None = None
    source_url: str | None = None
    notes: str | None = None


class CorpusSectionModel(BaseModel):
    id: str
    label: str
    description: str
    sources_count: int
    example_questions: list[str] = Field(default_factory=list)
    sources: list[CorpusSourceModel] = Field(default_factory=list)


class GlossaryEntryModel(BaseModel):
    term: str
    category: str
    short_definition: str
    why_it_matters: str
    related_terms: list[str] = Field(default_factory=list)


class SavedResponseModel(BaseModel):
    key: str
    session_id: str
    response_id: str | None = None
    chat_title: str | None = None
    preview: str | None = None
    saved_at: str | None = None


class AskResponseModel(BaseModel):
    session: SessionDetailModel
    answer: AnswerMetaModel
    confidence: ConfidenceModel
    sources: list[SourceCardModel]
    structured_data: dict[str, Any]
    follow_up_questions: list[str]
    procedural_steps: list[str]
    answer_markdown: str
    confidence_label: str
    confidence_score: float
    confidence_reasons: list[str]
    elapsed_ms: int
    citations_count: int
    sources_grouped: list[SourceCardModel]
    retrieval_query: str
    intent: str
    used_llm: bool
    response_mode: str
    llm_label: str | None = None
    retrieval_backend: str | None = None
    primary_source_id: str | None = None
    primary_source_title: str | None = None


app = FastAPI(
    title="RAG Contratos Públicos API",
    version="0.4.0",
    description="API FastAPI para chats persistentes, exploração do corpus e perguntas ao motor RAG.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _index_metadata() -> dict[str, Any]:
    if not config.INDEX_METADATA_FILE.exists():
        return {}
    try:
        import json

        return json.loads(config.INDEX_METADATA_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _load_pipeline() -> Any:
    """Carrega o motor RAG apenas quando necessário.

    Prioriza retrieval vetorial quando o índice e o provider correspondente estão
    disponíveis. Caso contrário, mantém um fallback lexical local para evitar 503
    em ambiente de demo.
    """
    try:
        from src.embeddings import get_embeddings, get_embeddings_status, ollama_available
        from src.local_retrieval import load_local_chunks
        from src.rag_pipeline import RAGPipeline
    except Exception as exc:  # pragma: no cover - depende do ambiente local
        raise RuntimeError(
            "Dependências do backend RAG indisponíveis. "
            "Confirma langchain/sentence-transformers e o corpus local."
        ) from exc

    embedding_name, llm_name = config.get_model_names()
    embedding_status = get_embeddings_status(embedding_name)
    index_metadata = _index_metadata()

    vectorstore = None
    can_try_vector = config.CHROMA_DIR.exists() and any(config.CHROMA_DIR.iterdir()) and embedding_status.get("ready")
    if can_try_vector:
        built_provider = index_metadata.get("provider")
        built_model = index_metadata.get("model")
        provider_matches = not built_provider or built_provider == embedding_status.get("provider")
        model_matches = not built_model or built_model == embedding_status.get("model") or built_model == embedding_name
        if provider_matches and model_matches:
            try:
                from src.vector_store import load_vector_store

                embeddings = get_embeddings(embedding_name)
                vectorstore = load_vector_store(embeddings)
            except Exception:
                vectorstore = None

    llm = None
    if ollama_available(llm_name):
        try:
            from langchain_community.chat_models import ChatOllama

            llm = ChatOllama(
                model=llm_name,
                base_url=config.OLLAMA_BASE_URL,
                temperature=0.05,
                num_predict=260,
                timeout=config.OLLAMA_REQUEST_TIMEOUT,
            )
        except Exception:
            llm = None

    if vectorstore is None and not load_local_chunks():
        raise RuntimeError(
            "Sem índice vetorial utilizável e sem corpus local legível para fallback lexical."
        )

    return RAGPipeline(vectorstore=vectorstore, top_k=config.TOP_K, llm=llm)


@lru_cache(maxsize=1)
def _backend_probe() -> tuple[bool, str | None, str, str | None]:
    try:
        pipeline = _load_pipeline()
        if getattr(pipeline, "vectorstore", None) is not None:
            if getattr(pipeline, "llm", None) is not None:
                return True, None, "vector+llm", "Retrieval vetorial e síntese local disponíveis."
            return True, None, "vector", "Retrieval vetorial disponível; LLM opcional indisponível."
        return True, None, "lexical", "Modo documental local ativo; respostas continuam disponíveis sem dependência do Ollama."
    except Exception as exc:  # pragma: no cover - depende do ambiente local
        return False, str(exc), "offline", None



def _invalidate_backend_probe() -> None:
    _backend_probe.cache_clear()
    _load_pipeline.cache_clear()
    _index_metadata.cache_clear()



def _is_default_session_title(title: str | None) -> bool:
    normalized = (title or "").strip().lower()
    return normalized in {"nova sessão", "novo chat", "chat novo", "chat sem título", "novo"}



def _auto_title_from_query(query: str, *, max_length: int = 72) -> str:
    cleaned = " ".join((query or "").replace("\n", " ").split()).strip(" .:;,-")
    if not cleaned:
        return "Novo chat"
    return cleaned[:max_length].rstrip()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _message_entry(role: Literal["user", "assistant"], content: str, *, qa_result: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": role,
        "content": content,
        "created_at": _now_iso(),
    }
    if qa_result is not None:
        message["qa_result"] = qa_result
    return message



def _safe_preview(text: str | None, *, limit: int = 140) -> str | None:
    content = " ".join((text or "").split()).strip()
    if not content:
        return None
    if len(content) <= limit:
        return content
    return content[: limit - 1].rstrip() + "…"



def _pages_label(pages: list[int]) -> str | None:
    pages = sorted([p for p in pages if isinstance(p, int)])
    if not pages:
        return None
    if len(pages) == 1:
        return f"p. {pages[0]}"
    if len(pages) <= 4:
        joined = ", ".join(str(p) for p in pages)
        return f"pp. {joined}"
    return f"pp. {pages[0]}–{pages[-1]}"



def _locator_from_page(page: int | None) -> str | None:
    return f"p. {page}" if isinstance(page, int) else None



def _normalize_source_card(raw: dict[str, Any]) -> SourceCardModel:
    pages = [p for p in (raw.get("pages") or []) if isinstance(p, int)]
    citations: list[SourceCitationModel] = []
    for item in raw.get("citations") or []:
        if not isinstance(item, dict):
            continue
        page = item.get("page") if isinstance(item.get("page"), int) else None
        citations.append(
            SourceCitationModel(
                index=int(item.get("index") or 0),
                page=page,
                locator=_locator_from_page(page),
                chunk_id=str(item.get("chunk_id")) if item.get("chunk_id") else None,
                excerpt=_safe_preview(str(item.get("excerpt") or ""), limit=320) or "",
            )
        )

    primary_locator = citations[0].locator if citations else _pages_label(pages)
    primary_excerpt = _safe_preview(str(raw.get("primary_excerpt") or ""), limit=360) or ""

    return SourceCardModel(
        source_id=str(raw.get("source_id") or ""),
        title=str(raw.get("title") or raw.get("filename") or raw.get("source_id") or "Fonte"),
        filename=str(raw.get("filename")) if raw.get("filename") else None,
        source_url=str(raw.get("source_url")) if raw.get("source_url") else None,
        entity=str(raw.get("entity")) if raw.get("entity") else None,
        document_type=str(raw.get("document_type")) if raw.get("document_type") else None,
        pages=pages,
        pages_label=_pages_label(pages),
        primary_locator=primary_locator,
        primary_excerpt=primary_excerpt,
        citations=citations,
        count=int(raw.get("count") or len(citations)),
    )



def _session_to_summary(session: dict[str, Any]) -> SessionSummaryModel:
    messages = session.get("messages") or []
    last_message = messages[-1] if messages and isinstance(messages[-1], dict) else None
    return SessionSummaryModel(
        id=str(session.get("id") or ""),
        title=str(session.get("title") or "Novo chat"),
        created_at=str(session.get("created_at") or ""),
        updated_at=str(session.get("updated_at") or session.get("created_at") or ""),
        messages_count=len(messages),
        last_message_preview=_safe_preview((last_message or {}).get("content")),
    )



def _session_to_detail(session: dict[str, Any]) -> SessionDetailModel:
    messages = []
    for item in session.get("messages") or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or "assistant"
        if role not in {"user", "assistant"}:
            role = "assistant"
        messages.append(
            SessionMessageModel(
                role=role,
                content=item.get("content") or "",
                created_at=str(item.get("created_at") or "").strip() or None,
                qa_result=item.get("qa_result") if isinstance(item.get("qa_result"), dict) else None,
            )
        )
    return SessionDetailModel(
        id=str(session.get("id") or ""),
        title=str(session.get("title") or "Novo chat"),
        created_at=str(session.get("created_at") or ""),
        updated_at=str(session.get("updated_at") or session.get("created_at") or ""),
        active_source_id=str(session.get("active_source_id") or "").strip() or None,
        active_source_title=str(session.get("active_source_title") or "").strip() or None,
        messages=messages,
    )



def _normalize_question_key(value: str) -> str:
    return " ".join((value or "").lower().replace("?", " ").split())


FIELD_QUERY_PREFIXES = (
    "qual ",
    "quais ",
    "quem ",
    "onde ",
    "quando ",
    "existe ",
    "há ",
    "ha ",
    "tem ",
    "indica ",
    "diz ",
    "mostra ",
    "o procedimento ",
)


def _query_scope_aliases() -> tuple[str, ...]:
    aliases: set[str] = set()
    prefixes = [
        "município de ",
        "municipio de ",
        "município do ",
        "municipio do ",
        "unidade local de saúde de ",
        "unidade local de saude de ",
        "unidade local de saúde do ",
        "unidade local de saude do ",
        "serviços de ação social da ",
        "servicos de acao social da ",
        "universidade do ",
        "universidade de ",
    ]
    for record in load_source_registry().values():
        for raw in (record.entity, record.title):
            label = _normalize_question_key(str(raw or ""))
            if not label or len(label) < 4:
                continue
            aliases.add(label)
            for prefix in prefixes:
                if label.startswith(prefix):
                    tail = label[len(prefix):].strip()
                    if tail and len(tail) >= 3:
                        aliases.add(tail)
    return tuple(sorted(aliases, key=len, reverse=True))


def _query_mentions_specific_scope(query: str) -> bool:
    normalized = _normalize_question_key(query)
    if not normalized:
        return False
    return any(alias in normalized for alias in _query_scope_aliases())


def _looks_like_contextual_follow_up(query: str) -> bool:
    normalized = _normalize_question_key(query)
    if not normalized:
        return False
    analysis = analyze_query(query)
    if analysis.is_search_example or analysis.is_broad_listing:
        return False
    if _query_mentions_specific_scope(query):
        return False
    if analysis.needs_document_context:
        return True
    if any(normalized.startswith(prefix) for prefix in FIELD_QUERY_PREFIXES):
        return True
    return len(normalized.split()) <= 8


def _should_clear_document_context(query: str) -> bool:
    normalized = _normalize_question_key(query)
    if not normalized:
        return False
    switch_markers = ("outro procedimento", "outra fonte", "noutro procedimento", "novo procedimento")
    if any(marker in normalized for marker in switch_markers):
        return True
    return analyze_query(query).is_search_example and not _looks_like_contextual_follow_up(query)


def _get_session_active_source(session: dict[str, Any]) -> tuple[str | None, str | None]:
    source_id = str(session.get("active_source_id") or "").strip() or None
    source_title = str(session.get("active_source_title") or "").strip() or None
    return source_id, source_title


def _resolve_preferred_source_id(session: dict[str, Any], query: str, payload_source_id: str | None = None) -> str | None:
    explicit = str(payload_source_id or "").strip() or None
    if explicit:
        return explicit
    if _should_clear_document_context(query):
        return None
    active_source_id, _ = _get_session_active_source(session)
    if active_source_id and _looks_like_contextual_follow_up(query):
        return active_source_id
    return None


def _build_need_context_payload(session: dict[str, Any], query: str) -> tuple[dict[str, Any], AnswerMetaModel, ConfidenceModel, list[SourceCardModel], list[str], list[str]]:
    markdown = (
        "## Resposta\n"
        "Preciso de um procedimento concreto para responder sem saltar entre documentos.\n\n"
        "## Detalhes\n"
        "- Indica uma entidade, município ou procedimento específico.\n"
        "- Em alternativa, usa uma pergunta de procura como as sugestões da home.\n\n"
        "## Fontes usadas\n"
        "Sem fontes, porque ainda não foi fixado um procedimento ativo."
    )
    confidence = ConfidenceModel(
        label="baixa",
        score=0.0,
        reasons=["A pergunta é contextual, mas ainda não existe um procedimento ativo na conversa."],
    )
    answer = AnswerMetaModel(
        markdown=markdown,
        intent=analyze_query(query).intent,
        retrieval_query=query,
        elapsed_ms=0,
        citations_count=0,
        used_llm=False,
        response_mode="heuristic",
        llm_label=None,
        retrieval_backend=None,
        primary_source_id=None,
        primary_source_title=None,
    )
    follow_up_questions = list(config.QUESTION_SUGGESTIONS[:4])
    procedural_steps: list[str] = []

    qa_result = {
        "confidence": confidence.model_dump(),
        "answer": answer.model_dump(),
        "sources": [],
        "structured_data": {},
        "follow_up_questions": follow_up_questions,
        "procedural_steps": procedural_steps,
        "confidence_label": confidence.label,
        "confidence_score": confidence.score,
        "confidence_reasons": confidence.reasons,
        "elapsed_ms": 0,
        "citations_count": 0,
        "sources_grouped": [],
        "intent": answer.intent,
        "retrieval_query": answer.retrieval_query,
        "used_llm": False,
        "response_mode": answer.response_mode,
        "llm_label": None,
        "retrieval_backend": None,
        "primary_source_id": None,
        "primary_source_title": None,
    }
    session.setdefault("messages", [])
    session["messages"].append(_message_entry("user", query))
    session["messages"].append(_message_entry("assistant", markdown, qa_result=qa_result))
    if _is_default_session_title(session.get("title")):
        session["title"] = _auto_title_from_query(query)
    persisted = upsert_session(session)
    return persisted, answer, confidence, [], follow_up_questions, procedural_steps



def _dedupe_follow_up_questions(questions: list[Any], current_query: str) -> list[str]:
    seen = {_normalize_question_key(current_query)}
    kept: list[str] = []
    for item in questions or []:
        question = " ".join(str(item or "").split()).strip()
        if not question:
            continue
        key = _normalize_question_key(question)
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(question)
        if len(kept) >= 5:
            break
    return kept



def _derive_llm_label(result: Any) -> str | None:
    raw = getattr(result, "used_llm", None)
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    if raw is True:
        return "LLM"
    return None



def _derive_response_mode(result: Any) -> str:
    return "llm" if bool(getattr(result, "used_llm", False)) else "heuristic"


@app.on_event("startup")  # noqa: deprecated — substituir por lifespan quando migrar para FastAPI ≥ 0.95
def on_startup() -> None:
    config.ensure_directories()
    _invalidate_backend_probe()



# ─── Respostas guardadas (persistência no backend) ─────────────────────────────

@app.get("/saved", response_model=list[SavedResponseModel])
def api_list_saved() -> list[SavedResponseModel]:
    """Lista respostas guardadas com integridade referencial verificada."""
    return [SavedResponseModel(**item) for item in list_saved_responses()]


@app.post("/saved", response_model=SavedResponseModel, status_code=201)
def api_add_saved(payload: SavedResponseModel) -> SavedResponseModel:
    """Guarda uma resposta. Substitui se a key já existir."""
    item = add_saved_response(payload.model_dump())
    return SavedResponseModel(**item)


@app.delete("/saved/{key}")
def api_remove_saved(key: str) -> dict[str, bool]:
    """Remove um guardado pelo key."""
    removed = remove_saved_response(key)
    if not removed:
        raise HTTPException(status_code=404, detail="Guardado não encontrado.")
    return {"deleted": True}


@app.get("/health")
def health() -> dict[str, Any]:
    config.ensure_directories()
    chroma_exists = config.CHROMA_DIR.exists() and any(config.CHROMA_DIR.iterdir())
    rag_backend_ready, rag_backend_error, rag_backend_mode, rag_backend_message = _backend_probe()
    return {
        "status": "ok",
        "chroma_ready": chroma_exists,
        "rag_backend_ready": rag_backend_ready,
        "rag_backend_error": rag_backend_error,
        "rag_backend_mode": rag_backend_mode,
        "rag_backend_message": rag_backend_message,
        "sessions_file": str(config.SESSIONS_FILE),
        "sessions_count": len(list_sessions()),
        "api_version": app.version,
        "recommended_frontend": "react",
    }


@app.get("/diagnostics")
def diagnostics() -> dict[str, Any]:
    return {
        **health(),
        "manual_checks": [
            "GET /health devolve status ok e estado coerente do backend RAG",
            "GET /bootstrap devolve categorias e perguntas sugeridas",
            "GET /corpus/overview devolve catálogo navegável do corpus",
            "GET /glossary devolve termos do domínio público",
            "POST /sessions cria um chat persistente",
            "POST /sessions/{id}/ask devolve answer, confidence, sources e structured_data",
            "DELETE /sessions/{id} remove o chat sem deixar estado inválido",
        ],
    }


@app.get("/bootstrap", response_model=BootstrapModel)
def bootstrap() -> BootstrapModel:
    rag_backend_ready, rag_backend_error, rag_backend_mode, rag_backend_message = _backend_probe()
    return BootstrapModel(
        api_version=app.version,
        product_title="RAG para análise de contratos e avisos públicos",
        question_suggestions=list(config.QUESTION_SUGGESTIONS),
        categories=ALLOWED_CATEGORIES,
        default_category="todos",
        sessions_enabled=True,
        rag_backend_ready=rag_backend_ready,
        rag_backend_error=rag_backend_error,
        rag_backend_mode=rag_backend_mode,
        rag_backend_message=rag_backend_message,
        recommended_frontend="react",
    )


@app.get("/corpus/overview", response_model=list[CorpusSectionModel])
def corpus_overview() -> list[CorpusSectionModel]:
    return [CorpusSectionModel(**item) for item in build_corpus_overview()]


@app.get("/glossary", response_model=list[GlossaryEntryModel])
def glossary() -> list[GlossaryEntryModel]:
    payload = []
    for item in get_glossary_entries():
        row = dict(item)
        row["related_terms"] = list(row.get("related_terms") or [])
        payload.append(GlossaryEntryModel(**row))
    return payload


@app.get("/sessions", response_model=list[SessionSummaryModel])
def api_list_sessions() -> list[SessionSummaryModel]:
    return [_session_to_summary(session) for session in list_sessions()]


@app.post("/sessions", response_model=SessionDetailModel, status_code=201)
def api_create_session(payload: SessionCreateRequest) -> SessionDetailModel:
    session = create_session(title=payload.title.strip() or "Novo chat")
    return _session_to_detail(session)


@app.get("/sessions/{session_id}", response_model=SessionDetailModel)
def api_get_session(session_id: str) -> SessionDetailModel:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat não encontrado.")
    return _session_to_detail(session)


@app.patch("/sessions/{session_id}", response_model=SessionDetailModel)
def api_update_session(session_id: str, payload: SessionUpdateRequest) -> SessionDetailModel:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat não encontrado.")
    session["title"] = payload.title.strip()
    session = upsert_session(session)
    return _session_to_detail(session)


@app.delete("/sessions/{session_id}")
def api_delete_session(session_id: str) -> dict[str, bool]:
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat não encontrado.")
    return {"deleted": True}


@app.post("/sessions/{session_id}/ask", response_model=AskResponseModel)
def api_ask(session_id: str, payload: AskRequest) -> AskResponseModel:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat não encontrado.")

    preferred_source_id = _resolve_preferred_source_id(session, payload.query, payload.preferred_source_id)
    if _looks_like_contextual_follow_up(payload.query) and not preferred_source_id and not _query_mentions_specific_scope(payload.query):
        session, answer, confidence, sources, follow_up_questions, procedural_steps = _build_need_context_payload(session, payload.query)
        return AskResponseModel(
            session=_session_to_detail(session),
            answer=answer,
            confidence=confidence,
            sources=sources,
            structured_data={},
            follow_up_questions=follow_up_questions,
            procedural_steps=procedural_steps,
            answer_markdown=answer.markdown,
            confidence_label=confidence.label,
            confidence_score=confidence.score,
            confidence_reasons=confidence.reasons,
            elapsed_ms=answer.elapsed_ms,
            citations_count=answer.citations_count,
            sources_grouped=sources,
            retrieval_query=answer.retrieval_query,
            intent=answer.intent,
            used_llm=answer.used_llm,
            response_mode=answer.response_mode,
            llm_label=answer.llm_label,
            retrieval_backend=answer.retrieval_backend,
            primary_source_id=answer.primary_source_id,
            primary_source_title=answer.primary_source_title,
        )

    try:
        pipeline = _load_pipeline()
        result = pipeline.ask(
            payload.query,
            top_k=payload.top_k,
            category=payload.category,
            preferred_source_id=preferred_source_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger("rag_api").error("RAG pipeline error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Backend RAG indisponível neste ambiente. Confirma o corpus local e o estado do Ollama.",
        ) from exc

    _log.info(
        "ask query=%r intent=%s confidence=%s elapsed_ms=%s retrieval=%s source=%s",
        payload.query[:80],
        getattr(result.analysis, "intent", "?"),
        getattr(result, "confidence_label", "?"),
        getattr(result, "elapsed_ms", "?"),
        getattr(result, "retrieval_backend", "?"),
        getattr(result, "primary_source_id", "?"),
    )
    sources = [_normalize_source_card(item) for item in (result.sources_grouped or []) if isinstance(item, dict)]
    follow_up_questions = _dedupe_follow_up_questions(getattr(result, "follow_up_questions", []) or [], payload.query)
    response_mode = _derive_response_mode(result)
    llm_label = _derive_llm_label(result)
    procedural_steps = [str(step).strip() for step in getattr(result, "procedural_steps", []) or [] if str(step).strip()]

    primary_source_id = str(getattr(result, "primary_source_id", "") or "").strip() or None
    primary_source_title = str(getattr(result, "primary_source_title", "") or "").strip() or None
    if primary_source_id:
        session["active_source_id"] = primary_source_id
        session["active_source_title"] = primary_source_title
    elif _should_clear_document_context(payload.query):
        session.pop("active_source_id", None)
        session.pop("active_source_title", None)

    answer = AnswerMetaModel(
        markdown=result.answer_markdown,
        intent=result.analysis.intent,
        retrieval_query=result.retrieval_query,
        elapsed_ms=result.elapsed_ms,
        citations_count=result.citations_count,
        used_llm=bool(result.used_llm),
        response_mode=response_mode,
        llm_label=llm_label,
        retrieval_backend=getattr(result, "retrieval_backend", None),
        primary_source_id=primary_source_id,
        primary_source_title=primary_source_title,
    )
    confidence = ConfidenceModel(
        label=result.confidence_label,
        score=result.confidence_score,
        reasons=result.confidence_reasons,
    )

    qa_result = {
        "confidence": confidence.model_dump(),
        "answer": answer.model_dump(),
        "sources": [item.model_dump() for item in sources],
        "structured_data": result.structured_data,
        "follow_up_questions": follow_up_questions,
        "procedural_steps": procedural_steps,
        "confidence_label": result.confidence_label,
        "confidence_score": result.confidence_score,
        "confidence_reasons": result.confidence_reasons,
        "elapsed_ms": result.elapsed_ms,
        "citations_count": result.citations_count,
        "sources_grouped": [item.model_dump() for item in sources],
        "intent": result.analysis.intent,
        "retrieval_query": result.retrieval_query,
        "used_llm": bool(result.used_llm),
        "response_mode": response_mode,
        "llm_label": llm_label,
        "retrieval_backend": getattr(result, "retrieval_backend", None),
        "primary_source_id": primary_source_id,
        "primary_source_title": primary_source_title,
    }
    session.setdefault("messages", [])
    session["messages"].append(_message_entry("user", payload.query))
    session["messages"].append(_message_entry("assistant", result.answer_markdown, qa_result=qa_result))
    if _is_default_session_title(session.get("title")):
        session["title"] = _auto_title_from_query(payload.query)
    session = upsert_session(session)

    return AskResponseModel(
        session=_session_to_detail(session),
        answer=answer,
        confidence=confidence,
        sources=sources,
        structured_data=result.structured_data,
        follow_up_questions=follow_up_questions,
        procedural_steps=procedural_steps,
        answer_markdown=result.answer_markdown,
        confidence_label=result.confidence_label,
        confidence_score=result.confidence_score,
        confidence_reasons=result.confidence_reasons,
        elapsed_ms=result.elapsed_ms,
        citations_count=result.citations_count,
        sources_grouped=sources,
        retrieval_query=result.retrieval_query,
        intent=result.analysis.intent,
        used_llm=bool(result.used_llm),
        response_mode=response_mode,
        llm_label=llm_label,
        retrieval_backend=getattr(result, "retrieval_backend", None),
        primary_source_id=primary_source_id,
        primary_source_title=primary_source_title,
    )
