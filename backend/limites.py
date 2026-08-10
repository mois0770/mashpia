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
    gastar mais enquanto o pedido já era pra ser recusado."""
    if teto_atingido():
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
