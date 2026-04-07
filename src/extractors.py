"""Extração estruturada rápida e determinística a partir dos trechos recuperados.

Melhorias v2:
- Critérios: extrai bloco completo (monofator/multifator + fatores/subfatores)
- Requisitos: extrai lista real de documentos exigidos em vez de Sim/Não
- Local: extrai NUT/município em vez de só "País: Portugal"
- Caução: inclui percentagem e condição além de Sim/Não
- Normalização: datas, montantes, booleanos
- Proveniência por campo: indica de que chunk saiu cada campo
"""

from __future__ import annotations

import re
from typing import Any
from langchain.schema import Document


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip(" .;:-")


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if m:
            value = _clean(m.group(1))
            if value:
                return value
    return None


def _best_from_docs(patterns: list[str], docs: list[Document]) -> tuple[str | None, int | None]:
    """Retorna (valor, índice_do_doc) para proveniência por campo."""
    for idx, doc in enumerate(docs[:6]):
        value = _first_match(patterns, getattr(doc, "page_content", "") or "")
        if value:
            return value, idx + 1  # 1-based citation index
    return None, None


def _normalize_money(value: str) -> str:
    """Garante que montantes têm formato legível: 73.032,00 EUR."""
    if not value:
        return value
    value = value.strip()
    # Já está bem formatado
    if re.search(r"\d[\d\.,]+\s*EUR", value, re.IGNORECASE):
        return value
    return value


def _normalize_boolean(value: str) -> str:
    if not value:
        return value
    vn = value.strip().lower()
    if vn in ("sim", "yes", "s", "true", "1"):
        return "Sim"
    if vn in ("não", "nao", "no", "n", "false", "0"):
        return "Não"
    return value


def _extract_criterios_block(docs: list[Document]) -> tuple[str | None, int | None]:
    """Extrai o bloco de critérios de adjudicação com estrutura real.

    Tenta capturar:
    1. Monofator (critério único — ex. Preço)
    2. Multifator com fatores/subfatores e ponderações
    3. Fallback para a linha de critério simples
    """
    for idx, doc in enumerate(docs[:6]):
        text = getattr(doc, "page_content", "") or ""

        # Padrão 1: bloco completo CRITÉRIO DE ADJUDICAÇÃO … CONDIÇÕES DO CONTRATO
        m = re.search(
            r"CRIT[ÉE]RIO DE ADJUDICA[CÇ][AÃ]O\s*(.+?)(?:24\s*-\s*CONDI[CÇ][ÕO]ES DO CONTRATO|$)",
            text, flags=re.IGNORECASE | re.DOTALL
        )
        if m:
            block = re.sub(r"\s+", " ", m.group(1)).strip()
            if block:
                # Extrai monofator / multifator
                mono = re.search(r"Monofator:\s*(Sim|N[aã]o)", block, re.IGNORECASE)
                multi = re.search(r"Multifator:\s*(Sim|N[aã]o)", block, re.IGNORECASE)
                factors = re.findall(r"Nome:\s*([^\n;]+?)(?:\s+Ponderação:\s*(\d+(?:,\d+)?%?))?(?=\s+Nome:|\s*$)", block, re.IGNORECASE)

                parts: list[str] = []
                if mono:
                    parts.append(f"Monofator: {_normalize_boolean(mono.group(1))}")
                if multi:
                    parts.append(f"Multifator: {_normalize_boolean(multi.group(1))}")
                if factors:
                    factor_strs = [f"{n.strip()}" + (f" ({p.strip()})" if p else "") for n, p in factors[:6]]
                    parts.append("Fatores: " + "; ".join(factor_strs))
                if not parts:
                    parts.append(block[:300].rstrip() + ("…" if len(block) > 300 else ""))
                return " | ".join(parts), idx + 1

        # Padrão 2: linha simples
        simple = re.search(
            r"Crit[ée]rio de adjudica[cç][aã]o[^:\n]*:\s*([^\n]+)",
            text, re.IGNORECASE
        )
        if simple:
            return _clean(simple.group(1))[:280], idx + 1

        # Padrão 3: monofator / multifator em linha
        mono_line = re.search(r"Monofator:\s*([^\n]+)", text, re.IGNORECASE)
        if mono_line:
            return f"Monofator: {_clean(mono_line.group(1))}", idx + 1

    return None, None


def _extract_requisitos_block(docs: list[Document]) -> tuple[str | None, int | None]:
    """Extrai requisitos/habilitações com mais detalhe que Sim/Não."""
    for idx, doc in enumerate(docs[:6]):
        text = getattr(doc, "page_content", "") or ""

        # Bloco Documentos de habilitação (pode ter lista de itens)
        m = re.search(
            r"Documentos de habilita[cç][aã]o:\s*(.+?)(?=\d+\s*-\s*[A-ZÁÉÍÓÚ]|CRIT[ÉE]RIO|$)",
            text, flags=re.IGNORECASE | re.DOTALL
        )
        if m:
            block = re.sub(r"\s+", " ", m.group(1)).strip()
            if block and len(block) > 4:
                return block[:400].rstrip() + ("…" if len(block) > 400 else ""), idx + 1

        # Habilitação profissional
        prof = re.search(
            r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*([^\n]+(?:\n(?!\d+\s*-).*)*)",
            text, re.IGNORECASE
        )
        if prof:
            value = _clean(re.sub(r"\s+", " ", prof.group(1)))
            if value and value.lower() not in ("sim", "não", "nao", "s", "n"):
                return value[:300], idx + 1

        # Requisito de participação
        req = re.search(r"Requisitos de admiss[aã]o[^:]*:\s*([^\n]+)", text, re.IGNORECASE)
        if req:
            value = _clean(req.group(1))
            if value and value.lower() not in ("sim", "não", "nao"):
                return value[:300], idx + 1

    return None, None


def _extract_local_block(docs: list[Document]) -> tuple[str | None, int | None]:
    """Extrai local com detalhe geográfico (NUT, município, endereço)."""
    for idx, doc in enumerate(docs[:6]):
        text = getattr(doc, "page_content", "") or ""

        # Bloco completo LOCAL DA EXECUÇÃO
        m = re.search(
            r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO\s*(?:\(PROCEDIMENTO\))?\s*(.+?)(?=\d+\s*-\s*PRAZO|$)",
            text, flags=re.IGNORECASE | re.DOTALL
        )
        if m:
            block = re.sub(r"\s+", " ", m.group(1)).strip()
            if block:
                # Extrai País + NUT + municipality
                pais = re.search(r"Pa[íi]s:\s*([^\s]+(?:\s+[A-Z][^\s]*)?)", block, re.IGNORECASE)
                nut = re.search(r"NUT\s+(?:III|II|I)?:\s*([A-Z]{2}\d+[^\s]*)", block, re.IGNORECASE)
                muni = re.search(r"Município:\s*([^\n;]+)", block, re.IGNORECASE)
                morada = re.search(r"Morada:\s*([^\n;]+)", block, re.IGNORECASE)

                parts: list[str] = []
                if pais:
                    parts.append(f"País: {pais.group(1).strip()}")
                if nut:
                    parts.append(f"NUT: {nut.group(1).strip()}")
                if muni:
                    parts.append(f"Município: {muni.group(1).strip()}")
                if morada:
                    parts.append(f"Morada: {morada.group(1).strip()}")

                if parts:
                    return "; ".join(parts), idx + 1
                # Fallback: primeiros 200 chars do bloco (melhor que só País: Portugal)
                return block[:200].rstrip() + ("…" if len(block) > 200 else ""), idx + 1

        # Local de trabalho simples
        lt = re.search(r"Local de trabalho:\s*([^\n]+)", text, re.IGNORECASE)
        if lt:
            return _clean(lt.group(1))[:200], idx + 1

        # Local da execução do contrato linha simples
        le = re.search(r"Local da execu[cç][aã]o do contrato:\s*([^\n]+)", text, re.IGNORECASE)
        if le:
            return _clean(le.group(1))[:200], idx + 1

    return None, None


def _extract_caucao_block(docs: list[Document]) -> tuple[str | None, int | None]:
    """Extrai caução com percentagem e regime, não apenas Sim/Não."""
    for idx, doc in enumerate(docs[:6]):
        text = getattr(doc, "page_content", "") or ""

        # Padrão principal: Prestação de caução: Sim/Não + eventual percentagem
        m = re.search(r"Presta[cç][aã]o de cau[cç][aã]o:\s*(Sim|N[aã]o)", text, re.IGNORECASE)
        if m:
            valor = _normalize_boolean(m.group(1))
            extra_parts: list[str] = [f"Prestação de caução: {valor}"]

            pct = re.search(r"Percentagem:\s*([\d]+(?:,\d+)?\s*%)", text, re.IGNORECASE)
            if pct:
                extra_parts.append(f"Percentagem: {pct.group(1).strip()}")

            regime = re.search(r"Regime:\s*([^\n;]+)", text, re.IGNORECASE)
            if regime:
                extra_parts.append(f"Regime: {_clean(regime.group(1))}")

            return " | ".join(extra_parts), idx + 1

        # Garantia exigida
        g = re.search(r"Garantia exigida:\s*([^\n]+)", text, re.IGNORECASE)
        if g:
            return _clean(g.group(1))[:200], idx + 1

    return None, None


def extract_structured_from_docs(docs: list[Document]) -> dict[str, Any]:
    """Extrai campos estruturados com proveniência por campo (source_citation)."""
    if not docs:
        return {}

    # ── Entidade ──────────────────────────────────────────────────────────────
    entidade = docs[0].metadata.get("entity") if docs and docs[0].metadata else None
    entidade_citation = 1
    if not entidade:
        entidade, entidade_citation = _best_from_docs([
            r"Designa[cç][aã]o da entidade adjudicante:\s*([^\n]+)",
            r"Emitente:\s*([^\n]+)",
            r"^(MUNIC[IÍ]PIO DE .+)$",
            r"^(UNIVERSIDADE .+)$",
        ], docs)

    # ── Objeto ────────────────────────────────────────────────────────────────
    objeto, objeto_citation = _best_from_docs([
        r"Designa[cç][aã]o do contrato:\s*([^\n]+)",
        r"Sum[áa]rio:\s*([^\n]+)",
        r"Descri[cç][aã]o:\s*([^\n]+)",
        r"Objeto principal\s*([^\n]+)",
    ], docs)

    # ── Prazos ────────────────────────────────────────────────────────────────
    prazo_props, prazo_props_citation = _best_from_docs([
        r"Prazo para apresenta[cç][aã]o das propostas:\s*([^\n]+)",
        r"Prazo de candidatura\s*[:\-]\s*([^\n]+)",
        r"aberto pelo prazo de\s*([^\.;\n]+)",
    ], docs)
    prazo_exec, prazo_exec_citation = _best_from_docs([
        r"Prazo de execu[cç][aã]o do contrato:\s*([^\n]+)",
        r"Prazo de validade:\s*([^\n]+)",
        r"Prazo de execução:\s*([^\n]+)",
    ], docs)

    prazos = None
    prazos_citation = prazo_props_citation or prazo_exec_citation
    if prazo_props or prazo_exec:
        parts = []
        if prazo_props:
            parts.append(f"apresentação/propostas: {prazo_props}")
        if prazo_exec:
            parts.append(f"execução/validade: {prazo_exec}")
        prazos = "; ".join(parts)

    # ── Valor ─────────────────────────────────────────────────────────────────
    valor, valor_citation = _best_from_docs([
        r"Valor do pre[cç]o base do procedimento:\s*([\d\.,]+\s*EUR)",
        r"Pre[cç]o base s/IVA:\s*([\d\.,]+\s*EUR)",
        r"pre[cç]o base[^\n]*?([\d\.,]+\s*EUR)",
        r"valor base[^\n]*?([\d\.,]+\s*EUR)",
    ], docs)
    if valor:
        valor = _normalize_money(valor)

    # ── Critérios (melhorado) ─────────────────────────────────────────────────
    criterios, criterios_citation = _extract_criterios_block(docs)

    # ── Caução (melhorado) ────────────────────────────────────────────────────
    caucao, caucao_citation = _extract_caucao_block(docs)

    # ── CPV ───────────────────────────────────────────────────────────────────
    cpv, cpv_citation = _best_from_docs([
        r"Vocabul[aá]rio Principal:\s*(\d{8}[^\n]*)",
        r"CPV[:\s]+(\d{8}[^\n]*)",
        r"Vocabul[aá]rio comum para os contratos p[úu]blicos[^\n]*:\s*([^\n]+)",
    ], docs)

    # ── Lotes ─────────────────────────────────────────────────────────────────
    lotes_raw, lotes_citation = _best_from_docs([
        r"Procedimento com lotes\?\s*(Sim|N[aã]o)",
        r"Divis[aã]o em lotes:\s*(Sim|N[aã]o)",
    ], docs)
    lotes = _normalize_boolean(lotes_raw) if lotes_raw else None

    # ── Local (melhorado) ─────────────────────────────────────────────────────
    local, local_citation = _extract_local_block(docs)

    # ── Requisitos (melhorado) ────────────────────────────────────────────────
    requisitos, requisitos_citation = _extract_requisitos_block(docs)

    # ── Referências ───────────────────────────────────────────────────────────
    refs = []
    for i, d in enumerate(docs[:3], start=1):
        excerpt = _clean(getattr(d, "page_content", ""))
        if excerpt:
            refs.append({
                "citation": f"[{i}]",
                "summary": excerpt[:160] + ("…" if len(excerpt) > 160 else ""),
            })

    # ── Mapa de proveniência ──────────────────────────────────────────────────
    field_citations: dict[str, int | None] = {
        "entidade": entidade_citation,
        "objeto": objeto_citation,
        "prazos": prazos_citation,
        "valor": valor_citation,
        "criterios": criterios_citation,
        "caucao": caucao_citation,
        "cpv": cpv_citation,
        "lotes": lotes_citation,
        "local": local_citation,
        "requisitos": requisitos_citation,
    }

    return {
        "entidade": entidade,
        "objeto": objeto,
        "prazos": prazos,
        "valor": valor,
        "criterios": criterios,
        "caucao": caucao,
        "cpv": cpv,
        "lotes": lotes,
        "local": local,
        "requisitos": requisitos,
        "referencias_relevantes": refs or None,
        "_field_citations": field_citations,  # proveniência por campo
    }
