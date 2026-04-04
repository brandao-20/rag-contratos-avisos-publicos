# LLM para análise de contratos/avisos públicos (RAG com citações)

Aplicação de demonstração com **FastAPI + React** para responder, com base documental, a perguntas sobre contratos e avisos públicos portugueses: objeto, prazos, requisitos, valor/preço base, critérios de adjudicação, entidade adjudicante/emitente, lotes, CPV, caução e local de execução.

As respostas são **ancoradas em fontes** com citações, extração estruturada e prevenção de alucinação.

## Arquitetura

```
api.py                  ← FastAPI: endpoints de saúde, bootstrap, sessões, perguntas
frontend/               ← React + Vite: UI de chats, fontes, campos, metadados
src/
  rag_pipeline.py       ← Pipeline principal (retrieval → answer → confiança)
  answer_builder.py     ← Extração direta + fallback com citações
  query_analysis.py     ← Análise de intenção + guardrails + expansão de query
  extractors.py         ← Extração estruturada determinística (10 campos)
  source_registry.py    ← Registo de fontes + metadados
  session_store.py      ← Sessões/chats persistentes em JSON
  vector_store.py       ← ChromaDB (create / load / query)
  chunking.py           ← Chunking com metadados estáveis
  embeddings.py         ← Embeddings via Ollama ou HuggingFace
  document_loaders.py   ← Carregamento de PDFs/TXT com metadados
  prompts.py            ← Prompt QA com anti-alucinação
  config.py             ← Configuração central
data/raw_docs/          ← Corpus de PDFs públicos
data/manifests/         ← sources_manifest.csv (metadados de fontes)
scripts/                ← Ingestão, validação, golden set, arranque
tests/                  ← Testes unitários + golden set
```

## Requisitos

- **Python 3.11+**
- **Node.js 18+**
- **Ollama** com modelo de embeddings (`nomic-embed-text`) e LLM opcional (`mistral`)

## Instalação

### Backend

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell

pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

## Arranque

### 1. Indexar o corpus (primeira vez ou após adicionar PDFs)

```bash
python scripts/ingest.py
# ou:
bash scripts/reindex.sh        # Linux/macOS
# scripts\reindex.bat          # Windows
```

### 2. Arrancar a API FastAPI

```bash
bash scripts/run_api.sh        # Linux/macOS
# scripts\run_api.bat          # Windows
# ou diretamente:
uvicorn api:app --reload
```

### 3. Arrancar o frontend React

```bash
bash scripts/run_frontend.sh   # Linux/macOS
# scripts\run_frontend.bat     # Windows
```

Frontend em: **http://localhost:5173**
API em: **http://localhost:8000**

## Variáveis de ambiente (opcionais)

| Variável | Valor padrão | Descrição |
|---|---|---|
| `EMBEDDING_MODEL` | `nomic-embed-text` | Modelo de embeddings Ollama |
| `LLM_MODEL` | `mistral` | Modelo LLM Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do Ollama |
| `TOP_K` | `4` | Chunks recuperados por pergunta |
| `CHUNK_SIZE` | `950` | Tamanho do chunk |

## Scripts úteis

| Script | Descrição |
|---|---|
| `scripts/ingest.py` | Indexa todos os PDFs em `data/raw_docs/` |
| `scripts/validate_pdfs.py` | Valida textualidade/estado dos PDFs |
| `scripts/build_manifest.py` | Reconstrói `sources_manifest.csv` |
| `scripts/run_golden.py` | Avalia retrieval no golden set |
| `scripts/fetch_sources.py` | Descarrega PDFs listados no manifesto |
| `scripts/clean_local_artifacts.bat` | Limpeza antes de commit |

## Testes

```bash
# Testes unitários (sem Ollama)
python -m pytest tests/test_router_publicos.py -v

# Testes de ingestão (requer corpus)
python -m pytest tests/test_ingest.py -v

# Golden set (requer Ollama + índice)
python scripts/run_golden.py
```

## Adicionar documentos ao corpus

1. Copia os PDFs para `data/raw_docs/`
2. Corre `python scripts/build_manifest.py` (reconstrói o CSV de metadados)
3. Corre `python scripts/validate_pdfs.py` (verifica textualidade)
4. Corre `python scripts/ingest.py` (re-indexa tudo)

## Campos extraídos

A aplicação extrai os seguintes campos de forma determinística:

- **Entidade adjudicante** / emitente
- **Objeto** / designação do contrato
- **Prazos** (apresentação de propostas + execução)
- **Valor / preço base**
- **Critérios de adjudicação**
- **Caução / garantia**
- **CPV** (vocabulário principal)
- **Lotes** (sim/não)
- **Local de execução**
- **Habilitações / requisitos**

## Aviso

Ferramenta de apoio à leitura documental. As respostas devem sempre ser confirmadas na fonte oficial. Esta aplicação **não substitui análise jurídica**.
