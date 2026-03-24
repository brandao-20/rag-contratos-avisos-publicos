"""Extração estruturada rápida e determinística a partir dos trechos recuperados."""

from __future__ import annotations

import re
from typing import Any
from langchain.schema import Document


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return _clean(m.group(1))
    return None


def extract_structured_from_docs(docs: list[Document]) -> dict[str, Any]:
    if not docs:
        return {}
    text = "\n\n".join(getattr(d, "page_content", "") for d in docs[:6])

    entidade = docs[0].metadata.get("entity") if docs and docs[0].metadata else None
    if not entidade:
        entidade = _first_match([
            r"Designação da entidade adjudicante:\s*(.+)",
            r"Emitente:\s*(.+)",
            r"^(MUNIC[IÍ]PIO DE .+)$",
            r"^(UNIVERSIDADE .+)$",
        ], text)

    objeto = _first_match([
        r"Designação do contrato:\s*(.+)",
        r"Sum[áa]rio:\s*(.+)",
        r"Descri[cç][aã]o:\s*(.+)",
        r"Objeto principal\s*(.+)",
    ], text)

    prazo_props = _first_match([
        r"Prazo para apresenta[cç][aã]o das propostas:\s*(.+)",
        r"aberto pelo prazo de\s*(.+?)\.",
        r"Prazo de candidatura\s*[:\-]\s*(.+)",
    ], text)
    prazo_exec = _first_match([
        r"Prazo de execu[cç][aã]o do contrato:\s*(.+)",
        r"Prazo de validade:\s*(.+)",
    ], text)
    prazos = None
    if prazo_props or prazo_exec:
        parts = []
        if prazo_props:
            parts.append(f"apresentação/propostas: {prazo_props}")
        if prazo_exec:
            parts.append(f"execução/validade: {prazo_exec}")
        prazos = "; ".join(parts)

    requisitos = _first_match([
        r"Documentos de habilita[cç][aã]o:\s*(.+)",
        r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*(.+)",
        r"Requisitos gerais de admiss[aã]o:\s*(.+)",
        r"Requisitos de admiss[aã]o[^:]*:\s*(.+)",
    ], text)

    valor = _first_match([
        r"Valor do pre[cç]o base do procedimento:\s*([\d\.,]+\s*EUR)",
        r"Pre[cç]o base s/IVA:\s*([\d\.,]+\s*EUR)",
        r"pre[cç]o base[^\n]*?([\d\.,]+\s*EUR)",
        r"valor base[^\n]*?([\d\.,]+\s*EUR)",
    ], text)

    criterios = _first_match([
        r"Crit[ée]rio de adjudica[cç][aã]o[^\n]*:\s*(.+)",
        r"Monofator:\s*Nome:\s*(.+)",
        r"Nome:\s*(Pre[cç]o|Qualidade[^\n]*)",
    ], text)

    refs = []
    for idx, d in enumerate(docs[:3], start=1):
        excerpt = _clean(getattr(d, "page_content", ""))
        if excerpt:
            refs.append({
                "citation": f"[{idx}]",
                "summary": excerpt[:160] + ("…" if len(excerpt) > 160 else ""),
            })

    return {
        "entidade": entidade,
        "objeto": objeto,
        "prazos": prazos,
        "requisitos": requisitos,
        "valor": valor,
        "criterios": criterios,
        "referencias_relevantes": refs or None,
    }
