"""Catálogo de exploração do corpus e glossário do domínio público.

Este módulo não inventa fontes documentais; apenas organiza o manifesto existente
em vistas úteis para demonstração e navegação da UI.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from .source_registry import SourceRecord, load_source_registry


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    category: str
    short_definition: str
    why_it_matters: str
    related_terms: tuple[str, ...] = ()


_THEME_BLUEPRINTS = [
    {
        "id": "contratacao_publica",
        "label": "Contratação pública",
        "description": "Peças e anúncios de procedimento de contratação pública, curados para a zona do Minho e centrados em objeto, prazo, preço base, critérios, caução, CPV, lotes e entidade adjudicante.",
        "example_questions": [
            "Qual é o objeto do procedimento?",
            "Existe preço base ou orçamento?",
            "Há divisão em lotes?",
        ],
    },
    {
        "id": "aviso_publico",
        "label": "Avisos públicos",
        "description": "Avisos publicados e respetivos elementos formais, como prazos, entidade emitente e enquadramento do procedimento.",
        "example_questions": [
            "Qual é o prazo para apresentação das propostas?",
            "Quem é a entidade adjudicante?",
            "Que CPV é indicado?",
        ],
    },
    {
        "id": "documento_publico",
        "label": "Outros documentos públicos",
        "description": "Documentação complementar ou peças de apoio presentes no corpus local da demonstração.",
        "example_questions": [
            "Que requisitos ou habilitações são exigidos?",
            "Existe prestação de caução?",
            "Qual é o local de execução?",
        ],
    },
]

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



def build_corpus_overview() -> list[dict[str, Any]]:
    registry = list(load_source_registry().values())
    by_category: dict[str, list[SourceRecord]] = defaultdict(list)
    for source in registry:
        by_category[source.category].append(source)

    sections: list[dict[str, Any]] = []
    for blueprint in _THEME_BLUEPRINTS:
        sources = sorted(
            by_category.get(blueprint["id"], []),
            key=lambda item: ((item.entity or ""), item.title.lower()),
        )
        sections.append(
            {
                "id": blueprint["id"],
                "label": blueprint["label"],
                "description": blueprint["description"],
                "sources_count": len(sources),
                "example_questions": list(blueprint["example_questions"]),
                "sources": [_source_preview(source) for source in sources[:8]],
            }
        )

    if registry:
        sections.insert(
            0,
            {
                "id": "todos",
                "label": "Corpus completo",
                "description": "Vista agregada do corpus regional do Minho disponível para a demonstração, sem alterar ou inventar fontes.",
                "sources_count": len(registry),
                "example_questions": [
                    "Qual é a entidade adjudicante deste procedimento?",
                    "Existe preço base ou valor de referência?",
                    "Que requisitos e documentos são mencionados?",
                ],
                "sources": [_source_preview(source) for source in sorted(registry, key=lambda item: item.title.lower())[:10]],
            },
        )
    return sections



def get_glossary_entries() -> list[dict[str, Any]]:
    return [asdict(entry) for entry in _GLOSSARY]
