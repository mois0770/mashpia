"""Chamada HTTP à OpenRouter com retry — usada por toda chamada de LLM/embedding
do projeto (tradução, classificação, geração, vetorização), para que uma falha
transiente de rede ou uma sobrecarga momentânea da API (timeout, desconexão,
429, 5xx) não estoure um traceback cru na interface. Depois de esgotar as
tentativas, levanta `ErroOpenRouter` — uma mensagem amigável, para a camada de
interface decidir como mostrar ao usuário.

Registra o custo real (`usage.cost`, devolvido pela própria OpenRouter) de
toda chamada NÃO-streaming no teto diário (backend/limites.py) — chamadas
streaming não têm o custo disponível na resposta inicial, então quem chama
com stream=True precisa registrar por conta própria a partir do evento
final do SSE (ver gerar_resposta.gerar_resposta_stream)."""

import time

import requests
import sentry_sdk

from config import OPENROUTER_BASE_URL, get_openrouter_key
from backend.limites import registrar_custo

TENTATIVAS_PADRAO = 3


class ErroOpenRouter(Exception):
    """Erro amigável de comunicação com a OpenRouter, já esgotadas as tentativas."""


def post_com_retry(caminho: str, corpo: dict, timeout: int,
                    tentativas: int = TENTATIVAS_PADRAO, stream: bool = False) -> requests.Response:
    ultimo_erro = "motivo desconhecido"
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}{caminho}",
                headers={"Authorization": f"Bearer {get_openrouter_key()}"},
                json=corpo,
                timeout=timeout,
                stream=stream,
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_erro = str(e)
            if tentativa < tentativas:
                time.sleep(2 ** (tentativa - 1))
                continue
            raise ErroOpenRouter(
                f"Não foi possível conectar à OpenRouter após {tentativas} tentativas "
                f"(rede instável ou API fora do ar)."
            ) from e

        # 429 (rate limit) e 5xx (erro do lado da OpenRouter) são transientes —
        # vale tentar de novo. Qualquer outro erro HTTP (401, 400 etc.) é
        # definitivo — retry não resolveria, então falha na primeira.
        if resp.status_code == 429 or resp.status_code >= 500:
            ultimo_erro = f"HTTP {resp.status_code}"
            if tentativa < tentativas:
                time.sleep(2 ** (tentativa - 1))
                continue
            raise ErroOpenRouter(
                f"A OpenRouter respondeu com erro ({resp.status_code}) após {tentativas} tentativas. "
                "Tente novamente em alguns instantes."
            )

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise ErroOpenRouter(
                f"Erro da OpenRouter ({resp.status_code}): {resp.text[:200]}"
            ) from e

        if not stream:
            try:
                custo = resp.json().get("usage", {}).get("cost", 0)
            except (ValueError, KeyError):
                custo = 0
            if custo:
                try:
                    registrar_custo(custo)
                except requests.RequestException as e:
                    # Registro de custo é best-effort — uma falha aqui (ex.: chave do
                    # Supabase inválida/rotacionada) não pode derrubar uma resposta que
                    # já chegou certinha da OpenRouter. Ainda assim reporta pro Sentry —
                    # é exatamente o tipo de falha silenciosa que passaria despercebida
                    # sem monitoramento (achado real: já aconteceu durante rotação de
                    # chave do Supabase, 2026-08-10).
                    sentry_sdk.capture_exception(e)
                    print(f"[aviso] falha ao registrar custo (resposta segue normalmente): {e}")

        return resp

    raise ErroOpenRouter(f"Falha na chamada à OpenRouter: {ultimo_erro}")
