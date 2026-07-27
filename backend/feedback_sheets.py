"""Envia feedback para um Google Form (que grava numa planilha do Google
ligada a ele) via POST direto ao endpoint público do formulário — o mesmo
mecanismo que o próprio formulário usa quando alguém o preenche pelo
navegador. Não precisa de credencial/OAuth/service account: é o mesmo tipo de
requisição que um Google Form aceita de qualquer navegador.

Configurado e testado (2026-07-27): FORM_ID e ENTRY_* apontam para o Form
real, submissão de ponta a ponta confirmada (linha aparece na planilha
ligada). O campo "Avaliacao" é múltipla escolha obrigatória no Form com
literais fixos (`_MAPA_AVALIACAO`) — se o texto vindo da interface não bater
com o mapa, `enviar_feedback_sheets` desiste do envio (retorna False) em vez
de mandar um valor que o Google rejeitaria.

feedback.py continua sendo a gravação garantida em paralelo (dupla gravação:
local + planilha) — nenhum feedback se perde mesmo se o envio ao Sheets
falhar por qualquer motivo (rede, validação, Form fora do ar).
"""

import requests

FORM_ID = "1FAIpQLSdnrjTNhmWywLD8pli2Y0glJiHtN2DFGIcg1M_zfh90yY1zGQ"

ENTRY_AVALIACAO = "entry.1384031781"
ENTRY_SUGESTAO = "entry.1987183465"
ENTRY_PERGUNTA = "entry.102054547"
ENTRY_RESPOSTA = "entry.817337785"

# O campo "Avaliacao" no Form é múltipla escolha obrigatória com estes 4
# literais exatos — diferem do texto exibido na interface (ex.: "Muito boa"
# vs. "Muito_Boa"). Qualquer valor fora deste mapa faz o Google rejeitar a
# submissão inteira (400), por isso normalizamos aqui antes de enviar.
_MAPA_AVALIACAO = {
    "Muito boa": "Muito_Boa",
    "Boa": "Boa",
    "Regular": "Regular",
    "Ruim": "Ruim",
}


def configurado() -> bool:
    return bool(FORM_ID and ENTRY_AVALIACAO and ENTRY_SUGESTAO)


def enviar_feedback_sheets(
    avaliacao: str,
    sugestao: str,
    pergunta: str | None = None,
    resposta: str | None = None,
) -> bool:
    if not configurado():
        return False

    avaliacao_form = _MAPA_AVALIACAO.get(avaliacao)
    if avaliacao_form is None:
        # Sem avaliação marcada (ou valor desconhecido) — o campo é
        # obrigatório no Form, não há literal válido para enviar. A cópia
        # local em feedback.jsonl já preserva o registro.
        return False

    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/formResponse"
    dados = {
        ENTRY_AVALIACAO: avaliacao_form,
        ENTRY_SUGESTAO: sugestao,
    }
    if ENTRY_PERGUNTA and pergunta:
        dados[ENTRY_PERGUNTA] = pergunta
    if ENTRY_RESPOSTA and resposta:
        dados[ENTRY_RESPOSTA] = resposta[:400]

    try:
        resp = requests.post(url, data=dados, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False
