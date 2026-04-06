"""Extração estruturada rápida e determinística a partir dos trechos recuperados."""

from __future__ import annotations

import re
from typing import Any
from langchain.schema import Document


def _clean(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "")).strip(" .;:-")
    return value



def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if m:
            value = _clean(m.group(1))
            if value:
                return value
    return None



def _best_from_docs(patterns: list[str], docs: list[Document]) -> str | None:
    for doc in docs[:6]:
        value = _first_match(patterns, getattr(doc, "page_content", "") or "")
        if value:
            return value
    return None



def extract_structured_from_docs(docs: list[Document]) -> dict[str, Any]:
    if not docs:
        return {}
    text = "\n\n".join(getattr(d, "page_content", "") for d in docs[:6])

    entidade = docs[0].metadata.get("entity") if docs and docs[0].metadata else None
    if not entidade:
        entidade = _best_from_docs([
            r"Designa[cç][aã]o da entidade adjudicante:\s*([^\n]+)",
            r"Emitente:\s*([^\n]+)",
            r"^(MUNIC[IÍ]PIO DE .+)$",
            r"^(UNIVERSIDADE .+)$",
        ], docs)

    objeto = _best_from_docs([
        r"Designa[cç][aã]o do contrato:\s*([^\n]+)",
        r"Sum[áa]rio:\s*([^\n]+)",
        r"Descri[cç][aã]o:\s*([^\n]+)",
        r"Objeto principal\s*([^\n]+)",
    ], docs)

    prazo_props = _best_from_docs([
        r"Prazo para apresenta[cç][aã]o das propostas:\s*([^\n]+)",
        r"Prazo de candidatura\s*[:\-]\s*([^\n]+)",
        r"aberto pelo prazo de\s*([^\.\n]+)",
    ], docs)
    prazo_exec = _best_from_docs([
        r"Prazo de execu[cç][aã]o do contrato:\s*([^\n]+)",
        r"Prazo de validade:\s*([^\n]+)",
    ], docs)
    prazos = None
    if prazo_props or prazo_exec:
        parts = []
        if prazo_props:
            parts.append(f"apresentação/propostas: {prazo_props}")
        if prazo_exec:
            parts.append(f"execução/validade: {prazo_exec}")
        prazos = "; ".join(parts)

    requisitos = _best_from_docs([
        r"Documentos de habilita[cç][aã]o:\s*([^\n]+)",
        r"Habilita[cç][aã]o para o exerc[ií]cio da atividade profissional:\s*([^\n]+)",
        r"Requisitos gerais de admiss[aã]o:\s*([^\n]+)",
        r"Requisitos de admiss[aã]o[^:]*:\s*([^\n]+)",
    ], docs)

    valor = _best_from_docs([
        r"Valor do pre[cç]o base do procedimento:\s*([\d\.,]+\s*EUR)",
        r"Pre[cç]o base s/IVA:\s*([\d\.,]+\s*EUR)",
        r"pre[cç]o base[^\n]*?([\d\.,]+\s*EUR)",
        r"valor base[^\n]*?([\d\.,]+\s*EUR)",
    ], docs)

    criterios = _best_from_docs([
        r"Crit[ée]rio de adjudica[cç][aã]o[^\n]*:\s*([^\n]+)",
        r"Monofator:\s*([^\n]+)",
        r"Multifator:\s*([^\n]+)",
    ], docs)

    caucao = _best_from_docs([
        r"Presta[cç][aã]o de cau[cç][aã]o:\s*([^\n]+)",
        r"Percentagem:\s*([\d\.,]+\s*%[^\n]*)",
        r"Garantia exigida:\s*([^\n]+)",
    ], docs)

    cpv = _best_from_docs([
        r"Vocabul[aá]rio Principal:\s*(\d{8}[^\n]*)",
        r"CPV[:\s]+(\d{8}[^\n]*)",
        r"Vocabul[aá]rio comum para os contratos p[úu]blicos[^\n]*:\s*([^\n]+)",
    ], docs)

    lotes = _best_from_docs([
        r"Procedimento com lotes\?\s*(Sim|N[aã]o)",
        r"Divis[aã]o em lotes:\s*(Sim|N[aã]o)",
    ], docs)

    local = _best_from_docs([
        r"Local da execu[cç][aã]o do contrato:\s*([^\n]+)",
        r"Local de trabalho:\s*([^\n]+)",
        r"LOCAL DA EXECU[CÇ][AÃ]O DO CONTRATO \(PROCEDIMENTO\)\s*([^\n]+)",
    ], docs)

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
        "valor": valor,
        "criterios": criterios,
        "caucao": caucao,
        "cpv": cpv,
        "lotes": lotes,
        "local": local,
        "requisitos": requisitos,
        "referencias_relevantes": refs or None,
    }
