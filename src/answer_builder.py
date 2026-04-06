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


FIELD_PATTERNS = {
    "objeto": [r"Designa[cç][aã]o do contrato:\s*(.+)", r"Sum[áa]rio:\s*(.+)", r"Descri[cç][aã]o:\s*(.+)"],
    "prazo": [r"Prazo para apresenta[cç][aã]o das propostas:\s*(.+)", r"aberto pelo prazo de\s*(.+?)\."],
    "prazo_exec": [r"Prazo de execu[cç][aã]o do contrato:\s*(.+)", r"Prazo de validade:\s*(.+)"],
    "valor": [r"Valor do pre[cç]o base do procedimento:\s*([\d\.\,]+\s*EUR)", r"Pre[cç]o base s/IVA:\s*([\d\.\,]+\s*EUR)"],
    "criterios": [r"CRIT[ÉE]RIO DE ADJUDICA[CÇ][AÃ]O(.+?)(?:24\s*-\s*CONDI[CÇ][ÕO]ES DO CONTRATO|$)", r"Monofator:\s*(.+)", r"Multifator:\s*(.+)"],
    "requisitos": [r"Documentos de habilita[cç][aã]o:\s*(.+)", r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*(.+)", r"Requisitos de admiss[aã]o[^:]*:\s*(.+)"],
    "entidade": [r"Designa[cç][aã]o da entidade adjudicante:\s*(.+)", r"Emitente:\s*(.+)"],
    "caucao": [r"Presta[cç][aã]o de cau[cç][aã]o:\s*(Sim|N[aã]o)", r"Garantia exigida:\s*(.+)"],
    "percentagem_caucao": [r"Percentagem:\s*([\d]+%)"],
    "cpv": [r"Vocabul[aá]rio Principal:\s*(\d{8})", r"CPV[:\s]+(\d{8})"],
    "lotes": [r"Procedimento com lotes\?\s*(Sim|N[aã]o)", r"Divis[aã]o em lotes:\s*(Sim|N[aã]o)"],
    "local": [r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO \(PROCEDIMENTO\)(.+?)(?:10\s*-\s*PRAZO DE EXECU[CÇ][AÃ]O DO CONTRATO|$)", r"Local de trabalho:\s*(.+)", r"Local da execu[cç][aã]o do contrato:\s*(.+)"],
}


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
            reasons=["A pergunta pede recomendação, opinião ou previsão fora do suporte documental do corpus."],
            should_answer=False,
        )
    if analysis.is_broad_listing:
        return ConfidenceDecision(
            label="baixa",
            score=0.0,
            reasons=[
                "A pergunta pede uma listagem global de contratos/avisos e não um elemento documental concreto.",
                "O corpus foi preparado para analisar procedimentos específicos com base em campos como objeto, prazo, preço base, caução, CPV, lotes e entidade adjudicante.",
            ],
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
            reasons.append("A evidência recuperada não mostra um prazo de apresentação suficientemente explícito.")
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


def _first_matching_chunk_index(chunks: Sequence[RetrievalChunk], patterns: Sequence[str]) -> int | None:
    for idx, ch in enumerate(chunks[:6], start=1):
        text = ch.text or ""
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
                return idx
    return 1 if chunks else None


def _search(patterns: Sequence[str], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            return match
    return None


def _extract_value(joined: str, key: str, *, max_length: int = 220) -> str | None:
    patterns = FIELD_PATTERNS.get(key, [])
    match = _search(patterns, joined)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" .;:-")
    if not value:
        return None
    return value[:max_length].rstrip() + ("…" if len(value) > max_length else "")


def _primary_source_label(chunks: Sequence[RetrievalChunk]) -> str | None:
    if not chunks:
        return None
    meta = chunks[0].meta or {}
    title = str(meta.get("source_title") or "").strip()
    entity = str(meta.get("entity") or "").strip()
    if entity and title and entity.lower() not in title.lower():
        return f"{entity} — {title}"
    return title or entity or None


def _unsupported_listing_answer(confidence: ConfidenceDecision) -> tuple[str, list[int]]:
    details = confidence.reasons or ["A pergunta pede uma listagem global sem um critério documental concreto."]
    detail_md = "\n".join(f"- {item}" for item in details)
    return (
        "## Resposta\n"
        "Não consigo listar \"contratos ativos\" ou \"avisos\" de forma fiável a partir do corpus inteiro sem um critério mais específico.\n\n"
        "## Detalhes\n"
        f"{detail_md}\n\n"
        "Pede antes um exemplo de procedimento com **caução**, **preço base**, **prazo**, **CPV** ou **entidade adjudicante** para obter uma resposta ancorada num documento concreto."
    ), []


def _build_procedural_steps(query: str, analysis: QueryAnalysis, chunks: Sequence[RetrievalChunk]) -> list[str]:
    if not analysis.is_procedural or not chunks:
        return []

    joined = "\n\n".join(ch.text for ch in chunks[:6])
    steps: list[str] = []
    objeto = _extract_value(joined, "objeto", max_length=200)
    valor = _extract_value(joined, "valor", max_length=80)
    prazo = _extract_value(joined, "prazo", max_length=120)
    prazo_exec = _extract_value(joined, "prazo_exec", max_length=120)
    requisitos = _extract_value(joined, "requisitos", max_length=200)
    criterios = _extract_value(joined, "criterios", max_length=180)
    caucao = _extract_value(joined, "caucao", max_length=100)
    cpv = _extract_value(joined, "cpv", max_length=100)
    lotes = _extract_value(joined, "lotes", max_length=60)
    local = _extract_value(joined, "local", max_length=160)

    steps.append(f"Confirmar o objeto e o enquadramento do procedimento{': ' + objeto if objeto else ''}.")

    financial_bits = []
    if valor:
        financial_bits.append(f"preço base {valor}")
    if cpv:
        financial_bits.append(f"CPV {cpv}")
    if lotes:
        financial_bits.append(f"lotes: {lotes}")
    if financial_bits:
        steps.append("Verificar os elementos económicos e de estrutura do procedimento: " + "; ".join(financial_bits) + ".")

    if prazo or prazo_exec:
        timeline_bits = []
        if prazo:
            timeline_bits.append(f"prazo de apresentação {prazo}")
        if prazo_exec:
            timeline_bits.append(f"prazo de execução/validade {prazo_exec}")
        steps.append("Fechar a componente temporal antes de avançar: " + "; ".join(timeline_bits) + ".")

    if requisitos:
        steps.append(f"Rever os requisitos e documentos de habilitação mencionados: {requisitos}.")

    closing_bits = []
    if criterios:
        closing_bits.append(f"critérios: {criterios}")
    if caucao:
        closing_bits.append(f"caução/garantia: {caucao}")
    if local:
        closing_bits.append(f"local de execução: {local}")
    if closing_bits:
        steps.append("Validar as condições finais do procedimento: " + "; ".join(closing_bits) + ".")

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
    joined = "\n\n".join(ch.text for ch in chunks[:6])

    intent = analysis.intent
    match = None
    cited = [1]
    answer = None
    details = None
    confidence = None
    source_label = _primary_source_label(chunks) or "o procedimento recuperado"

    if intent == "prazo":
        match = _search(FIELD_PATTERNS["prazo"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["prazo"]) or 1]
            answer = (
                f"## Resposta\nEncontrei um procedimento com prazo explícito: **{source_label}**. O prazo identificado é **{value}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO prazo identificado é **{value}** [{cited[0]}]."
            )
            details = "## Detalhes\nO valor foi extraído diretamente do campo de prazo presente no documento recuperado."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrado um campo de prazo explícito no documento."], True)
    elif intent == "valor":
        match = _search(FIELD_PATTERNS["valor"], joined)
        if match:
            value = match.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["valor"]) or 1]
            answer = (
                f"## Resposta\nEncontrei um procedimento com preço base explícito: **{source_label}**. O preço base identificado é **{value}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO valor/preço base identificado é **{value}** [{cited[0]}]."
            )
            details = "## Detalhes\nO montante foi extraído diretamente do campo de preço base do procedimento."
            confidence = ConfidenceDecision("alta", 0.9, ["Foi encontrado um montante monetário explícito associado ao preço base."], True)
    elif intent == "caucao":
        match = _search(FIELD_PATTERNS["caucao"], joined)
        if match:
            value = match.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["caucao"]) or 1]
            extra = _search(FIELD_PATTERNS["percentagem_caucao"], joined)
            percentage_tail = f" A percentagem indicada é **{extra.group(1).strip()}**." if extra else ""
            if analysis.is_search_example:
                if value.lower().startswith("s"):
                    answer = f"## Resposta\nEncontrei um procedimento que prevê prestação de caução: **{source_label}**.{percentage_tail} [{cited[0]}]."
                else:
                    answer = f"## Resposta\nEncontrei um procedimento ({source_label}) que indica **{value}** para a prestação de caução [{cited[0]}]."
            else:
                if value.lower().startswith("s"):
                    answer = f"## Resposta\nSim, o procedimento prevê prestação de caução.{percentage_tail} [{cited[0]}]."
                else:
                    answer = f"## Resposta\nNão, o procedimento indica que não existe prestação de caução [{cited[0]}]."
            details = "## Detalhes\nA resposta foi construída a partir do campo explícito de caução/garantia encontrado na fonte principal."
            confidence = ConfidenceDecision("alta", 0.91, ["Foi encontrado um campo explícito de prestação de caução."], True)
    elif intent == "cpv":
        match = _search(FIELD_PATTERNS["cpv"], joined)
        if match:
            value = match.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["cpv"]) or 1]
            answer = (
                f"## Resposta\nEncontrei um procedimento com CPV explícito: **{source_label}**. O CPV identificado é **{value}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO CPV identificado é **{value}** [{cited[0]}]."
            )
            details = "## Detalhes\nO código foi extraído diretamente do campo CPV/Vocabulário Principal recuperado."
            confidence = ConfidenceDecision("alta", 0.92, ["Foi encontrado um código CPV explícito no documento."], True)
    elif intent == "criterios":
        match = _search(FIELD_PATTERNS["criterios"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["criterios"]) or 1]
            short = value[:280].rstrip() + ("…" if len(value) > 280 else "")
            answer = (
                f"## Resposta\nEncontrei um procedimento com referência explícita a critérios de adjudicação: **{source_label}**. O trecho recuperado indica **{short}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nOs critérios de adjudicação recuperados indicam: **{short}** [{cited[0]}]."
            )
            details = "## Detalhes\nA resposta foi sintetizada a partir da secção explícita de critério de adjudicação."
            confidence = ConfidenceDecision("média", 0.78, ["Foi encontrada a secção explícita de critério de adjudicação."], True)
    elif intent == "entidade":
        match = _search(FIELD_PATTERNS["entidade"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["entidade"]) or 1]
            answer = (
                f"## Resposta\nEncontrei um procedimento cuja entidade adjudicante identificada é **{value}**. A fonte principal recuperada é **{source_label}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nA entidade identificada é **{value}** [{cited[0]}]."
            )
            details = "## Detalhes\nA entidade foi extraída diretamente do cabeçalho institucional do documento recuperado."
            confidence = ConfidenceDecision("alta", 0.88, ["Foi encontrada uma designação explícita da entidade adjudicante/emitente."], True)
    elif intent == "local":
        match = _search(FIELD_PATTERNS["local"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["local"]) or 1]
            short = value[:220].rstrip() + ("…" if len(value) > 220 else "")
            answer = (
                f"## Resposta\nEncontrei um procedimento com local de execução explícito: **{source_label}**. O local recuperado é **{short}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO local identificado é **{short}** [{cited[0]}]."
            )
            details = "## Detalhes\nO local foi extraído diretamente da secção de execução/local de trabalho do documento."
            confidence = ConfidenceDecision("média", 0.79, ["Foi encontrada uma secção explícita sobre o local."], True)
    elif intent == "requisitos":
        match = _search(FIELD_PATTERNS["requisitos"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["requisitos"]) or 1]
            short = value[:260].rstrip() + ("…" if len(value) > 260 else "")
            answer = (
                f"## Resposta\nEncontrei um procedimento com requisitos/habilitações explícitos: **{source_label}**. O trecho recuperado indica **{short}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nOs requisitos/habilitações recuperados indicam: **{short}** [{cited[0]}]."
            )
            details = "## Detalhes\nA resposta foi extraída diretamente da secção de habilitação/documentos de habilitação do documento."
            confidence = ConfidenceDecision("média", 0.77, ["Foi encontrada uma secção explícita de habilitação/requisitos."], True)
    elif intent == "lotes":
        match = _search(FIELD_PATTERNS["lotes"], joined)
        if match:
            value = match.group(1).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["lotes"]) or 1]
            answer = (
                f"## Resposta\nEncontrei um procedimento com informação explícita sobre lotes: **{source_label}**. O documento indica **{value}** quanto à existência de lotes [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO documento indica **{value}** quanto à existência de lotes [{cited[0]}]."
            )
            details = "## Detalhes\nA resposta foi extraída diretamente do campo relativo à divisão em lotes."
            confidence = ConfidenceDecision("alta", 0.89, ["Foi encontrado um campo explícito sobre a existência de lotes."], True)
    else:
        match = _search(FIELD_PATTERNS["objeto"], joined)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            cited = [_first_matching_chunk_index(chunks, FIELD_PATTERNS["objeto"]) or 1]
            short = value[:260].rstrip() + ("…" if len(value) > 260 else "")
            answer = (
                f"## Resposta\nUm procedimento compatível com o teu pedido é **{source_label}**. O objeto identificado é **{short}** [{cited[0]}]."
                if analysis.is_search_example
                else f"## Resposta\nO objeto/designação identificado é **{short}** [{cited[0]}]."
            )
            details = "## Detalhes\nA resposta foi extraída diretamente do campo de designação/descrição do contrato ou do sumário do aviso."
            confidence = ConfidenceDecision("alta", 0.85, ["Foi encontrada uma designação/descrição explícita do objeto."], True)

    if answer and details and confidence:
        sources = "\n".join(_citation_line(i, chunks[i - 1]) for i in cited if 0 < i <= len(chunks))
        procedural_steps = _build_procedural_steps(query, analysis, chunks)
        markdown = f"{answer}\n\n{details}\n\n## Fontes usadas\n{sources}\n\nConfirmar sempre a informação na fonte oficial."
        markdown = _append_steps_block(markdown, procedural_steps)
        return DirectExtraction(markdown, cited, confidence, procedural_steps)
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
        excerpt = re.sub(r"\s+", " ", ch.text).strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:220].rstrip() + "…"
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
    confidence = evaluate_confidence(query, analysis, chunks)
    if analysis.is_broad_listing:
        fallback_answer, cited = _unsupported_listing_answer(confidence)
        return AnswerPackage(
            answer_markdown=fallback_answer,
            cited_indexes=cited,
            confidence=confidence,
            follow_up_questions=list(follow_ups),
            used_llm=False,
            retrieval_query=retrieval_query,
            procedural_steps=[],
        )

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
