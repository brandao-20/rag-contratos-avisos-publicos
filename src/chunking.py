"""Chunking com preservação de metadados e IDs estáveis."""

from __future__ import annotations

from typing import Iterable

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter



def chunk_documents(docs: Iterable[Document], *, chunk_size: int, chunk_overlap: int) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
    )
    out: list[Document] = []
    for doc in docs:
        splits = splitter.split_text(doc.page_content)
        for idx, chunk in enumerate(splits):
            meta = dict(doc.metadata)
            source_id = meta.get("source_id") or meta.get("source_file") or "doc"
            locator = meta.get("locator") or f"p.{meta.get('page') or 0}"
            meta.update(
                {
                    "chunk_id": idx,
                    "chunk_uid": f"{source_id}:{locator}:c{idx}",
                }
            )
            out.append(Document(page_content=chunk, metadata=meta))
    return out
