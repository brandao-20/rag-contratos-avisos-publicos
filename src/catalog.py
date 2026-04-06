"""Catálogo de exploração do corpus e glossário do domínio público.

Este módulo não inventa fontes documentais; apenas organiza o manifesto existente
em vistas úteis para demonstração e navegação da UI.
"""

from __future__ import annotations


from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .source_registry import SourceRecord, load_source_registry


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    category: str
    short_definition: str
    why_it_matters: str
    related_terms: tuple[str, ...] = ()


_GLOSSARY: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        term="Entidade adjudicante",
        category="atores",
        short_definition="Organismo público ou entidade que promove o procedimento e celebra o contrato.",
        why_it_matters="É a referência institucional principal do aviso e ajuda a contextualizar a origem da peça documental.",
        related_terms=("emitente", "procedimento", "contrato"),
    ),
    GlossaryEntry(
        term="Objeto do contrato",
        category="conteúdo",
        short_definition="Descrição do bem, serviço ou empreitada que se pretende adquirir ou executar.",
        why_it_matters="Costuma ser o primeiro campo a consultar para perceber o âmbito real do procedimento.",
        related_terms=("designação", "descrição", "CPV"),
    ),
    GlossaryEntry(
        term="Preço base",
        category="valor",
        short_definition="Montante máximo ou valor de referência definido para o procedimento, quando aplicável.",
        why_it_matters="Influencia a análise económica, a necessidade de caução e a leitura das condições financeiras do contrato.",
        related_terms=("valor base", "orçamento", "proposta"),
    ),
    GlossaryEntry(
        term="Prazo para apresentação de propostas",
        category="prazos",
        short_definition="Data ou período dentro do qual as propostas podem ser submetidas.",
        why_it_matters="É um dos campos mais críticos para participação e costuma surgir de forma explícita no aviso.",
        related_terms=("candidatura", "prazo de execução", "proposta"),
    ),
    GlossaryEntry(
        term="Prazo de execução",
        category="prazos",
        short_definition="Intervalo temporal previsto para executar o contrato após adjudicação.",
        why_it_matters="Ajuda a avaliar a duração do compromisso contratual e a viabilidade operacional.",
        related_terms=("validade", "cronograma", "local de execução"),
    ),
    GlossaryEntry(
        term="Critério de adjudicação",
        category="avaliação",
        short_definition="Regra usada para comparar propostas e decidir a adjudicação.",
        why_it_matters="Indica se o foco está apenas no preço ou numa combinação de fatores qualitativos e quantitativos.",
        related_terms=("monofator", "multifator", "ponderação"),
    ),
    GlossaryEntry(
        term="Caução",
        category="garantias",
        short_definition="Garantia financeira que pode ser exigida ao adjudicatário para assegurar o cumprimento do contrato.",
        why_it_matters="Pode ter impacto financeiro relevante e nem sempre é exigida em todos os procedimentos.",
        related_terms=("garantia", "percentagem", "adjudicatário"),
    ),
    GlossaryEntry(
        term="CPV",
        category="classificação",
        short_definition="Código do Vocabulário Comum para os Contratos Públicos, usado para classificar o objeto do procedimento.",
        why_it_matters="Facilita a pesquisa temática e ajuda a validar se o procedimento pertence ao domínio esperado.",
        related_terms=("vocabulário principal", "objeto do contrato"),
    ),
    GlossaryEntry(
        term="Lote",
        category="estrutura",
        short_definition="Parcela autónoma de um procedimento que pode ser adjudicada separadamente.",
        why_it_matters="Muda a forma como o concurso é analisado e pode permitir participação parcial.",
        related_terms=("procedimento com lotes", "preço base", "objeto"),
    ),
    GlossaryEntry(
        term="Habilitações",
        category="requisitos",
        short_definition="Conjunto de documentos ou condições exigidos para demonstrar aptidão legal, técnica ou financeira.",
        why_it_matters="Sem estas evidências a proposta pode ser excluída, mesmo que o preço seja competitivo.",
        related_terms=("documentos de habilitação", "alvará", "requisitos"),
    ),
    GlossaryEntry(
        term="Caderno de encargos",
        category="peças",
        short_definition="Documento que fixa as cláusulas técnicas e jurídicas a cumprir na execução do contrato.",
        why_it_matters="Mesmo quando não está totalmente no corpus, é uma peça central para interpretar obrigações e condições.",
        related_terms=("peças do procedimento", "execução", "requisitos"),
    ),
    GlossaryEntry(
        term="Procedimento",
        category="estrutura",
        short_definition="Processo formal de contratação pública a que o aviso ou contrato diz respeito.",
        why_it_matters="Serve de enquadramento para prazos, critérios, peças documentais e modo de participação.",
        related_terms=("anúncio", "contrato", "adjudicação"),
    ),
)


def _source_preview(source: SourceRecord) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "title": source.title,
        "entity": source.entity,
        "document_type": source.document_type,
        "source_url": source.url,
        "notes": source.notes,
    }


def _sorted_sources(items: Iterable[SourceRecord]) -> list[SourceRecord]:
    return sorted(items, key=lambda item: ((item.entity or ""), item.title.lower()))


def build_corpus_overview() -> list[dict[str, Any]]:
    registry = list(load_source_registry().values())
    if not registry:
        return []

    municipalities = [
        source for source in registry
        if (source.entity or "").lower().startswith(("município", "municipio"))
    ]
    institutions = [source for source in registry if source not in municipalities]

    sections: list[dict[str, Any]] = [
        {
            "id": "todos",
            "label": "Corpus regional do Minho",
            "description": "Conjunto curado de anúncios de procedimento focado no Minho, preparado para reduzir saltos semânticos e manter as respostas ancoradas num procedimento concreto.",
            "sources_count": len(registry),
            "example_questions": [
                "Procura um procedimento do Município de Braga com preço base explícito.",
                "Mostra um procedimento do Minho onde exista prestação de caução.",
                "Mostra um procedimento com CPV explícito e preço base identificado.",
            ],
            "sources": [],
        }
    ]

    if municipalities:
        sections.append(
            {
                "id": "municipios",
                "label": "Municípios do Minho",
                "description": "Procedimentos emitidos por municípios da região, úteis para perguntas sobre objeto, preço base, prazo, lotes, local e critérios.",
                "sources_count": len(municipalities),
                "example_questions": [
                    "Procura um procedimento do Município de Amares e identifica o objeto.",
                    "Mostra um procedimento de Arcos de Valdevez e verifica se tem lotes.",
                    "Procura um procedimento de Viana do Castelo e indica o prazo de apresentação.",
                ],
                "sources": [_source_preview(source) for source in _sorted_sources(municipalities)[:10]],
            }
        )

    if institutions:
        sections.append(
            {
                "id": "saude_ensino",
                "label": "Saúde e ensino públicos",
                "description": "Fontes da Universidade do Minho, SASUM e unidades locais de saúde, úteis para demonstrar casos com lotes, CPV, preço base e critérios multifator.",
                "sources_count": len(institutions),
                "example_questions": [
                    "Procura um procedimento da Universidade do Minho com preço base explícito.",
                    "Mostra um procedimento da ULS Braga e identifica o prazo de apresentação.",
                    "Procura um procedimento do ensino superior com lotes explícitos.",
                ],
                "sources": [_source_preview(source) for source in _sorted_sources(institutions)[:10]],
            }
        )

    return sections


def get_glossary_entries() -> list[dict[str, Any]]:
    return [asdict(entry) for entry in _GLOSSARY]
