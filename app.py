"""Aplicação Streamlit para análise de avisos e contratos públicos.

Permite ao utilizador colocar perguntas em linguagem natural sobre um corpus
previamente indexado, obtendo respostas fundamentadas com citações e
extração estruturada de informação.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

# Garantir que a raiz do projecto está no sys.path para importarmos `src` como pacote.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.embeddings import get_embeddings
from src.vector_store import load_vector_store
from src.rag_pipeline import RAGPipeline
from src.ui_helpers import display_answer, display_citations, display_structured_info


def load_pipeline(top_k: int) -> RAGPipeline | None:
    """Carrega o vector store e devolve uma instância do pipeline.

    Retorna `None` se o índice não existir.
    """
    if not config.CHROMA_DIR.exists() or not any(config.CHROMA_DIR.iterdir()):
        return None
    embedding_name, _ = config.get_model_names()
    embeddings = get_embeddings(embedding_name)
    vs = load_vector_store(embeddings)
    return RAGPipeline(vectorstore=vs, top_k=top_k)


def main() -> None:
    st.set_page_config(page_title="Analisador de Avisos Públicos", layout="wide")
    st.title("Analisador de Contratos e Avisos Públicos")
    st.write(
        "Esta aplicação permite colocar perguntas em linguagem natural sobre um conjunto de avisos/contratos públicos e obter respostas baseadas nos documentos, com citações e extração estruturada de informação."
    )
    st.write(
        "**Nota:** A ferramenta é um apoio à leitura. Confirmar sempre a informação na fonte oficial. Não substitui aconselhamento jurídico."
    )

    st.sidebar.header("Configuração")
    top_k = st.sidebar.slider(
        "Número de trechos a recuperar (top_k)", min_value=2, max_value=10, value=config.TOP_K
    )
    if st.sidebar.button("Reindexar documentos"):
        st.sidebar.write("A reindexar…")
        try:
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "ingest.py")],
                cwd=str(PROJECT_ROOT),
                check=True,
            )
            st.sidebar.success("Reindexação concluída.")
        except subprocess.CalledProcessError as exc:
            st.sidebar.error(f"Falha na reindexação (código {exc.returncode}).")
        except Exception as e:
            st.sidebar.error(f"Falha na reindexação: {e}")

    try:
        pipeline = load_pipeline(top_k)
    except Exception as e:
        st.error(f"Erro ao carregar o índice/modelo de embeddings: {e}")
        st.stop()

    if pipeline is None:
        st.warning(
            "O índice vetorial ainda não foi criado ou está vazio. Execute `python scripts/ingest.py` (na raiz do projecto) ou use o botão 'Reindexar documentos'."
        )
        st.stop()

    pergunta = st.text_input(
        "Coloque a sua pergunta sobre os documentos carregados:",
        placeholder="Ex.: Qual é o objeto do contrato?",
    )
    if st.button("Perguntar") and pergunta.strip():
        with st.spinner("A gerar resposta..."):
            resposta, documentos = pipeline.answer_question(pergunta)
            display_answer(resposta)
            display_citations(documentos)
            estrutura = pipeline.extract_structured(documentos)
            display_structured_info(estrutura)


if __name__ == "__main__":
    main()
