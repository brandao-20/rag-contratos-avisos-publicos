"""Configurações centralizadas para a aplicação.

Este módulo define constantes e funções utilitárias para configurar os modelos,
o tamanho dos blocos de texto, caminhos para dados e parâmetros de recuperação.
As configurações podem ser ajustadas conforme necessário para adaptar o
comportamento da aplicação.
"""

from pathlib import Path
from typing import Optional


# Pasta onde os documentos originais (.pdf/.txt/.md) estão armazenados.
RAW_DOCS_DIR: Path = Path("data/raw_docs")

# Pasta onde a base de dados vetorial Chroma será persistida.
CHROMA_DIR: Path = Path("chroma_db")

# Tamanho dos blocos de texto (em caracteres) usados para os embeddings.
CHUNK_SIZE: int = 800

# Número de caracteres de sobreposição entre blocos consecutivos.
CHUNK_OVERLAP: int = 100

# Nome do modelo de embeddings a usar com Ollama.
# Por omissão usa-se 'mistral', mas pode ser alterado para outro modelo
# disponível localmente. Este nome é passado para `OllamaEmbeddings`.
EMBEDDING_MODEL_NAME: str = "mistral"

# Nome do modelo de LLM para geração de respostas. Por omissão 'mistral'.
LLM_MODEL_NAME: str = "mistral"

# Número máximo de documentos a recuperar por pergunta.
TOP_K: int = 4


def ensure_directories() -> None:
    """Garante que as pastas essenciais existem no sistema de ficheiros.

    Esta função deve ser chamada antes de executar operações que dependam
    da existência das pastas (por exemplo, criação do índice Chroma).
    """
    RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def get_model_names() -> tuple[str, str]:
    """Obtém os nomes dos modelos de embeddings e LLM.

    Retorna uma tupla `(embedding_model_name, llm_model_name)`. Se variáveis de
    ambiente específicas estiverem definidas (por exemplo, `EMBEDDING_MODEL` ou
    `LLM_MODEL`), estas substituem os valores por defeito. Isto permite ao
    utilizador ajustar rapidamente o modelo sem alterar o código.
    """
    import os
    embedding = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL_NAME)
    llm = os.getenv("LLM_MODEL", LLM_MODEL_NAME)
    return embedding, llm
