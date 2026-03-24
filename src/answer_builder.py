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


@dataclass
class DirectExtraction:
    answer_markdown: str
    cited_indexes: list[int]
    confidence: ConfidenceDecision



def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()



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
            reasons=["Pergunta fora do âmbito documental/jurídico suportado."],
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
        elif re.search(r"\b\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}\b", joined_norm):
            score += 0.18
        else:
            reasons.append("A evidência não contém um prazo de apresentação suficientemente explícito.")
    elif analysis.intent == "valor":
        if re.search(r"(?:valor do )?pre[cç]o base do procedimento:\s*[\d\.\,]+\s*eur", joined_norm) or re.search(r"pre[cç]o base s/iva:\s*[\d\.\,]+\s*eur", joined_norm):
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
        if "procedimento com lotes?" in joined_norm:
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
        reasons.append("Cobertura e semelhança insuficientes para responder com segurança.")

    score = max(0.0, min(score, 0.97))
    if score >= 0.80 and should_answer:
        label = "alta"
    elif score >= 0.56 and should_answer:
        label = "média"
    else:
        label = "baixa"

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



def _first_matching_chunk_index(chunks: Sequence[RetrievalChunk], patterns: Sequence[str]) -> int | None:
    for idx, ch in enumerate(chunks[:6], start=1):
        text = ch.text or ""
        for p in patterns:
            if re.search(p, text, flags=re.IGNORECASE | re.MULTILINE):
                return idx
    return 1 if chunks else None



def _search(patterns: Sequence[str], text: str) -> re.Match[str] | None:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return m
    return None



def _direct_extraction(query: str, analysis: QueryAnalysis, chunks: Sequence[RetrievalChunk]) -> DirectExtraction | None:
    if not chunks:
        return None
    joined = "\n\n".join(ch.text for ch in chunks[:6])

    intent = analysis.intent
    m = None
    cited = [1]
    answer = None
    details = None
    confidence = None

    if intent == "prazo":
        m = _search([
            r"Prazo para apresenta[cç][aã]o das propostas:\s*(.+)",
            r"aberto pelo prazo de\s*(.+?)\."
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Prazo para apresenta[cç][aã]o das propostas:", r"aberto pelo prazo de"]) or 1]
            answer = f"## Resposta\nO prazo identificado é **{value}** [{cited[0]}]."
            details = "## Detalhes\nO valor foi extraído diretamente do campo de prazo presente no documento recuperado."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrado um campo de prazo explícito no documento."], True)
    elif intent == "valor":
        m = _search([
            r"Valor do pre[cç]o base do procedimento:\s*([\d\.\,]+\s*EUR)",
            r"Pre[cç]o base s/IVA:\s*([\d\.\,]+\s*EUR)"
        ], joined)
        if m:
            value = m.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Valor do pre[cç]o base do procedimento:", r"Pre[cç]o base s/IVA:"]) or 1]
            answer = f"## Resposta\nO valor/preço base identificado é **{value}** [{cited[0]}]."
            details = "## Detalhes\nO montante foi extraído diretamente do campo de preço base do procedimento."
            confidence = ConfidenceDecision("alta", 0.9, ["Foi encontrado um montante monetário explícito associado ao preço base."], True)
    elif intent == "caucao":
        m = _search([
            r"Presta[cç][aã]o de cau[cç][aã]o:\s*(Sim|N[aã]o)",
        ], joined)
        if m:
            value = m.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Presta[cç][aã]o de cau[cç][aã]o:"]) or 1]
            extra = _search([r"Percentagem:\s*([\d]+%)"], joined)
            tail = f" A percentagem indicada é **{extra.group(1).strip()}** [{cited[0]}]." if extra else ""
            answer = f"## Resposta\nSim, o documento indica prestação de caução: **{value}** [{cited[0]}].{tail}" if value.lower().startswith('s') else f"## Resposta\nNão, o documento indica prestação de caução: **{value}** [{cited[0]}]."
            details = "## Detalhes\nA resposta foi extraída diretamente do campo 'Prestação de caução' do documento recuperado."
            confidence = ConfidenceDecision("alta", 0.91, ["Foi encontrado um campo explícito de prestação de caução."], True)
    elif intent == "cpv":
        m = _search([
            r"Vocabul[aá]rio Principal:\s*(\d{8})",
        ], joined)
        if m:
            value = m.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Vocabul[aá]rio Principal:"]) or 1]
            answer = f"## Resposta\nO CPV identificado é **{value}** [{cited[0]}]."
            details = "## Detalhes\nO código foi extraído diretamente do campo 'Vocabulário Principal' do documento recuperado."
            confidence = ConfidenceDecision("alta", 0.92, ["Foi encontrado um código CPV explícito no documento."], True)
    elif intent == "criterios":
        m = _search([
            r"CRIT[ÉE]RIO DE ADJUDICA[CÇ][AÃ]O(.+?)(?:24\s*-\s*CONDI[CÇ][ÕO]ES DO CONTRATO|$)",
            r"Monofator:\s*(.+)",
            r"Multifator:\s*(.+)",
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"CRIT[ÉE]RIO DE ADJUDICA[CÇ][AÃ]O", r"Monofator:", r"Multifator:"]) or 1]
            short = value[:280].rstrip() + ("…" if len(value) > 280 else "")
            answer = f"## Resposta\nOs critérios de adjudicação recuperados indicam: **{short}** [{cited[0]}]."
            details = "## Detalhes\nA resposta foi sintetizada a partir da secção 'Critério de adjudicação' do documento recuperado."
            confidence = ConfidenceDecision("média", 0.78, ["Foi encontrada a secção explícita de critério de adjudicação."], True)
    elif intent == "entidade":
        m = _search([
            r"Designa[cç][aã]o da entidade adjudicante:\s*(.+)",
            r"Emitente:\s*(.+)",
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Designa[cç][aã]o da entidade adjudicante:", r"Emitente:"]) or 1]
            answer = f"## Resposta\nA entidade identificada é **{value}** [{cited[0]}]."
            details = "## Detalhes\nA entidade foi extraída diretamente do cabeçalho institucional do documento recuperado."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrada uma designação explícita da entidade adjudicante/emitente."], True)
    elif intent == "local":
        m = _search([
            r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO \(PROCEDIMENTO\)(.+?)(?:10\s*-\s*PRAZO DE EXECU[CÇ][AÃ]O DO CONTRATO|$)",
            r"Local de trabalho:\s*(.+)",
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO", r"Local de trabalho:"]) or 1]
            short = value[:220].rstrip() + ("…" if len(value) > 220 else "")
            answer = f"## Resposta\nO local identificado é **{short}** [{cited[0]}]."
            details = "## Detalhes\nO local foi extraído diretamente da secção de execução/local de trabalho do documento."
            confidence = ConfidenceDecision("média", 0.79, ["Foi encontrada uma secção explícita sobre o local."], True)
    elif intent == "requisitos":
        m = _search([
            r"Documentos de habilita[cç][aã]o:\s*(.+)",
            r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*(.+)",
            r"Requisitos de admiss[aã]o[^:]*:\s*(.+)",
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Documentos de habilita[cç][aã]o:", r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:", r"Requisitos de admiss[aã]o"]) or 1]
            short = value[:260].rstrip() + ("…" if len(value) > 260 else "")
            answer = f"## Resposta\nOs requisitos/habilitações recuperados indicam: **{short}** [{cited[0]}]."
            details = "## Detalhes\nA resposta foi extraída diretamente da secção de habilitação/documentos de habilitação do documento."
            confidence = ConfidenceDecision("média", 0.77, ["Foi encontrada uma secção explícita de habilitação/requisitos."], True)
    elif intent == "lotes":
        m = _search([
            r"Procedimento com lotes\?\s*(Sim|N[aã]o)",
        ], joined)
        if m:
            value = m.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Procedimento com lotes\?"]) or 1]
            answer = f"## Resposta\nO documento indica **{value}** quanto à existência de lotes [{cited[0]}]."
            details = "## Detalhes\nA resposta foi extraída diretamente do campo 'Procedimento com lotes?'."
            confidence = ConfidenceDecision("alta", 0.89, ["Foi encontrado um campo explícito sobre a existência de lotes."], True)
    else:  # objeto
        m = _search([
            r"Designa[cç][aã]o do contrato:\s*(.+)",
            r"Sum[áa]rio:\s*(.+)",
            r"Descri[cç][aã]o:\s*(.+)",
        ], joined)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, [r"Designa[cç][aã]o do contrato:", r"Sum[áa]rio:", r"Descri[cç][aã]o:"]) or 1]
            short = value[:260].rstrip() + ("…" if len(value) > 260 else "")
            answer = f"## Resposta\nO objeto/designação identificado é **{short}** [{cited[0]}]."
            details = "## Detalhes\nA resposta foi extraída diretamente do campo de designação/descrição do contrato ou do sumário do aviso."
            confidence = ConfidenceDecision("alta", 0.85, ["Foi encontrada uma designação/descrição explícita do objeto."], True)

    if answer and details and confidence:
        sources = "\n".join(_citation_line(i, chunks[i-1]) for i in cited if 0 < i <= len(chunks))
        markdown = f"{answer}\n\n{details}\n\n## Fontes usadas\n{sources}\n\nConfirmar sempre a informação na fonte oficial."
        return DirectExtraction(markdown, cited, confidence)
    return None



def _build_fallback_answer(chunks: Sequence[RetrievalChunk], confidence: ConfidenceDecision) -> tuple[str, list[int]]:
    if not chunks:
        return (
            "## Resposta\nNão foi encontrada informação suficiente nos documentos carregados.\n\n"
            "## Detalhes\nNão existe evidência textual recuperada que suporte uma resposta fiável.\n\n"
            "## Fontes usadas\nSem fontes recuperadas.\n\n"
            "Confirmar sempre a informação na fonte oficial.",
            [],
        )
    top = chunks[:3]
    lines = []
    cited = []
    for idx, ch in enumerate(top, start=1):
        meta = ch.meta
        page = meta.get("page")
        loc = f"p.{page}" if page is not None else "texto"
        excerpt = re.sub(r"\s+", " ", ch.text).strip()
        if len(excerpt) > 260:
            excerpt = excerpt[:260].rstrip() + "…"
        lines.append(f"[{idx}] {meta.get('source_title') or meta.get('source_file')} ({loc}) — {excerpt}")
        cited.append(idx)
    details = "\n".join(f"- {r}" for r in confidence.reasons) if confidence.reasons else "- A resposta foi construída apenas com base nos excertos recuperados."
    answer = (
        "## Resposta\n"
        "Foi encontrada evidência parcial nos documentos, mas não suficiente para uma resposta plenamente segura.\n\n"
        "## Detalhes\n"
        f"{details}\n\n"
        "## Fontes usadas\n"
        + "\n".join(lines)
        + "\n\nConfirmar sempre a informação na fonte oficial."
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
        )

    confidence = evaluate_confidence(query, analysis, chunks)

    if llm is None or not confidence.should_answer:
        fallback_answer, cited = _build_fallback_answer(chunks, confidence)
        return AnswerPackage(
            answer_markdown=fallback_answer,
            cited_indexes=cited,
            confidence=confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
        )

    try:
        result = llm.invoke(prompt_text)
        text = getattr(result, "content", str(result)).strip()
    except Exception as exc:
        confidence.reasons.append(f"Falha do LLM: {exc}")
        fallback_answer, cited = _build_fallback_answer(chunks, confidence)
        return AnswerPackage(
            answer_markdown=fallback_answer,
            cited_indexes=cited,
            confidence=confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
        )

    if "## Resposta" not in text:
        text = text.strip()
        detail = "As fontes abaixo sustentam a resposta." if chunks else "Sem fontes recuperadas."
        sources = []
        for idx, ch in enumerate(chunks[:3], start=1):
            sources.append(_citation_line(idx, ch))
        text = (
            f"## Resposta\n{text}\n\n"
            f"## Detalhes\n{detail}\n\n"
            f"## Fontes usadas\n" + ("\n".join(sources) if sources else "Sem fontes recuperadas.")
            + "\n\nConfirmar sempre a informação na fonte oficial."
        )

    cited = sorted({int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", text)})
    if not cited and chunks:
        cited = list(range(1, min(3, len(chunks)) + 1))
    return AnswerPackage(
        answer_markdown=text,
        cited_indexes=cited,
        confidence=confidence,
        follow_up_questions=list(follow_ups),
        used_llm=True,
        retrieval_query=retrieval_query,
    )
