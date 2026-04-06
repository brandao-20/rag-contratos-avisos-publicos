"""Construção de respostas com confiança, extração direta e fallback com citações."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .query_analysis import QueryAnalysis, should_force_dont_know
from .source_registry import enrich_metadata


@dataclass
class RetrievalChunk:
    text: str
    score: float
    distance: float | None
    meta: dict[str, Any]
    lex: int = 0
    coverage: float = 0.0
    rank: int = 0
    blended: float = 0.0


@dataclass
class ConfidenceDecision:
    label: str
    score: float
    reasons: list[str] = field(default_factory=list)
    should_answer: bool = True
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)


@dataclass
class AnswerPackage:
    answer_markdown: str
    cited_indexes: list[int]
    confidence: ConfidenceDecision
    follow_up_questions: list[str]
    used_llm: bool
    retrieval_query: str
    procedural_steps: list[str] = field(default_factory=list)


@dataclass
class DirectExtraction:
    answer_markdown: str
    cited_indexes: list[int]
    confidence: ConfidenceDecision
    procedural_steps: list[str] = field(default_factory=list)


@dataclass
class FieldCandidate:
    value: str
    citation_idx: int
    chunk: RetrievalChunk
    field_key: str
    score: float


FIELD_PATTERNS = {
    "objeto": [
        r"Designa[cç][aã]o do contrato:\s*([^\n]+)",
        r"Sum[áa]rio:\s*([^\n]+)",
        r"Descri[cç][aã]o:\s*([^\n]+)",
    ],
    "prazo": [
        r"Prazo para apresenta[cç][aã]o das propostas:\s*([^\n]+)",
        r"Prazo de candidatura\s*[:\-]\s*([^\n]+)",
        r"aberto pelo prazo de\s*([^\.\n]+)",
    ],
    "prazo_exec": [
        r"Prazo de execu[cç][aã]o do contrato:\s*([^\n]+)",
        r"Prazo de validade:\s*([^\n]+)",
    ],
    "valor": [
        r"Valor do pre[cç]o base do procedimento:\s*([\d\.,]+\s*EUR)",
        r"Pre[cç]o base s/IVA:\s*([\d\.,]+\s*EUR)",
        r"pre[cç]o base[^\n]*?([\d\.,]+\s*EUR)",
    ],
    "criterios": [
        r"Crit[ée]rio de adjudica[cç][aã]o[^\n]*:\s*([^\n]+)",
        r"Monofator:\s*([^\n]+)",
        r"Multifator:\s*([^\n]+)",
    ],
    "requisitos": [
        r"Documentos de habilita[cç][aã]o:\s*([^\n]+)",
        r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*([^\n]+)",
        r"Requisitos de admiss[aã]o[^:]*:\s*([^\n]+)",
    ],
    "entidade": [
        r"Designa[cç][aã]o da entidade adjudicante:\s*([^\n]+)",
        r"Emitente:\s*([^\n]+)",
    ],
    "caucao": [
        r"Presta[cç][aã]o de cau[cç][aã]o:\s*(Sim|N[aã]o|[^\n]+)",
        r"Garantia exigida:\s*([^\n]+)",
    ],
    "percentagem_caucao": [r"Percentagem:\s*([\d]+%)"],
    "cpv": [
        r"Vocabul[aá]rio Principal:\s*(\d{8}[^\n]*)",
        r"CPV[:\s]+(\d{8}[^\n]*)",
    ],
    "lotes": [
        r"Procedimento com lotes\?\s*(Sim|N[aã]o)",
        r"Divis[aã]o em lotes:\s*(Sim|N[aã]o)",
    ],
    "local": [
        r"Local da execu[cç][aã]o do contrato:\s*([^\n]+)",
        r"Local de trabalho:\s*([^\n]+)",
        r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO \(PROCEDIMENTO\)\s*([^\n]+)",
    ],
}


SECTION_NOISE = re.compile(
    r"\b(?:prestação de caução|prestacao de caucao|descrição da garantia exigida|documentos de habilitação|habilit[aã]ção para o exerc[ií]cio|condições de apresentação|local da execução do contrato|plataforma eletr[oó]nica|crit[ée]rio de adjudica[cç][aã]o)\b",
    flags=re.IGNORECASE,
)


DATE_TIME_RE = re.compile(r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{4}(?:\s+\d{1,2}:\d{2})?\b")



def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()



def _clean_value(value: str, *, max_length: int = 260) -> str:
    text = re.sub(r"\s+", " ", (value or "")).strip(" .;:-")
    if not text:
        return ""
    if SECTION_NOISE.search(text):
        text = SECTION_NOISE.split(text, maxsplit=1)[0].strip(" .;:-")
    text = re.split(r"\s{2,}|\s(?=\d{1,2}\s*[-–]\s*[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ])", text, maxsplit=1)[0].strip()
    if len(text) > max_length:
        text = text[:max_length].rstrip() + "…"
    return text



def _lexical_overlap(query: str, text: str) -> int:
    q_tokens = {t for t in re.findall(r"[\w%\-]{3,}", _norm(query))}
    t_tokens = {t for t in re.findall(r"[\w%\-]{3,}", _norm(text))}
    return len(q_tokens & t_tokens)



def _coverage(query: str, text: str, required_terms: Sequence[str]) -> float:
    joined = _norm(text)
    if not required_terms:
        return 1.0
    matched = [term for term in required_terms if _norm(term) in joined]
    return len(matched) / len(required_terms)



def normalize_chunks(query: str, docs: Iterable[Any], required_terms: Sequence[str]) -> list[RetrievalChunk]:
    out: list[RetrievalChunk] = []
    for rank, doc in enumerate(docs, start=1):
        meta = enrich_metadata(getattr(doc, "metadata", {}) or {})
        distance = meta.get("distance")
        if distance is not None:
            try:
                distance = float(distance)
            except Exception:
                distance = None
        score = 1.0 / (1.0 + distance) if distance is not None else 1.0 / rank
        text = getattr(doc, "page_content", "") or ""
        lex = _lexical_overlap(query, text)
        coverage = _coverage(query, text, required_terms)
        blended = 0.50 * min(score, 1.0) + 0.30 * min(lex / 8.0, 1.0) + 0.20 * coverage
        out.append(
            RetrievalChunk(
                text=text,
                score=score,
                distance=distance,
                meta=meta,
                lex=lex,
                coverage=coverage,
                rank=rank,
                blended=blended,
            )
        )
    out.sort(key=lambda ch: (ch.blended, ch.coverage, ch.lex, ch.score), reverse=True)
    return out



def evaluate_confidence(query: str, analysis: QueryAnalysis, chunks: Sequence[RetrievalChunk]) -> ConfidenceDecision:
    if should_force_dont_know(query):
        return ConfidenceDecision(
            label="baixa",
            score=0.0,
            reasons=["A pergunta pede recomendação, opinião ou previsão fora do suporte documental do corpus."],
            should_answer=False,
        )
    if not chunks:
        return ConfidenceDecision(
            label="baixa",
            score=0.0,
            reasons=["Sem evidência recuperada."],
            should_answer=False,
        )

    top = list(chunks[:4])
    joined = "\n".join(ch.text for ch in top)
    joined_norm = _norm(joined)
    matched = [t for t in analysis.must_terms if _norm(t) in joined_norm]
    missing = [t for t in analysis.must_terms if _norm(t) not in joined_norm]

    avg_cov = sum(ch.coverage for ch in top) / max(1, len(top))
    top_lex = max(ch.lex for ch in top)
    top_score = max(ch.score for ch in top)
    blended = max(ch.blended for ch in top)

    reasons: list[str] = []
    should_answer = True
    score = 0.40 * avg_cov + 0.25 * min(top_score, 1.0) + 0.20 * min(top_lex / 7.0, 1.0) + 0.15 * blended

    if analysis.intent == "prazo":
        if re.search(r"prazo para apresenta[cç][aã]o das propostas:\s*[^\n]+", joined_norm):
            score += 0.28
        elif DATE_TIME_RE.search(joined_norm):
            score += 0.18
        else:
            reasons.append("A evidência recuperada não mostra um prazo de apresentação suficientemente explícito.")
    elif analysis.intent == "valor":
        if re.search(r"(?:valor do )?pre[cç]o base do procedimento:\s*[\d\.,]+\s*eur", joined_norm) or re.search(r"pre[cç]o base s/iva:\s*[\d\.,]+\s*eur", joined_norm):
            score += 0.30
        else:
            reasons.append("A evidência não mostra um valor base suficientemente explícito.")
    elif analysis.intent == "criterios":
        if "critério de adjudicação" in joined_norm or "criterio de adjudicacao" in joined_norm:
            score += 0.24
        if "monofator" in joined_norm or "multifator" in joined_norm:
            score += 0.10
    elif analysis.intent == "requisitos":
        if "documentos de habilitação" in joined_norm or "habilitação para o exercício da atividade profissional" in joined_norm or "alvará" in joined_norm or "alvara" in joined_norm:
            score += 0.24
    elif analysis.intent == "entidade":
        if "designação da entidade adjudicante" in joined_norm or "emitente:" in joined_norm:
            score += 0.28
    elif analysis.intent == "local":
        if "local da execução do contrato" in joined_norm or "local de trabalho:" in joined_norm:
            score += 0.24
    elif analysis.intent == "caucao":
        if "prestação de caução:" in joined_norm or "prestacao de caucao:" in joined_norm:
            score += 0.34
        else:
            reasons.append("A evidência não mostra claramente a prestação de caução.")
    elif analysis.intent == "cpv":
        if "vocabulário principal:" in joined_norm or "vocabulário comum para os contratos públicos" in joined_norm or re.search(r"\b\d{8}\b", joined_norm):
            score += 0.34
        else:
            reasons.append("A evidência não mostra claramente o código CPV.")
    elif analysis.intent == "lotes":
        if "procedimento com lotes?" in joined_norm or "divisão em lotes" in joined_norm:
            score += 0.30
    else:
        if "designação do contrato:" in joined_norm or "sumário:" in joined_norm or "descricao:" in joined_norm or "descrição:" in joined_norm:
            score += 0.20

    if not matched and analysis.must_terms:
        reasons.append("Os termos obrigatórios da intenção não aparecem de forma suficientemente explícita na evidência principal.")
        if analysis.intent not in {"cpv", "caucao", "prazo", "valor"}:
            should_answer = False

    if score < 0.38:
        should_answer = False
        reasons.append("Cobertura e alinhamento lexical insuficientes para responder com segurança.")

    score = max(0.0, min(score, 0.97))
    if score >= 0.80 and should_answer:
        label = "alta"
    elif score >= 0.56 and should_answer:
        label = "média"
    else:
        label = "baixa"

    if label == "alta" and not reasons:
        reasons.append("Os campos relevantes surgem de forma explícita e coerente nas fontes recuperadas.")
    elif label == "média" and not reasons:
        reasons.append("Existe suporte documental útil, mas nem todos os campos aparecem de forma totalmente explícita.")
    elif label == "baixa" and not reasons:
        reasons.append("A evidência é parcial ou insuficiente para responder com segurança.")

    return ConfidenceDecision(
        label=label,
        score=round(score, 3),
        reasons=reasons,
        should_answer=should_answer,
        matched_terms=matched,
        missing_terms=missing,
    )



def _citation_line(idx: int, ch: RetrievalChunk) -> str:
    page = ch.meta.get("page")
    loc = f"p.{page}" if page is not None else "texto"
    return f"[{idx}] {ch.meta.get('source_title') or ch.meta.get('source_file')} ({loc})"



def _search(patterns: Sequence[str], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            return match
    return None



def _boost_for_value(field_key: str, value: str) -> float:
    raw = _norm(value)
    if field_key == "prazo":
        return 0.35 if DATE_TIME_RE.search(raw) else 0.18
    if field_key == "valor":
        return 0.32 if "eur" in raw else 0.16
    if field_key == "cpv":
        return 0.32 if re.search(r"\b\d{8}\b", raw) else 0.15
    if field_key == "lotes":
        return 0.20 if raw in {"sim", "não", "nao"} else 0.08
    if field_key == "caucao":
        return 0.28 if raw in {"sim", "não", "nao"} or "%" in raw else 0.12
    return 0.08



def _find_best_field_candidate(chunks: Sequence[RetrievalChunk], field_key: str) -> FieldCandidate | None:
    patterns = FIELD_PATTERNS.get(field_key) or []
    candidates: list[FieldCandidate] = []
    for idx, ch in enumerate(chunks[:8], start=1):
        source_bonus = 0.02 if ch.meta.get("page") == 1 else 0.0
        for pattern in patterns:
            match = re.search(pattern, ch.text or "", flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if not match:
                continue
            value = _clean_value(match.group(1), max_length=220 if field_key != "criterios" else 280)
            if not value:
                continue
            score = ch.blended + _boost_for_value(field_key, value) + source_bonus
            candidates.append(FieldCandidate(value=value, citation_idx=idx, chunk=ch, field_key=field_key, score=score))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.score, item.chunk.coverage, item.chunk.lex), reverse=True)
    return candidates[0]



def _build_procedural_steps(query: str, analysis: QueryAnalysis, chunks: Sequence[RetrievalChunk]) -> list[str]:
    if not analysis.is_procedural or not chunks:
        return []

    objeto = _find_best_field_candidate(chunks, "objeto")
    valor = _find_best_field_candidate(chunks, "valor")
    prazo = _find_best_field_candidate(chunks, "prazo")
    prazo_exec = _find_best_field_candidate(chunks, "prazo_exec")
    requisitos = _find_best_field_candidate(chunks, "requisitos")
    criterios = _find_best_field_candidate(chunks, "criterios")
    caucao = _find_best_field_candidate(chunks, "caucao")
    cpv = _find_best_field_candidate(chunks, "cpv")
    lotes = _find_best_field_candidate(chunks, "lotes")
    local = _find_best_field_candidate(chunks, "local")

    steps: list[str] = []
    steps.append(
        f"Confirma primeiro o objeto e o enquadramento do procedimento{': ' + objeto.value if objeto else ''}."
    )

    financial_bits = []
    if valor:
        financial_bits.append(f"preço base {valor.value}")
    if cpv:
        financial_bits.append(f"CPV {cpv.value}")
    if lotes:
        financial_bits.append(f"lotes: {lotes.value}")
    if financial_bits:
        steps.append("Valida os elementos económicos e estruturais do procedimento: " + "; ".join(financial_bits) + ".")

    if prazo or prazo_exec:
        timeline_bits = []
        if prazo:
            timeline_bits.append(f"prazo de apresentação {prazo.value}")
        if prazo_exec:
            timeline_bits.append(f"prazo de execução/validade {prazo_exec.value}")
        steps.append("Fecha a componente temporal antes de avançar: " + "; ".join(timeline_bits) + ".")

    if requisitos:
        steps.append(f"Revê os requisitos e documentos de habilitação mencionados: {requisitos.value}.")

    closing_bits = []
    if criterios:
        closing_bits.append(f"critérios: {criterios.value}")
    if caucao:
        closing_bits.append(f"caução/garantia: {caucao.value}")
    if local:
        closing_bits.append(f"local de execução: {local.value}")
    if closing_bits:
        steps.append("Verifica as condições finais do procedimento: " + "; ".join(closing_bits) + ".")

    deduped: list[str] = []
    seen = set()
    for step in steps:
        key = _norm(step)
        if key and key not in seen:
            seen.add(key)
            deduped.append(step)
        if len(deduped) >= 5:
            break
    return deduped



def _append_steps_block(markdown: str, steps: Sequence[str]) -> str:
    if not steps:
        return markdown
    lines = "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))
    return f"{markdown}\n\n## Passos sugeridos\n{lines}"



def _direct_extraction(query: str, analysis: QueryAnalysis, chunks: Sequence[RetrievalChunk]) -> DirectExtraction | None:
    if not chunks:
        return None

    intent = analysis.intent
    answer = None
    details = None
    confidence = None
    candidate: FieldCandidate | None = None

    if intent == "prazo":
        candidate = _find_best_field_candidate(chunks, "prazo")
        if candidate:
            answer = f"## Resposta\nCom base na fonte principal recuperada, o prazo para apresentação das propostas é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nA resposta foi extraída diretamente do campo de prazo presente no procedimento mais relevante para a pergunta."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrado um campo explícito de prazo na fonte principal."], True)
    elif intent == "valor":
        candidate = _find_best_field_candidate(chunks, "valor")
        if candidate:
            answer = f"## Resposta\nO preço base identificado no procedimento é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nO montante foi extraído diretamente do campo de preço base do procedimento recuperado."
            confidence = ConfidenceDecision("alta", 0.90, ["Foi encontrado um montante explícito associado ao preço base."], True)
    elif intent == "caucao":
        candidate = _find_best_field_candidate(chunks, "caucao")
        if candidate:
            extra = _find_best_field_candidate(chunks, "percentagem_caucao")
            raw = _norm(candidate.value)
            if raw in {"sim", "nao", "não"}:
                text = "Sim, o procedimento prevê prestação de caução" if raw == "sim" else "Não, o procedimento não prevê prestação de caução"
            else:
                text = f"O procedimento refere prestação de caução nos seguintes termos: **{candidate.value}**"
            if extra:
                text += f". A percentagem indicada é **{extra.value}** [{extra.citation_idx}]"
            answer = f"## Resposta\n{text} [{candidate.citation_idx}]."
            details = "## Detalhes\nA resposta foi construída a partir do campo explícito de caução/garantia encontrado na fonte principal."
            confidence = ConfidenceDecision("alta", 0.90, ["Foi encontrado um campo explícito sobre caução ou garantia exigida."], True)
    elif intent == "cpv":
        candidate = _find_best_field_candidate(chunks, "cpv")
        if candidate:
            answer = f"## Resposta\nO código CPV identificado no procedimento é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nO código foi extraído diretamente do campo de Vocabulário Principal/CPV."
            confidence = ConfidenceDecision("alta", 0.92, ["Foi encontrado um código CPV explícito no documento."], True)
    elif intent == "criterios":
        candidate = _find_best_field_candidate(chunks, "criterios")
        if candidate:
            answer = f"## Resposta\nNos documentos recuperados, o critério de adjudicação indicado é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nA formulação foi extraída da secção explícita de critério de adjudicação do procedimento mais relevante."
            confidence = ConfidenceDecision("média", 0.79, ["Foi encontrada a secção explícita de critério de adjudicação."], True)
    elif intent == "entidade":
        candidate = _find_best_field_candidate(chunks, "entidade")
        if candidate:
            answer = f"## Resposta\nA entidade adjudicante ou emitente identificada é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nA entidade foi extraída diretamente do cabeçalho institucional do documento recuperado."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrada uma designação explícita da entidade adjudicante/emitente."], True)
    elif intent == "local":
        candidate = _find_best_field_candidate(chunks, "local")
        if candidate:
            answer = f"## Resposta\nO local de execução identificado é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nO local foi extraído da secção de execução/local de trabalho do documento mais relevante."
            confidence = ConfidenceDecision("média", 0.79, ["Foi encontrada uma secção explícita sobre o local de execução."], True)
    elif intent == "requisitos":
        candidate = _find_best_field_candidate(chunks, "requisitos")
        if candidate:
            answer = f"## Resposta\nOs requisitos ou documentos de habilitação identificados são **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nA resposta foi extraída diretamente da secção de habilitação/documentos de habilitação do documento recuperado."
            confidence = ConfidenceDecision("média", 0.77, ["Foi encontrada uma secção explícita de habilitação/requisitos."], True)
    elif intent == "lotes":
        candidate = _find_best_field_candidate(chunks, "lotes")
        if candidate:
            raw = _norm(candidate.value)
            sentence = "O procedimento está organizado em lotes" if raw == "sim" else "O procedimento não está organizado em lotes"
            answer = f"## Resposta\n{sentence} [{candidate.citation_idx}]."
            details = "## Detalhes\nA resposta foi extraída diretamente do campo relativo à divisão em lotes."
            confidence = ConfidenceDecision("alta", 0.89, ["Foi encontrado um campo explícito sobre a existência de lotes."], True)
    else:
        candidate = _find_best_field_candidate(chunks, "objeto")
        if candidate:
            answer = f"## Resposta\nO objeto ou designação identificado no procedimento é **{candidate.value}** [{candidate.citation_idx}]."
            details = "## Detalhes\nA formulação foi extraída diretamente do campo de designação/descrição do contrato ou do sumário do aviso."
            confidence = ConfidenceDecision("alta", 0.85, ["Foi encontrada uma descrição explícita do objeto do procedimento."], True)

    if answer and details and confidence and candidate:
        source = candidate.chunk.meta.get("source_title") or candidate.chunk.meta.get("source_file") or "Fonte"
        page = candidate.chunk.meta.get("page")
        locator = f"p.{page}" if page is not None else "texto"
        procedural_steps = _build_procedural_steps(query, analysis, chunks)
        markdown = (
            f"{answer}\n\n{details}\n\n"
            f"## Fontes usadas\n[{candidate.citation_idx}] {source} ({locator})\n\n"
            "Confirmar sempre a informação na fonte oficial."
        )
        markdown = _append_steps_block(markdown, procedural_steps)
        return DirectExtraction(markdown, [candidate.citation_idx], confidence, procedural_steps)
    return None



def _build_fallback_answer(chunks: Sequence[RetrievalChunk], confidence: ConfidenceDecision) -> tuple[str, list[int]]:
    if not chunks:
        return (
            "## Resposta\nNão consigo responder com confiança com base nas fontes recuperadas.\n\n"
            "## Detalhes\n- Não existe evidência textual suficiente para sustentar uma resposta fiável.\n\n"
            "## Fontes usadas\nSem fontes recuperadas.",
            [],
        )

    top = chunks[:3]
    lines = []
    cited = []
    for idx, ch in enumerate(top, start=1):
        meta = ch.meta
        page = meta.get("page")
        loc = f"p.{page}" if page is not None else "texto"
        excerpt = _clean_value(ch.text, max_length=220)
        lines.append(f"[{idx}] {meta.get('source_title') or meta.get('source_file')} ({loc}) — {excerpt}")
        cited.append(idx)

    bullet_reasons = confidence.reasons or ["A evidência recuperada é parcial ou insuficiente para uma resposta fiável."]
    details = "\n".join(f"- {reason}" for reason in bullet_reasons)

    answer = (
        "## Resposta\n"
        "Não consigo responder com confiança com base nas fontes recuperadas.\n\n"
        "## Detalhes\n"
        f"{details}\n\n"
        "## Fontes usadas\n"
        + "\n".join(lines)
    )
    return answer, cited



def build_grounded_answer(
    *,
    query: str,
    analysis: QueryAnalysis,
    chunks: Sequence[RetrievalChunk],
    llm: Any,
    prompt_text: str,
    follow_ups: Sequence[str],
    retrieval_query: str,
) -> AnswerPackage:
    direct = _direct_extraction(query, analysis, chunks)
    if direct is not None:
        return AnswerPackage(
            answer_markdown=direct.answer_markdown,
            cited_indexes=direct.cited_indexes,
            confidence=direct.confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
            procedural_steps=direct.procedural_steps,
        )

    confidence = evaluate_confidence(query, analysis, chunks)
    procedural_steps = _build_procedural_steps(query, analysis, chunks)

    if llm is None or not confidence.should_answer:
        fallback_answer, cited = _build_fallback_answer(chunks, confidence)
        fallback_answer = _append_steps_block(fallback_answer, procedural_steps if confidence.should_answer else [])
        return AnswerPackage(
            answer_markdown=fallback_answer,
            cited_indexes=cited,
            confidence=confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
            procedural_steps=procedural_steps if confidence.should_answer else [],
        )

    try:
        result = llm.invoke(prompt_text)
        text = getattr(result, "content", str(result)).strip()
    except Exception as exc:
        confidence.reasons.append(f"Falha do LLM: {exc}")
        fallback_answer, cited = _build_fallback_answer(chunks, confidence)
        fallback_answer = _append_steps_block(fallback_answer, procedural_steps if confidence.should_answer else [])
        return AnswerPackage(
            answer_markdown=fallback_answer,
            cited_indexes=cited,
            confidence=confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
            procedural_steps=procedural_steps if confidence.should_answer else [],
        )

    if "## Resposta" not in text:
        detail = "As fontes abaixo sustentam a resposta." if chunks else "Sem fontes recuperadas."
        sources = []
        for idx, ch in enumerate(chunks[:3], start=1):
            sources.append(_citation_line(idx, ch))
        text = (
            f"## Resposta\n{text.strip()}\n\n"
            f"## Detalhes\n{detail}\n\n"
            f"## Fontes usadas\n" + ("\n".join(sources) if sources else "Sem fontes recuperadas.")
        )

    text = _append_steps_block(text, procedural_steps)
    cited = sorted({int(match.group(1)) for match in re.finditer(r"\[(\d+)\]", text)})
    if not cited and chunks:
        cited = list(range(1, min(3, len(chunks)) + 1))
    return AnswerPackage(
        answer_markdown=text,
        cited_indexes=cited,
        confidence=confidence,
        follow_up_questions=list(follow_ups),
        used_llm=True,
        retrieval_query=retrieval_query,
        procedural_steps=procedural_steps,
    )
