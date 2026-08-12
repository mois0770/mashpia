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


def get_supabase_config() -> tuple[str, str] | None:
    """Mesma cadeia de fallback de get_openrouter_key(). Retorna (url, chave
    service_role) ou None se não configurado — quem chama decide o que fazer
    (backend/limites.py cai de volta pro arquivo local nesse caso, pra não
    quebrar uso local/scripts sem exigir conta no Supabase)."""
    url = os.environ.get("SUPABASE_URL")
    chave = os.environ.get("SUPABASE_SERVICE_KEY")
    if url and chave:
        return url, chave

    try:
        import streamlit as st
        if "SUPABASE_URL" in st.secrets and "SUPABASE_SERVICE_KEY" in st.secrets:
            return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"]
    except Exception:
        pass

    _arquivo = BASE_DIR / "Supabase_Key.txt"
    if _arquivo.exists():
        linhas = _arquivo.read_text().strip().splitlines()
        if len(linhas) >= 2:
            return linhas[0].strip(), linhas[1].strip()

    return None


def get_qdrant_config() -> tuple[str, str] | None:
    """Mesmo padrão de get_supabase_config(). Retorna (url, chave) ou None se
    não configurado — pipeline/vetorizar.py cai de volta pro ChromaDB local
    nesse caso (mesmo motivo: não travar uso local/scripts sem conta no
    Qdrant)."""
    url = os.environ.get("QDRANT_URL")
    chave = os.environ.get("QDRANT_API_KEY")
    if url and chave:
        return url, chave

    try:
        import streamlit as st
        if "QDRANT_URL" in st.secrets and "QDRANT_API_KEY" in st.secrets:
            return st.secrets["QDRANT_URL"], st.secrets["QDRANT_API_KEY"]
    except Exception:
        pass

    _arquivo = BASE_DIR / "Qdrant_Key.txt"
    if _arquivo.exists():
        linhas = _arquivo.read_text().strip().splitlines()
        if len(linhas) >= 2:
            return linhas[0].strip(), linhas[1].strip()

    return None


def get_sentry_dsn() -> str | None:
    """Mesmo padrão de get_supabase_config()/get_qdrant_config(), mas devolve
    um valor só (a DSN do Sentry não é secreta como as outras chaves — é
    write-only por natureza, mas mantém o mesmo formato de arquivo local por
    consistência). None se não configurado — quem chama decide não inicializar
    o Sentry nesse caso, sem quebrar uso local sem conta lá."""
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        return dsn

    try:
        import streamlit as st
        if "SENTRY_DSN" in st.secrets:
            return st.secrets["SENTRY_DSN"]
    except Exception:
        pass

    _arquivo = BASE_DIR / "Sentry_Dsn.txt"
    if _arquivo.exists():
        return _arquivo.read_text().strip()

    return None


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modelo de embedding multilíngue — ver seção 11.3 do documento de arquitetura.
EMBEDDING_MODEL = "openai/text-embedding-3-large"

# Modelo de classificação/geração — "boa qualidade", a refinar conforme uso real.
LLM_MODEL = "anthropic/claude-sonnet-5"
