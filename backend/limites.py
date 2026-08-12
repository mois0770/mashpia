"""Proteção de custo para uso público do app — teto de gasto diário na chave
da OpenRouter. Antes desta camada, qualquer pessoa com o link do app
consumia a chave pessoal do usuário sem limite nenhum (cada pergunta faz 3+
chamadas: tradução, classificação, geração).

A OpenRouter devolve o custo real em dólar de cada chamada (`usage.cost` na
resposta) — o teto é rastreado com esse valor real, não estimado por token.

Valores padrão conservadores, pensados para ajustar facilmente depois:
TETO_CUSTO_DIARIO_USD e MAX_PERGUNTAS_POR_SESSAO são as duas constantes a
mudar se o teto se mostrar folgado ou apertado demais na prática.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import sentry_sdk

from config import DATA_DIR, get_supabase_config

TETO_CUSTO_DIARIO_USD = 5.0
MAX_PERGUNTAS_POR_SESSAO = 10

_ARQUIVO_USO = DATA_DIR / "uso_diario.json"
_TABELA_SUPABASE = "uso_diario"


class TetoDeCustoAtingido(Exception):
    """Levantada quando o gasto acumulado do dia já bateu o teto —
    interrompe ANTES de gastar mais, não depois."""


def _supabase_headers(chave: str) -> dict:
    return {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}


def _carregar_estado() -> dict:
    """Lê do Supabase quando configurado (achado real 2026-08-10: o disco
    local NÃO sobrevive a reboot/redeploy no Streamlit Community Cloud —
    testado e confirmado). Sem Supabase configurado (dev local, scripts como
    medir_tokens.py), cai no arquivo local — mesmo comportamento de antes,
    pra não exigir conta no Supabase só pra rodar testes."""
    hoje = date.today().isoformat()
    config_supabase = get_supabase_config()

    if config_supabase:
        url, chave = config_supabase
        resp = requests.get(
            f"{url}/rest/v1/{_TABELA_SUPABASE}",
            headers=_supabase_headers(chave),
            params={"data": f"eq.{hoje}", "select": "custo_acumulado_usd"},
            timeout=10,
        )
        resp.raise_for_status()
        linhas = resp.json()
        if linhas:
            return {"data": hoje, "custo_acumulado_usd": float(linhas[0]["custo_acumulado_usd"])}
        return {"data": hoje, "custo_acumulado_usd": 0.0}

    if _ARQUIVO_USO.exists():
        estado = json.loads(_ARQUIVO_USO.read_text(encoding="utf-8"))
        if estado.get("data") == hoje:
            return estado
    return {"data": hoje, "custo_acumulado_usd": 0.0}


def _salvar_estado(estado: dict) -> None:
    config_supabase = get_supabase_config()

    if config_supabase:
        url, chave = config_supabase
        headers = _supabase_headers(chave)
        headers["Prefer"] = "resolution=merge-duplicates"
        resp = requests.post(
            f"{url}/rest/v1/{_TABELA_SUPABASE}",
            headers=headers,
            params={"on_conflict": "data"},
            json={
                "data": estado["data"],
                "custo_acumulado_usd": estado["custo_acumulado_usd"],
                "ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ARQUIVO_USO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def custo_hoje() -> float:
    return _carregar_estado()["custo_acumulado_usd"]


def teto_atingido() -> bool:
    return custo_hoje() >= TETO_CUSTO_DIARIO_USD


def verificar_teto() -> None:
    """Chamar ANTES de iniciar uma pergunta nova (antes de qualquer chamada
    à OpenRouter) — levanta TetoDeCustoAtingido se já bateu o teto, evitando
    gastar mais enquanto o pedido já era pra ser recusado.

    Diferente de registrar_custo() (best-effort, nunca derruba uma resposta
    já paga): aqui, se não der pra consultar o Supabase (ex.: chave rotacionada,
    instabilidade), a checagem falha FECHADA — bloqueia a pergunta em vez de
    deixar passar sem nenhum controle de custo, que é exatamente o risco que
    este módulo existe pra evitar (ver docstring do arquivo)."""
    try:
        atingido = teto_atingido()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
        raise TetoDeCustoAtingido(
            "Não foi possível verificar o limite de uso agora (instabilidade temporária). "
            "Tente novamente em alguns instantes."
        ) from e

    if atingido:
        raise TetoDeCustoAtingido(
            f"O limite diário de uso deste app (US$ {TETO_CUSTO_DIARIO_USD:.2f}) já foi "
            "atingido. Volte amanhã ou entre em contato com o responsável pelo projeto."
        )


def registrar_custo(usd: float) -> None:
    """Soma ao acumulado do dia — chamado depois de CADA chamada bem-sucedida
    à OpenRouter (post_com_retry para chamadas não-streaming; o gerador de
    streaming registra separadamente, pois o custo só vem no evento final
    do SSE, não na resposta inicial)."""
    if not usd:
        return
    estado = _carregar_estado()
    estado["custo_acumulado_usd"] = estado.get("custo_acumulado_usd", 0.0) + usd
    estado["ultima_atualizacao"] = datetime.now(timezone.utc).isoformat()
    _salvar_estado(estado)


# --- Teto de perguntas por usuário/dia (2026-08-10) -------------------------
# Diferente de MAX_PERGUNTAS_POR_SESSAO (session_state do Streamlit, reseta a
# cada recarregar de página — não serve como teto comercial de verdade) —
# este teto é por IDENTIDADE do usuário (uma senha por assinante, ver
# interface/app.py::_verificar_senha) e persiste entre sessões, resetando por
# data corrida, não por sessão. Portado do Mentor, mas já nascendo com o
# mesmo backend Supabase de custo_hoje()/registrar_custo() — a versão
# original do Mentor usava só arquivo local, que teria o mesmo problema de
# persistência já corrigido aqui (reboot no Streamlit Cloud reseta o disco).

MAX_PERGUNTAS_POR_USUARIO_DIA = 5

_ARQUIVO_PERGUNTAS = DATA_DIR / "perguntas_por_usuario.json"
_TABELA_SUPABASE_PERGUNTAS = "perguntas_por_usuario"


class LimiteDiarioAtingido(Exception):
    """Levantada quando um usuário já usou suas MAX_PERGUNTAS_POR_USUARIO_DIA
    perguntas de hoje (ou quando não foi possível verificar — mesma política
    de falha fechada de verificar_teto())."""


def _carregar_perguntas_arquivo() -> dict:
    if _ARQUIVO_PERGUNTAS.exists():
        try:
            return json.loads(_ARQUIVO_PERGUNTAS.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _salvar_perguntas_arquivo(dados: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ARQUIVO_PERGUNTAS.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def perguntas_hoje(usuario_id: str) -> int:
    hoje = date.today().isoformat()
    config_supabase = get_supabase_config()

    if config_supabase:
        url, chave = config_supabase
        resp = requests.get(
            f"{url}/rest/v1/{_TABELA_SUPABASE_PERGUNTAS}",
            headers=_supabase_headers(chave),
            params={"usuario_id": f"eq.{usuario_id}", "data": f"eq.{hoje}", "select": "perguntas"},
            timeout=10,
        )
        resp.raise_for_status()
        linhas = resp.json()
        return int(linhas[0]["perguntas"]) if linhas else 0

    registro = _carregar_perguntas_arquivo().get(usuario_id, {})
    if registro.get("data") != hoje:
        return 0
    try:
        return int(registro.get("perguntas", 0))
    except (TypeError, ValueError):
        return 0


def limite_diario_atingido(usuario_id: str) -> bool:
    return perguntas_hoje(usuario_id) >= MAX_PERGUNTAS_POR_USUARIO_DIA


def verificar_limite_diario(usuario_id: str) -> None:
    """Chamar ANTES de processar uma pergunta nova — mesma política de falha
    fechada de verificar_teto(): se não der pra consultar o Supabase, bloqueia
    em vez de deixar passar sem controle nenhum."""
    try:
        atingido = limite_diario_atingido(usuario_id)
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
        raise LimiteDiarioAtingido(
            "Não foi possível verificar seu limite de perguntas agora (instabilidade "
            "temporária). Tente novamente em alguns instantes."
        ) from e

    if atingido:
        raise LimiteDiarioAtingido(
            f"Você atingiu o limite de {MAX_PERGUNTAS_POR_USUARIO_DIA} perguntas de hoje. "
            "Volte amanhã para continuar."
        )


def registrar_pergunta(usuario_id: str) -> None:
    """Chamar depois de uma pergunta processada com sucesso — soma 1 ao
    contador de hoje do usuário. Best-effort (mesma política de
    registrar_custo(): não pode derrubar uma resposta que já chegou certinha
    por causa de uma falha aqui)."""
    hoje = date.today().isoformat()
    config_supabase = get_supabase_config()

    if config_supabase:
        url, chave = config_supabase
        try:
            atual = perguntas_hoje(usuario_id)
            headers = _supabase_headers(chave)
            headers["Prefer"] = "resolution=merge-duplicates"
            resp = requests.post(
                f"{url}/rest/v1/{_TABELA_SUPABASE_PERGUNTAS}",
                headers=headers,
                params={"on_conflict": "usuario_id,data"},
                json={
                    "usuario_id": usuario_id,
                    "data": hoje,
                    "perguntas": atual + 1,
                    "ultima_pergunta": datetime.now(timezone.utc).isoformat(),
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
            print(f"[aviso] falha ao registrar pergunta (resposta segue normalmente): {e}")
        return

    dados = _carregar_perguntas_arquivo()
    registro = dados.get(usuario_id, {})
    if registro.get("data") != hoje:
        registro = {"data": hoje, "perguntas": 0}
    registro["perguntas"] = int(registro.get("perguntas", 0)) + 1
    registro["ultima_pergunta"] = datetime.now(timezone.utc).isoformat()
    dados[usuario_id] = registro
    _salvar_perguntas_arquivo(dados)
