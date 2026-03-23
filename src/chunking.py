"""Divisão de documentos em blocos menores."""

from __future__ import annotations

from typing import Iterable, List

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter


def chunk_documents(docs: Iterable[Document], *, chunk_size: int, chunk_overlap: int) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunked_docs: List[Document] = []
    for doc in docs:
        splits = splitter.split_text(doc.page_content)
        for i, chunk in enumerate(splits):
            metadata = dict(doc.metadata)
            metadata.update(
                {
                    "chunk_id": i,
                    "chunk_uid": f"{metadata.get('source_file','')}:p{metadata.get('page') or 0}:c{i}",
                }
            )
            chunked_docs.append(Document(page_content=chunk, metadata=metadata))
    return chunked_docs
