"""Chamada HTTP à OpenRouter com retry — usada por toda chamada de LLM/embedding
do projeto (tradução, classificação, geração, vetorização), para que uma falha
transiente de rede ou uma sobrecarga momentânea da API (timeout, desconexão,
429, 5xx) não estoure um traceback cru na interface. Depois de esgotar as
tentativas, levanta `ErroOpenRouter` — uma mensagem amigável, para a camada de
interface decidir como mostrar ao usuário."""

import time

import requests

from config import OPENROUTER_BASE_URL, get_openrouter_key

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

        return resp

    raise ErroOpenRouter(f"Falha na chamada à OpenRouter: {ultimo_erro}")
