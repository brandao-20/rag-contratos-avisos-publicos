# LLM para análise de contratos/avisos públicos (RAG com citações)

Produto de demonstração para responder, com base documental, a perguntas sobre **contratos e avisos públicos**: objeto, prazos, requisitos, valor/preço base, critérios de adjudicação, entidade adjudicante/emitente, lotes, CPV, caução, local de execução e outros campos relevantes.

## Arquitetura final

- **Backend Python (FastAPI)** para ingestão, indexação, retrieval, answer builder, extração estruturada e chats persistentes
- **Frontend React** para chats, perguntas sugeridas, fontes, campos extraídos, metadados e UX final

A base antiga em Streamlit deixou de ser a interface principal e já não faz parte do fluxo recomendado de arranque.

## Objetivo funcional

- responder em linguagem natural com base no corpus carregado
- apresentar **citações das fontes**
- extrair **informação estruturada** quando os campos são explícitos no documento
- evitar respostas inventadas fora da evidência documental
- permitir uma demonstração simples, limpa e testável

## Requisitos

- Python 3.11+
- Node.js 18+
- ambiente virtual Python (`.venv`)

## Instalação

### 1) Backend base

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### 2) Frontend

```powershell
cd frontend
npm install
cd ..
```

## Arranque recomendado

### Backend API

```powershell
scripts/run_api.bat
```

### Frontend React

```powershell
scripts/run_frontend.bat
```

## Scripts que fazem sentido manter

- `scripts/ingest.py` — ingestão e indexação do corpus
- `scripts/reindex.bat` / `scripts/reindex.sh` — atalho para reindexação
- `scripts/fetch_sources.py` — descarrega PDFs listados no manifesto/urls
- `scripts/build_manifest.py` — reconstrói `sources_manifest.csv`
- `scripts/validate_pdfs.py` / `.bat` — valida textualidade/estado dos PDFs
- `scripts/run_golden.py` / `.bat` — avaliação simples em golden set
- `scripts/run_api.bat` — arranque local da FastAPI
- `scripts/run_frontend.bat` — arranque local do frontend React
- `scripts/clean_local_artifacts.bat` — limpeza local antes de commit/empacotamento

## Scripts/ficheiros que já não fazem sentido manter

- `app.py` — launcher legado de Streamlit
- `src/ui_helpers.py` — helpers exclusivos do legado Streamlit
- `scripts/run_app.bat` — launcher do legado Streamlit
- `scripts/run_stack_notes.txt` — redundante face ao README

## Fluxo mínimo de regressão

Confirmar no mínimo:

1. `GET /health` sem erro crítico
2. criação/listagem/apagamento de chats
3. pergunta manual
4. retrieval + resposta
5. citações/fontes
6. extração estruturada
7. perguntas sugeridas só na última resposta
8. dark/light mode coerentes
9. sem sobreposições visuais graves

## Limpeza antes de commit

```powershell
scripts/clean_local_artifacts.bat
```

Isto remove artefactos locais como `__pycache__`, `frontend/node_modules`, `frontend/dist`, `.pytest_cache`, `.vite`, `data/app_state/sessions.json` e `tests/golden_report_publicos.json`.

## Estrutura relevante

```text
README.md
api.py
requirements.txt
requirements-api.txt
frontend/
scripts/
  ingest.py
  reindex.bat
  run_api.bat
  run_frontend.bat
  clean_local_artifacts.bat
src/
  rag_pipeline.py
  answer_builder.py
  query_analysis.py
  extractors.py
  source_registry.py
  vector_store.py
  embeddings.py
tests/
  golden_qa_publicos.json
```

## Aviso

Ferramenta de apoio à leitura documental. Confirmar sempre a informação na fonte oficial. Não substitui análise jurídica.
