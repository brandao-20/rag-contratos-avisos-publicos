"""Funções auxiliares para a interface Streamlit."""

from __future__ import annotations

from typing import List, Dict, Any

import streamlit as st
from langchain.schema import Document


def display_answer(answer: str) -> None:
    st.subheader("Resposta")
    st.write(answer)


def display_citations(documents: List[Document]) -> None:
    if not documents:
        st.info("Não foram recuperados documentos relevantes.")
        return

    st.subheader("Fontes / Citações")
    st.caption(f"Trechos recuperados: {len(documents)}")

    for idx, doc in enumerate(documents, start=1):
        meta = doc.metadata
        source = meta.get("source_file", "")
        page = meta.get("page")
        page_str = f"página {page}" if page else "texto"
        source_url = meta.get("source_url")
        header = f"**[{idx}] {source}** ({page_str})"
        st.markdown(header)
        if source_url:
            st.caption(f"Fonte oficial: {source_url}")
        excerpt = doc.page_content
        if len(excerpt) > 700:
            excerpt = excerpt[:700] + " …"
        st.write(excerpt)


def display_structured_info(data: Dict[str, Any]) -> None:
    st.subheader("Informação Estruturada (extraída)")
    if not data:
        st.info("Não foi possível extrair informação estruturada do contexto.")
        return
    st.json(data, expanded=False)
