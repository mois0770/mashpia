"""Cadastro self-service de assinantes — complementa o gate manual
(st.secrets["usuarios"], onde EU edito os Secrets pra cada pessoa nova).
Contas criadas aqui ficam no Supabase (tabela usuarios_cadastro), com senha
com HASH (bcrypt) — diferente do st.secrets, que guarda senha em texto puro
(aceitável só pra um punhado de contas editadas manualmente por mim, nunca
pra cadastro aberto ao público).

Fase de teste (2026-08-11): toda conta nova criada aqui já entra ATIVA
(`ativo=true`), sem cobrança associada ainda — é só pra validar o mecanismo
de cadastro/login em si. Quando a integração com Stripe existir, `ativo`
passa a ser controlado pelo webhook (só True depois do pagamento
confirmado), não mais True por padrão na criação.
"""

import bcrypt
import requests

from config import get_supabase_config

_TABELA = "usuarios_cadastro"


class UsuarioJaExiste(Exception):
    """Levantada ao tentar criar uma conta com usuario_id já em uso."""


class CadastroIndisponivel(Exception):
    """Levantada quando o Supabase não está configurado. Sem fallback local
    (diferente de backend/limites.py) — não faz sentido testar cadastro
    self-service sem um lugar de verdade pra guardar a conta."""


def _supabase_headers(chave: str) -> dict:
    return {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}


def _exigir_supabase() -> tuple[str, str]:
    config = get_supabase_config()
    if not config:
        raise CadastroIndisponivel(
            "Cadastro self-service exige Supabase configurado (SUPABASE_URL/SUPABASE_SERVICE_KEY)."
        )
    return config


def usuario_existe(usuario_id: str) -> bool:
    url, chave = _exigir_supabase()
    resp = requests.get(
        f"{url}/rest/v1/{_TABELA}",
        headers=_supabase_headers(chave),
        params={"usuario_id": f"eq.{usuario_id}", "select": "usuario_id"},
        timeout=10,
    )
    resp.raise_for_status()
    return bool(resp.json())


def criar_conta(usuario_id: str, senha: str, email: str = "") -> None:
    if usuario_existe(usuario_id):
        raise UsuarioJaExiste(f"Já existe uma conta com o usuário '{usuario_id}'.")

    url, chave = _exigir_supabase()
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    resp = requests.post(
        f"{url}/rest/v1/{_TABELA}",
        headers=_supabase_headers(chave),
        json={"usuario_id": usuario_id, "senha_hash": senha_hash, "email": email, "ativo": True},
        timeout=10,
    )
    resp.raise_for_status()


def verificar_login(usuario_id: str, senha: str) -> bool:
    """True se usuario_id existe, está ativo, e a senha bate com o hash
    salvo. Qualquer problema de conexão/configuração conta como login
    inválido — falha fechada, mesma política do resto do app (não dá pra
    liberar acesso quando não dá pra confirmar a senha de verdade)."""
    try:
        url, chave = _exigir_supabase()
        resp = requests.get(
            f"{url}/rest/v1/{_TABELA}",
            headers=_supabase_headers(chave),
            params={"usuario_id": f"eq.{usuario_id}", "select": "senha_hash,ativo"},
            timeout=10,
        )
        resp.raise_for_status()
        linhas = resp.json()
    except (requests.RequestException, CadastroIndisponivel):
        return False

    if not linhas or not linhas[0]["ativo"]:
        return False
    return bcrypt.checkpw(senha.encode("utf-8"), linhas[0]["senha_hash"].encode("utf-8"))
