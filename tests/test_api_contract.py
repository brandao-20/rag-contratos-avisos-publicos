"""Testes leves do contrato HTTP da API, sem depender do backend RAG completo."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import app
from src import config


client = TestClient(app)


def setup_module() -> None:
    config.ensure_directories()
    if config.SESSIONS_FILE.exists():
        config.SESSIONS_FILE.unlink()



def teardown_module() -> None:
    if config.SESSIONS_FILE.exists():
        config.SESSIONS_FILE.unlink()



def test_bootstrap_endpoint() -> None:
    res = client.get("/bootstrap")
    assert res.status_code == 200
    body = res.json()
    assert body["product_title"]
    assert isinstance(body["question_suggestions"], list)
    assert isinstance(body["categories"], list)



def test_corpus_and_glossary_endpoints() -> None:
    corpus = client.get("/corpus/overview")
    glossary = client.get("/glossary")
    assert corpus.status_code == 200
    assert glossary.status_code == 200
    assert isinstance(corpus.json(), list)
    assert isinstance(glossary.json(), list)
    assert glossary.json()[0]["term"]



def test_session_crud_contract() -> None:
    created = client.post("/sessions", json={"title": "Teste API"})
    assert created.status_code == 201
    session = created.json()
    session_id = session["id"]

    listing = client.get("/sessions")
    assert listing.status_code == 200
    assert any(item["id"] == session_id for item in listing.json())

    patch = client.patch(f"/sessions/{session_id}", json={"title": "Novo título"})
    assert patch.status_code == 200
    assert patch.json()["title"] == "Novo título"

    ask = client.post(f"/sessions/{session_id}/ask", json={"query": "Qual é o objeto?", "category": "todos"})
    assert ask.status_code in {200, 503}

    deleted = client.delete(f"/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True



def test_health_endpoint() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
