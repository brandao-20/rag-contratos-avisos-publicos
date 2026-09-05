# Public Procurement RAG

A Retrieval-Augmented Generation (RAG) application for exploring Portuguese public procurement documents through natural-language queries.

The system combines semantic retrieval, structured information extraction and source-grounded answer generation to help users inspect procurement notices and contracts while keeping each answer traceable to the underlying documents.

## Features

### Source-Grounded Question Answering

Ask natural-language questions about public procurement documents and receive answers grounded in retrieved source content.

The system can identify information such as:

- procurement object or description
- contracting authority
- base price or contract value
- submission deadlines
- execution periods
- award criteria
- guarantees and bid bonds
- CPV codes
- lots
- execution location
- qualification requirements

### Retrieval-Augmented Generation

The retrieval pipeline supports:

- vector search with ChromaDB
- semantic embeddings
- lexical fallback retrieval
- query analysis and intent detection
- retrieval query expansion
- source prioritisation
- document-level focus for follow-up questions

If the vector index is unavailable, the application can continue operating through a local lexical retrieval fallback.

### Source Citations

Answers include traceable evidence from the retrieved documents.

The application exposes:

- grouped sources
- document titles
- page references
- citation excerpts
- primary source identification
- retrieval backend information

This makes it possible to inspect the evidence behind an answer instead of treating the generated response as a standalone result.

### Structured Extraction

Alongside the generated answer, the backend extracts structured procurement information from retrieved documents.

Examples include:

```text
Contracting authority
Procurement object
Base price
Submission deadline
Execution period
CPV
Lots
Award criteria
Guarantee
Execution location
```

Structured extraction is performed separately from the generated answer to provide more predictable access to important fields.

### Confidence Information

Each answer includes an internal confidence assessment based on retrieval and evidence quality.

The API returns:

- confidence label
- confidence score
- confidence reasons
- citation count
- retrieval latency

The confidence indicator is intended as an explainability aid and not as a guarantee of factual correctness.

### Persistent Conversations

The application supports persistent chat sessions with:

- conversation history
- automatically generated chat titles
- contextual follow-up questions
- active document context
- saved responses

Short follow-up questions can remain focused on the previously selected procurement procedure.

### Corpus Explorer

The frontend includes a corpus exploration mode for inspecting the documents available to the RAG system.

### Procurement Glossary

A dedicated glossary provides short explanations of procurement-related terminology and related concepts.

### Evaluation

The project includes:

- API contract tests
- ingestion tests
- retrieval and routing tests
- a curated golden question set
- a dedicated evaluation script

## Tech Stack

### AI / RAG

- Python
- LangChain
- ChromaDB
- Sentence Transformers
- Ollama
- Mistral
- `nomic-embed-text`
- Hugging Face embeddings fallback
- PyPDF

### Backend

- FastAPI
- Uvicorn
- Pydantic

### Frontend

- React
- Vite
- JavaScript

### Testing

- Pytest

## Architecture

```text
┌──────────────────────┐
│     React Frontend   │
│        Vite          │
└──────────┬───────────┘
           │
           │ HTTP / JSON
           ▼
┌──────────────────────┐
│      FastAPI API     │
│ Sessions · Sources   │
│ Corpus · Glossary    │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────┐
│        RAG Pipeline         │
│                             │
│  Query Analysis             │
│         │                   │
│         ▼                   │
│  Retrieval Query Expansion  │
│         │                   │
│         ▼                   │
│  Vector / Lexical Retrieval │
│         │                   │
│         ▼                   │
│  Source Selection           │
│         │                   │
│         ▼                   │
│  Structured Extraction      │
│         │                   │
│         ▼                   │
│  Grounded Answer Builder    │
└──────────┬──────────────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌───────────┐  ┌───────────────┐
│ ChromaDB  │  │ Local Corpus  │
│  Vectors  │  │ Lexical Search│
└───────────┘  └───────────────┘
     │
     ▼
┌──────────────────────┐
│  Optional Local LLM  │
│   Ollama / Mistral   │
└──────────────────────┘
```

## Retrieval Strategy

The application supports multiple runtime modes depending on the available local services.

### Vector + LLM

When a compatible ChromaDB index and Ollama models are available:

```text
Query
  ↓
Query analysis
  ↓
Semantic retrieval
  ↓
Source ranking
  ↓
Context construction
  ↓
Local LLM synthesis
  ↓
Grounded answer + citations
```

### Vector Only

If the vector index is available but the LLM is not, retrieved evidence can still be processed through the deterministic answer-building pipeline.

### Lexical Fallback

If vector retrieval cannot be used, the system falls back to local lexical document retrieval.

This allows the application to remain usable without requiring every AI service to be running.

## Embeddings

The default embedding model is:

```text
nomic-embed-text
```

When the configured Ollama embedding model is unavailable, the project can fall back to:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The provider and model used to build the index are recorded in the local index metadata.

## Local LLM

The default local language model is:

```text
mistral
```

LLM generation is optional.

The backend checks whether the configured Ollama model is available before enabling LLM-based answer synthesis.

## Project Structure

```text
public-procurement-rag/
├── api.py
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── src/
│   ├── answer_builder.py
│   ├── catalog.py
│   ├── chunking.py
│   ├── config.py
│   ├── document_loaders.py
│   ├── embeddings.py
│   ├── extractors.py
│   ├── local_retrieval.py
│   ├── prompts.py
│   ├── query_analysis.py
│   ├── rag_pipeline.py
│   ├── retriever.py
│   ├── session_store.py
│   ├── source_registry.py
│   └── vector_store.py
├── scripts/
│   ├── build_manifest.py
│   ├── fetch_sources.py
│   ├── ingest.py
│   ├── reindex.sh
│   ├── reindex.bat
│   ├── run_api.sh
│   ├── run_api.bat
│   ├── run_frontend.sh
│   ├── run_frontend.bat
│   ├── run_golden.py
│   └── validate_pdfs.py
├── tests/
│   ├── golden_qa_publicos.json
│   ├── test_api_contract.py
│   ├── test_ingest.py
│   └── test_router_publicos.py
├── data/
├── requirements.txt
├── requirements-api.txt
├── .env.example
└── README.md
```

## Getting Started

### Requirements

- Python 3.11+
- Node.js 18+
- npm

Optional:

- Ollama

## Installation

Clone the repository:

```bash
git clone https://github.com/brandao-20/public-procurement-rag.git
cd public-procurement-rag
```

### Python Environment

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### Frontend

Install the frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

## Configuration

Create a local environment file from the provided example.

macOS / Linux:

```bash
cp .env.example .env
```

Windows:

```powershell
Copy-Item .env.example .env
```

Default configuration:

```env
LLM_MODEL=mistral
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
CHUNK_SIZE=950
CHUNK_OVERLAP=150
TOP_K=6
```

The frontend can also be configured through:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Optional Ollama Setup

If you want to use the default local AI models, install Ollama and download:

```bash
ollama pull nomic-embed-text
ollama pull mistral
```

The application can still operate in reduced modes when Ollama is unavailable.

## Preparing the Corpus

Place the procurement PDF documents inside:

```text
data/raw_docs/
```

The ingestion pipeline reads the documents, splits them into chunks, generates embeddings and creates the local ChromaDB index.

Run:

```bash
python scripts/ingest.py
```

Alternatively:

macOS / Linux:

```bash
bash scripts/reindex.sh
```

Windows:

```powershell
.\scripts\reindex.bat
```

The resulting vector database is stored locally in:

```text
chroma_db/
```

## Running the Application

### Backend

Run the FastAPI server:

```bash
uvicorn api:app --reload
```

Or use the provided script.

macOS / Linux:

```bash
bash scripts/run_api.sh
```

Windows:

```powershell
.\scripts\run_api.bat
```

The API is available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

### Frontend

From the `frontend/` directory:

```bash
npm run dev
```

Or use the provided script.

macOS / Linux:

```bash
bash scripts/run_frontend.sh
```

Windows:

```powershell
.\scripts\run_frontend.bat
```

The frontend is available at:

```text
http://localhost:5173
```

## API Capabilities

The FastAPI backend provides functionality for:

- application bootstrap and backend status
- persistent chat sessions
- natural-language questions
- source citations
- saved responses
- corpus exploration
- procurement glossary
- diagnostics

The response model includes both human-readable and machine-readable information, including:

```text
Answer
Intent
Retrieval query
Sources
Structured fields
Confidence
Follow-up questions
Procedural steps
Retrieval backend
Primary source
Latency
```

## Testing

Run the API contract tests:

```bash
python -m pytest tests/test_api_contract.py -v
```

Run the retrieval and routing tests:

```bash
python -m pytest tests/test_router_publicos.py -v
```

Run the ingestion tests:

```bash
python -m pytest tests/test_ingest.py -v
```

Run all tests:

```bash
python -m pytest tests -v
```

## Golden-Set Evaluation

The project includes a curated question set for evaluating retrieval and answer behaviour.

Run:

```bash
python scripts/run_golden.py
```

The golden set is stored in:

```text
tests/golden_qa_publicos.json
```

## PDF Validation

Documents can be checked before ingestion with:

```bash
python scripts/validate_pdfs.py
```

This helps identify problematic source files before they enter the retrieval pipeline.

## Design Goals

The project was built around four main principles:

### Grounded Answers

Generated responses should remain anchored to retrieved evidence.

### Inspectable Sources

Users should be able to see which documents and excerpts contributed to an answer.

### Graceful Degradation

The system should remain usable when optional local AI components are unavailable.

### Structured Information

Important procurement fields should be available in structured form in addition to natural-language answers.

## Limitations

- Answer quality depends on the quality and coverage of the indexed documents.
- OCR is not part of the core ingestion pipeline, so image-only PDFs may require preprocessing.
- The confidence score is an internal evidence-quality indicator, not a probability of correctness.
- Local LLM quality depends on the configured Ollama model.
- The application is intended to assist document exploration and does not replace legal or procurement expertise.

## Purpose

This project was developed as an applied RAG and information-retrieval system, with emphasis on:

- retrieval architecture
- local LLM integration
- embeddings
- vector databases
- structured extraction
- citations
- explainability
- fallback strategies
- API design
- conversational interfaces
- evaluation

It is presented here as a portfolio project demonstrating applied AI and software engineering.
