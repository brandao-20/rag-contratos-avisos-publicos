"""Análise de intenção, guardrails e expansão de query para RAG documental."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from . import config

STOPWORDS = {
    "a", "o", "os", "as", "de", "do", "da", "dos", "das", "e", "ou", "para", "por", "em", "no", "na", "nos", "nas",
    "um", "uma", "uns", "umas", "qual", "quais", "que", "como", "onde", "quando", "quanto", "quanta", "há", "ha",
}

IRRELEVANT_PATTERNS = (
    "quem vai ganhar",
    "melhor empresa",
    "vale a pena concorrer",
    "é legal",
    "e legal",
    "corrup",
    "previs",
    "mercado imobili",
    "euribor",
    "tempo em lisboa",
    "melhor zona",
    "opini",
    "recomenda",
)

SEARCH_EXAMPLE_PATTERNS = (
    "procura um procedimento",
    "mostra um procedimento",
    "encontra um procedimento",
    "indica um procedimento",
    "da-me um procedimento",
    "dá-me um procedimento",
    "procura um aviso",
    "mostra um aviso",
)

DEICTIC_PATTERNS = (
    "neste procedimento",
    "neste contrato",
    "neste aviso",
    "deste procedimento",
    "deste contrato",
    "deste aviso",
    "este procedimento",
    "este contrato",
    "este aviso",
)

BROAD_LISTING_PATTERNS = (
    "que contratos ativos existem",
    "quais contratos ativos existem",
    "que contratos existem",
    "quais contratos existem",
    "que avisos existem",
    "quais avisos existem",
    "lista de contratos",
    "lista de avisos",
    "todos os contratos",
    "todos os avisos",
)

PROCEDURAL_PATTERNS = (
    "como ",
    "quais os passos",
    "quais são os passos",
    "o que devo verificar",
    "o que verificar",
    "como participar",
    "como apresentar",
    "como cumprir",
    "como submeter",
)


@dataclass(frozen=True)
class QueryAnalysis:
    intent: str
    must_terms: tuple[str, ...] = field(default_factory=tuple)
    preferred_terms: tuple[str, ...] = field(default_factory=tuple)
    answer_mode: str = "grounded"
    reason: str = ""
    is_procedural: bool = False
    is_search_example: bool = False
    needs_document_context: bool = False
    is_broad_listing: bool = False


def norm(text: str) -> str:
    s = unicodedata.normalize("NFD", text or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower().strip()


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-zA-Zà-ÿ0-9%\.\-/]{2,}", norm(text))
    return [t for t in toks if t not in STOPWORDS]


def should_force_dont_know(query: str) -> bool:
    qn = norm(query)
    return any(term in qn for term in IRRELEVANT_PATTERNS)


def is_procedural_query(query: str) -> bool:
    qn = norm(query)
    return any(qn.startswith(pattern) or pattern in qn for pattern in PROCEDURAL_PATTERNS)


def is_search_example_query(query: str) -> bool:
    qn = norm(query)
    return any(qn.startswith(pattern) for pattern in SEARCH_EXAMPLE_PATTERNS)


def needs_document_context(query: str) -> bool:
    qn = norm(query)
    return any(pattern in qn for pattern in DEICTIC_PATTERNS)


def is_broad_listing_query(query: str) -> bool:
    qn = norm(query)
    return any(pattern in qn for pattern in BROAD_LISTING_PATTERNS)


def _contains_any(text: str, items: Iterable[str]) -> bool:
    return any(norm(i) in text for i in items)


def classify_intent(query: str) -> str:
    qn = norm(query)
    if _contains_any(qn, config.INTENT_SYNONYMS["caucao"]):
        return "caucao"
    if _contains_any(qn, config.INTENT_SYNONYMS["cpv"]):
        return "cpv"
    if _contains_any(qn, config.INTENT_SYNONYMS["lotes"]):
        return "lotes"
    if _contains_any(qn, config.INTENT_SYNONYMS["prazo"]):
        return "prazo"
    if _contains_any(qn, config.INTENT_SYNONYMS["valor"]):
        return "valor"
    if _contains_any(qn, config.INTENT_SYNONYMS["criterios"]):
        return "criterios"
    if _contains_any(qn, config.INTENT_SYNONYMS["requisitos"]):
        return "requisitos"
    if _contains_any(qn, config.INTENT_SYNONYMS["entidade"]):
        return "entidade"
    if _contains_any(qn, config.INTENT_SYNONYMS["local"]):
        return "local"
    if _contains_any(qn, config.INTENT_SYNONYMS["legal"]):
        return "legal"
    return "objeto"


def analyze_query(query: str) -> QueryAnalysis:
    intent = classify_intent(query)
    preferred_terms = list(config.INTENT_SYNONYMS.get(intent, []))
    must_terms: list[str] = []

    if intent == "prazo":
        must_terms = ["prazo", "propostas"]
    elif intent == "valor":
        must_terms = ["preço base", "eur"]
    elif intent == "criterios":
        must_terms = ["critério", "adjudicação"]
    elif intent == "requisitos":
        must_terms = ["habilitação", "documentos de habilitação"]
    elif intent == "entidade":
        must_terms = ["entidade adjudicante"]
    elif intent == "local":
        must_terms = ["local"]
    elif intent == "legal":
        must_terms = ["artigo", "lei"]
    elif intent == "caucao":
        must_terms = ["prestação de caução"]
    elif intent == "cpv":
        must_terms = ["cpv", "vocabulário principal"]
    elif intent == "lotes":
        must_terms = ["procedimento com lotes"]
    else:
        must_terms = ["designação do contrato", "descrição"]

    procedural = is_procedural_query(query)
    search_example = is_search_example_query(query)
    contextual = needs_document_context(query)
    broad_listing = is_broad_listing_query(query)
    answer_mode = "procedural" if procedural else "grounded"

    return QueryAnalysis(
        intent=intent,
        must_terms=tuple(must_terms),
        preferred_terms=tuple(preferred_terms),
        answer_mode=answer_mode,
        reason=f"intent:{intent}",
        is_procedural=procedural,
        is_search_example=search_example,
        needs_document_context=contextual,
        is_broad_listing=broad_listing,
    )


def augment_query_for_retrieval(query: str, analysis: QueryAnalysis | None = None) -> str:
    analysis = analysis or analyze_query(query)
    parts: list[str] = [query.strip()]

    for item in analysis.must_terms[:6]:
        parts.append(item)
    for item in analysis.preferred_terms[:8]:
        parts.append(item)

    if analysis.intent == "objeto":
        parts.extend(["designação do contrato", "descrição", "objeto principal", "CPV"])
    elif analysis.intent == "prazo":
        parts.extend(["prazo para apresentação das propostas", "prazo de execução do contrato", "data limite", "prazo durante o qual os concorrentes são obrigados a manter as respetivas propostas"])
    elif analysis.intent == "valor":
        parts.extend(["preço base", "valor do preço base do procedimento", "preço base s/IVA", "EUR"])
    elif analysis.intent == "requisitos":
        parts.extend(["habilitação para o exercício da atividade profissional", "documentos de habilitação", "alvará"])
    elif analysis.intent == "criterios":
        parts.extend(["critério de adjudicação", "monofator", "multifator", "ponderação"])
    elif analysis.intent == "caucao":
        parts.extend(["prestação de caução", "percentagem", "garantia exigida"])
    elif analysis.intent == "cpv":
        parts.extend(["CPV", "vocabulário principal", "vocabulário comum para os contratos públicos"])
    elif analysis.intent == "lotes":
        parts.extend(["procedimento com lotes", "lotes", "não", "sim"])

    seen = set()
    unique_parts: list[str] = []
    for part in parts:
        normalized = norm(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_parts.append(part)
    return " | ".join(unique_parts)
