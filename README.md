# Analisador de Contratos e Avisos Públicos (RAG com Citações)

Este projecto implementa uma aplicação em **Python** que utiliza **Grandes Modelos de Linguagem (LLM)** e um motor de **Recuperação aumentada por geração (RAG)** para analisar contratos e avisos públicos. O objectivo é permitir que qualquer utilizador coloque perguntas em linguagem natural sobre um conjunto de documentos (por exemplo, avisos de abertura de concursos públicos, anúncios de procedimentos, etc.) e obtenha respostas baseadas nos conteúdos desses documentos, com **citações** das fontes e uma **extração estruturada** de informação relevante.

## Funcionalidades Principais

1. **Ingestão de documentos** a partir de uma pasta local (`data/raw_docs/`). São suportados ficheiros `.pdf`, `.txt` e `.md` com texto pesquisável.
2. **Extração e limpeza de texto**: os documentos são lidos, o texto é limpo e normalizado e são guardados metadados (ficheiro, página, etc.).
3. **Segmentação em blocos (chunking)** com sobreposição configurável para preservar o contexto.
4. **Criação de embeddings e indexação** usando **ChromaDB** com persistência local.
5. **Interface web em Streamlit** (Português de Portugal) onde o utilizador pode colocar perguntas, ver as respostas do modelo e as citações das fontes.
6. **Extração estruturada de informação‑chave** (entidade, objecto, prazos, requisitos, valor, critérios) em formato JSON.
7. **Mensagens de fallback** quando não existe informação suficiente no corpus.
8. **Scripts de apoio** para ingestão de documentos, reindexação e (opcionalmente) download automático das fontes reais.

## Arquitectura Resumida

O projecto segue uma arquitectura modular organizada em `src/`:

- `config.py` – configurações centrais (modelo a usar no Ollama, tamanhos de chunk, caminhos, etc.).
- `document_loaders.py` – funções para carregar e limpar documentos de diferentes formatos.
- `chunking.py` – responsável por cortar documentos em blocos de tamanho fixo com sobreposição.
- `embeddings.py` – instanciação do modelo de embeddings (por omissão usa `OllamaEmbeddings`, com fallback para um modelo leve se `ollama` não estiver disponível).
- `vector_store.py` – criação e carregamento do índice ChromaDB.
- `retriever.py` – wrapper que expõe métodos de recuperação `top_k` sobre o índice.
- `prompts.py` – templates de prompts em Português usados para Q&A e extração estruturada.
- `rag_pipeline.py` – combina o LLM e o vector store para gerar respostas baseadas no contexto e extrair informação estruturada.
- `ui_helpers.py` – funções auxiliares para a interface em Streamlit.
- `app.py` – aplicação Streamlit pronta a correr com `streamlit run app.py`.

Na pasta `scripts/` existem scripts adicionais para ingestão (`ingest.py`), para reindexar rapidamente (`reindex.sh`) e para descarregar as fontes listadas em `sources_manifest.csv` (`fetch_sources.py`).

## Tecnologias Usadas

| Tecnologia           | Descrição                                                                                             |
|----------------------|-------------------------------------------------------------------------------------------------------|
| **Python 3.11+**     | Linguagem de programação principal.                                                                   |
| **Streamlit**        | Framework para a interface web, permitindo criar rapidamente aplicações interactivas.                  |
| **Ollama**           | Backend local para LLMs e embeddings (ex.: `mistral` ou `llama2`). É necessário instalar localmente. |
| **LangChain**        | Biblioteca para orquestrar LLMs, embeddings e pipelines de RAG.                                        |
| **ChromaDB**         | Base de dados vetorial open‑source com persistência local para indexação dos embeddings.              |
| **pypdf**            | Extracção de texto de documentos PDF.                                                                 |

## Como Cumpre os Requisitos Académicos

* **Utilidade clara** – Permite analisar avisos e contratos públicos, extrair prazos, requisitos e objectos do contrato e responder a perguntas específicas com evidência textual.
* **Projeto funcional** – Inclui todo o código fonte, dados de exemplo e scripts de ingestão; a aplicação corre localmente via Streamlit.
* **Testabilidade** – Um corpus real de demonstração está incluído (ficheiros `.txt` provenientes de avisos públicos) e existem scripts e testes básicos para garantir o funcionamento.
* **Exequível em 15 dias** – O escopo foi controlado para garantir uma implementação realista e estável sem over‑engineering.
* **Trabalho individual** – A estrutura modular favorece a compreensão e modificação por uma única pessoa.

## Pré‑requisitos

Antes de executar a aplicação, garanta que tem:

1. **Python 3.11 ou superior** instalado.
2. **Ollama** instalado localmente. Pode ser obtido em [https://ollama.com/](https://ollama.com/) e instalado conforme as instruções para o seu sistema operativo.
3. Pelo menos um modelo LLM e um modelo de embeddings disponíveis no Ollama. Este projecto utiliza, por omissão, o modelo `mistral` (7B) tanto para geração como para embeddings. Instale‑o com:
   ```bash
   ollama pull mistral
   ```
4. Recomenda‑se a criação de um ambiente virtual Python.

## Instalação

1. **Clonar ou descompactar** este repositório.
2. Navegar para a pasta do projecto:
   ```bash
   cd public_docs_rag
   ```
3. Instalar as dependências Python:
   ```bash
   pip install -r requirements.txt
   ```

## Como Correr a Aplicação

1. Verifique que o serviço `ollama` está a correr na sua máquina e que o modelo requerido está disponível (ex.: `mistral`).
2. Ingerir os documentos (apenas necessário na primeira execução ou após adicionar novos documentos):
   ```bash
   python scripts/ingest.py
   ```
   Este script lê os ficheiros em `data/raw_docs/`, cria o índice ChromaDB em `chroma_db/` e guarda os metadados.
3. Iniciar a aplicação Streamlit:
   ```bash
   streamlit run app.py
   ```
4. Abrir o browser na morada fornecida pela Streamlit (habitualmente `http://localhost:8501`).

## Adicionar ou Substituir Documentos

1. Coloque novos ficheiros `.pdf`, `.txt` ou `.md` na pasta `data/raw_docs/`.
2. Actualize ou adicione as entradas correspondentes em `data/manifests/sources_manifest.csv`, indicando o URL de origem e outros metadados.
3. Execute novamente `python scripts/ingest.py` para reindexar.

## Corpus de Demonstração

Incluímos um pequeno conjunto de avisos e anúncios reais em formato `.txt` na pasta `data/raw_docs/`. Estes ficheiros foram criados a partir de documentos oficiais publicados no **Diário da República** e em sites de entidades públicas (ver `data/manifests/sources_manifest.csv`). Devido a restrições de download automático de alguns sites, os ficheiros PDF originais podem não estar incluídos ou podem estar bloqueados para download automático; cada linha do manifesto indica a **URL de origem**, a entidade responsável, a data de recolha e notas sobre o tipo de documento.

Se pretender obter os ficheiros originais, pode utilizar o script `scripts/fetch_sources.py` (quando aplicável) ou seguir as instruções no manifesto para download manual.

## Fontes Oficiais Sugeridas

Para expandir o corpus, considere pesquisar e descarregar documentos nas seguintes plataformas oficiais e fiáveis:

* **Diário da República** – <https://diariodarepublica.pt/> (avisos e anúncios em PDF).
* **Portal Base (Contratos Públicos)** – <https://www.base.gov.pt/> (informação detalhada sobre contratos e anúncios de procedimento).
* **Dados.gov.pt** – <https://dados.gov.pt/> (catálogo de datasets públicos que podem incluir contratos e avisos).
* **Portais de ministérios e autarquias** (ex.: municípios, Secretaria‑Geral do Ambiente, etc.) que disponibilizam avisos e peças documentais.

## Estrutura de Pastas

```
public_docs_rag/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── raw_docs/
│   │   ├── avis2650_2025_2.txt
│   │   ├── aviso_abertura_sgambiente.txt
│   │   ├── anuncio_31579_2025.txt
│   │   ├── anuncio_25751_2025.txt
│   │   ├── avis28964_2024_2.txt
│   │   └── avis26436_2024_2.txt
│   └── manifests/
│       └── sources_manifest.csv
├── chroma_db/
├── scripts/
│   ├── ingest.py
│   ├── fetch_sources.py
│   └── reindex.sh
├── src/
│   ├── config.py
│   ├── document_loaders.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── prompts.py
│   ├── rag_pipeline.py
│   ├── ui_helpers.py
├── tests/
│   └── test_ingest.py
└── demo_questions.md
```

## Limitações Conhecidas

* A aplicação depende da disponibilidade do serviço **Ollama** e dos modelos apropriados; certifique‑se de que os modelos estão instalados.
* Documentos apenas em formato de imagem (PDF digitalizado) não são suportados no MVP; para esses casos é necessário efectuar OCR externo.
* O corpus incluído é reduzido e serve apenas para demonstração. Para resultados mais robustos, reindexe com um conjunto maior de avisos/contratos.
* As respostas não substituem aconselhamento jurídico; confirme sempre a informação nas fontes originais.

## Aviso Legal / Uso

Esta ferramenta é um **apoio à leitura e análise documental**. As respostas produzidas pelo LLM baseiam‑se no contexto recuperado dos documentos carregados. **Não substitui análise jurídica nem aconselhamento legal profissional.** Confirme sempre a informação nas fontes oficiais.