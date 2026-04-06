"""Configurações centrais do projeto RAG para avisos/contratos públicos."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DOCS_DIR = DATA_DIR / "raw_docs"
MANIFEST_DIR = DATA_DIR / "manifests"
APP_STATE_DIR = DATA_DIR / "app_state"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
TESTS_DIR = PROJECT_ROOT / "tests"

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "950"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("TOP_K", "4"))
RETRIEVAL_CANDIDATES = int(os.getenv("RETRIEVAL_CANDIDATES", "18"))

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL_NAME = os.getenv("LLM_MODEL", "mistral")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))

SESSIONS_FILE = APP_STATE_DIR / "sessions.json"
INDEX_METADATA_FILE = APP_STATE_DIR / "index_metadata.json"
GOLDEN_QA_FILE = TESTS_DIR / "golden_qa_publicos.json"

INTENT_SYNONYMS = {
    "objeto": ["objeto", "designacao", "designação", "descrição", "descricao", "contrato", "aquisição", "aquisicao", "empreitada", "serviço", "servico"],
    "prazo": ["prazo", "data limite", "dias", "prazo apresentação", "prazo de execução", "prazo de candidatura", "apresentação das propostas", "apresentacao das propostas", "prazo para apresentação"],
    "requisitos": ["requisito", "habilitação", "habilitacao", "habilitações", "participação", "participacao", "admissão", "admissao", "alvará", "alvara", "documentos de habilitação", "documentos de habilitacao"],
    "valor": ["preço base", "preco base", "valor base", "orçamento", "orcamento", "eur", "euros", "montante"],
    "criterios": ["critério", "criterio", "adjudicação", "adjudicacao", "monofator", "multifator", "ponderação", "ponderacao", "preço", "qualidade"],
    "entidade": ["entidade adjudicante", "entidade", "adjudicante", "emitente", "município", "municipio", "universidade", "secretaria", "epe"],
    "local": ["local", "execução", "execucao", "freguesia", "concelho", "distrito", "instalações", "instalacoes", "localidade"],
    "legal": ["artigo", "regime", "lei", "portaria", "decreto-lei", "fundamento legal"],
    "caucao": ["caução", "caucao", "prestação de caução", "prestacao de caucao", "garantia exigida", "garantia"],
    "cpv": ["cpv", "vocabulário principal", "vocabulário comum para os contratos públicos", "vocabulário comum", "vocabulário"],
    "lotes": ["lotes", "procedimento com lotes", "tem lotes", "há lotes", "ha lotes"],
}

QUESTION_SUGGESTIONS = [
    "Qual é o objeto deste aviso ou contrato?",
    "Qual é o preço base ou valor base?",
    "Qual é o prazo para apresentação das propostas?",
    "Existe prestação de caução?",
    "Qual é o CPV indicado?",
    "Que critérios de adjudicação são referidos?",
    "Quem é a entidade adjudicante ou emitente?",
    "O procedimento tem lotes?",
    "Qual é o prazo de execução do contrato?",
    "Que habilitações ou documentos são exigidos?",
    "Qual é o local de execução do contrato?",
]

FOLLOW_UP_BY_INTENT = {
    "objeto": [
        "Existe preço base ou valor base?",
        "Qual é o prazo de execução do contrato?",
        "Qual é o CPV indicado?",
    ],
    "prazo": [
        "Existe prestação de caução?",
        "Que critérios de adjudicação são referidos?",
        "Quem é a entidade adjudicante?",
    ],
    "requisitos": [
        "Existe alvará ou habilitação específica?",
        "Há documentos obrigatórios na candidatura?",
        "Qual é o prazo de apresentação?",
    ],
    "valor": [
        "Existe prestação de caução?",
        "O procedimento tem lotes?",
        "Qual é o critério de adjudicação?",
    ],
    "criterios": [
        "Existe preço base?",
        "Qual é o prazo para apresentação das propostas?",
        "Há negociação prevista?",
    ],
    "caucao": [
        "Qual é a percentagem da caução?",
        "Qual é o preço base?",
        "O procedimento tem lotes?",
    ],
    "cpv": [
        "Qual é o objeto do contrato?",
        "Qual é o preço base?",
        "Qual é o prazo de apresentação das propostas?",
    ],
    "lotes": [
        "Existe preço base?",
        "Qual é o objeto do contrato?",
        "Qual é o critério de adjudicação?",
    ],
}


def ensure_directories() -> None:
    RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def get_model_names() -> tuple[str, str]:
    embedding = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL_NAME)
    llm = os.getenv("LLM_MODEL", LLM_MODEL_NAME)
    return embedding, llm
