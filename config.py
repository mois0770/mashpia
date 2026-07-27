"""Configuração compartilhada do projeto — chave da OpenRouter, caminhos de dados."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"

_KEY_FILE = BASE_DIR / "Openrouter_Ket.txt"


def get_openrouter_key() -> str:
    if "OPENROUTER_API_KEY" in os.environ:
        return os.environ["OPENROUTER_API_KEY"]

    # No Streamlit Community Cloud não existe Openrouter_Ket.txt (fora do
    # repositório, coberto pelo .gitignore) — a chave é configurada no painel
    # "Secrets" da plataforma e chega aqui via st.secrets. Import feito dentro
    # da função para não obrigar scripts que não usam Streamlit (CLI,
    # backend/main.py) a ter o pacote carregado sem necessidade.
    try:
        import streamlit as st
        if "OPENROUTER_API_KEY" in st.secrets:
            return st.secrets["OPENROUTER_API_KEY"]
    except Exception:
        pass

    if _KEY_FILE.exists():
        return _KEY_FILE.read_text().strip()
    raise RuntimeError(
        f"Chave da OpenRouter não encontrada (nem em OPENROUTER_API_KEY, nem em st.secrets, "
        f"nem em {_KEY_FILE})."
    )


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modelo de embedding multilíngue — ver seção 11.3 do documento de arquitetura.
EMBEDDING_MODEL = "openai/text-embedding-3-large"

# Modelo de classificação/geração — "boa qualidade", a refinar conforme uso real.
LLM_MODEL = "anthropic/claude-sonnet-5"
