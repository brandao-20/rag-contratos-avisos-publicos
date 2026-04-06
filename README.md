# LLM para análise de contratos/avisos públicos (RAG com citações)

Aplicação académica com **FastAPI + React/Vite** para consultar contratos e avisos públicos em linguagem natural, com foco em:

- objeto / designação,
- entidade adjudicante / emitente,
- prazo para propostas e prazo de execução,
- valor ou preço base,
- critérios de adjudicação,
- caução / garantia,
- CPV,
- lotes,
- local de execução,
- habilitações / requisitos.

A resposta é sempre apresentada com **fontes agrupadas, citações, confiança explicada, extração estruturada** e um fluxo de UI preparado para demonstração final.

## Principais melhorias desta versão

- UI reorganizada em **sidebar + conversa + inspeção** com home mais limpa.
- **Pesquisa de chats**, favoritos locais, exportação de conversa e feedback discreto.
- Modos dedicados para **Conversar**, **Explorar corpus** e **Glossário**.
- **Inspeção de citação** no painel direito.
- Respostas procedimentais com **passos sugeridos** quando a pergunta o justifica.
- Endpoints adicionais para **exploração do corpus** e **glossário**.
- Backend mantido em **FastAPI + motor RAG Python**, sem regressar a Streamlit.

## Arquitetura

```text
api.py                  -> FastAPI: health, bootstrap, sessões, perguntas, corpus, glossário
frontend/               -> React + Vite: UI final
src/
  rag_pipeline.py       -> pipeline principal (retrieval -> answer -> confiança)
  answer_builder.py     -> extração direta, fallback, passos procedimentais
  query_analysis.py     -> análise de intenção, expansão de query, guardrails
  extractors.py         -> extração estruturada determinística
  source_registry.py    -> manifesto + metadados + agrupamento de fontes
  session_store.py      -> persistência local de chats
  catalog.py            -> exploração do corpus + glossário do domínio
  document_loaders.py   -> leitura dos PDFs
  chunking.py           -> chunking com metadados estáveis
  embeddings.py         -> embeddings via Ollama ou fallback HuggingFace
  vector_store.py       -> ChromaDB
scripts/                -> ingestão, manifesto, validação, arranque, golden
tests/                  -> smoke tests do contrato HTTP e testes do projeto
```

## Requisitos

- Python 3.11+
- Node.js 18+
- Dependências Python de `requirements.txt` e `requirements-api.txt`
- Opcional mas recomendado: **Ollama** com `nomic-embed-text` e `mistral`

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

### 1) Ingerir / reindexar o corpus

```bash
python scripts/ingest.py
# ou
bash scripts/reindex.sh        # Linux/macOS
# scripts\reindex.bat         # Windows
```

### 2) Arrancar a API

```bash
bash scripts/run_api.sh        # Linux/macOS
# scripts\run_api.bat         # Windows
# ou diretamente:
uvicorn api:app --reload
```

### 3) Arrancar o frontend

```bash
bash scripts/run_frontend.sh   # Linux/macOS
# scripts\run_frontend.bat    # Windows
```

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`

## Endpoints úteis

- `GET /health`
- `GET /bootstrap`
- `GET /corpus/overview`
- `GET /glossary`
- `GET /sessions`
- `POST /sessions`
- `PATCH /sessions/{id}`
- `DELETE /sessions/{id}`
- `POST /sessions/{id}/ask`

## Scripts úteis

- `scripts/ingest.py` -> indexa todos os PDFs em `data/raw_docs/`
- `scripts/build_manifest.py` -> reconstrói `sources_manifest.csv`
- `scripts/validate_pdfs.py` -> gera relatório JSON/CSV de qualidade dos PDFs
- `scripts/run_golden.py` -> avaliação simples sobre o golden set
- `scripts/fetch_sources.py` -> descarrega PDFs listados no manifesto ou em `urls_dr.txt`

## Testes

```bash
python -m pytest tests/test_api_contract.py -v
python -m pytest tests/test_router_publicos.py -v
python -m pytest tests/test_ingest.py -v
```

## Fluxo de demo recomendado

1. Abrir a home e mostrar perguntas sugeridas.
2. Criar um chat e perguntar por objeto, preço base, prazo e entidade.
3. Mostrar a inspeção da resposta: **fontes**, **campos** e **metadados**.
4. Abrir a vista **Explorar corpus**.
5. Abrir o **Glossário**.
6. Mostrar exportação do chat e favoritos locais.

## Limites conhecidos

- O melhor desempenho exige **índice vetorial existente** e dependências RAG instaladas.
- O uso de LLM é opcional; quando indisponível, a aplicação continua a responder por extração direta ou fallback documental.
- Ferramenta de apoio à leitura: **não substitui análise jurídica**.
