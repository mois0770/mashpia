"""Geração de resposta final: classifica a pergunta (adam_kadmon), recupera
chunks EXPRESSA/DEFINE relevantes às Sefirot/Entidades identificadas, e gera a
resposta usando o prompt fixo do projeto.

Calibrada (checklist do prompt fixo + verificação de fidelidade de citação,
ver 00_Estado_Atual.txt seção 4.8) e otimizada para performance (2026-07-27):
reaproveita a mesma busca vetorial da classificação em vez de repeti-la do
zero na hora de montar o contexto de geração (ver
adam_kadmon.classificar_com_vizinhos).

Grafo estrutural conectado à geração (2026-07-27): as Sefirot ativadas pela
classificação são expandidas via grafo.schema.expandir_por_grafo antes de
filtrar chunks — SINTETIZA/CANALIZA/GOVERNA passam a ser travessia real no
NetworkX, não só inferência implícita do LLM a partir do texto dos chunks.

Retry + tratamento de erro (2026-07-27): as chamadas à OpenRouter passam por
openrouter_client.post_com_retry (retry com backoff em timeout/desconexão/
429/5xx) em vez de requests.post cru — ver backend/openrouter_client.py.
gerar_resposta_stream também trata desconexão NO MEIO do streaming (depois
que a resposta já começou a chegar), caso em que retry do zero não é
apropriado — yield uma nota de interrupção em vez de estourar exceção.

3 níveis de resposta (2026-07-27, ver NIVEIS abaixo): o usuário escolhe antes
de perguntar. As regras de CONTEÚDO do prompt fixo (fonte, vocabulário,
terminologia, protocolo de lacuna) valem sempre, em qualquer nível — só
extensão/estrutura variam, via instrução extra anexada ao system message.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.adam_kadmon import _dividir, classificar_com_vizinhos
from backend.openrouter_client import ErroOpenRouter, post_com_retry
from grafo.schema import CONCEITOS_ESTRUTURAIS, expandir_por_grafo

PROMPT_FIXO_PATH = Path(__file__).resolve().parent.parent / "00_Prompt_Sistema_Fixo.txt"
N_CHUNKS_CONTEXTO = 8

# A partir deste peso (escala 0-5, ver grafo.schema.CONCEITOS_ESTRUTURAIS) um
# chunk é considerado central o suficiente pra sinalizar explicitamente ao
# LLM — mesmo motivo das relações do grafo: não depender de síntese implícita
# do modelo pra reconhecer um conceito que o corpus expressa sem nomear
# (achado "Dirá BeTachtonim": 0 ocorrências literais, 25 chunks do conceito).
PESO_MINIMO_DESTAQUE = 4

NIVEL_PADRAO = 1

# Cada nível só ajusta EXTENSÃO/ESTRUTURA (via instrução anexada ao prompt
# fixo) e o teto de max_tokens (também ajuda velocidade/custo nos níveis mais
# curtos) — nunca as regras de conteúdo do prompt fixo, que continuam valendo
# integralmente em qualquer nível (fonte, vocabulário, terminologia,
# protocolo de lacuna).
NIVEIS = {
    1: {
        "nome": "Completo",
        "max_tokens": 3000,
        "instrucao": None,  # comportamento padrão já calibrado, sem instrução extra
    },
    2: {
        "nome": "Resumido",
        "max_tokens": 1200,
        "instrucao": (
            "NÍVEL DE RESPOSTA SOLICITADO PARA ESTA CONSULTA: Resumido.\n"
            "Isto sobrepõe SÓ a extensão/estrutura das instruções acima — as regras de "
            "conteúdo (fonte exclusiva nos trechos fornecidos, vocabulário, terminologia "
            "fixada, protocolo de lacuna) continuam valendo integralmente.\n"
            "Mantenha a travessia (abertura pela Fonte -> corpo pelas Sefirot ativadas, "
            "seguindo Alma->Pensamento->Mente->Sentimento->Ação -> fechamento NOMEANDO Dirá "
            "BeTachtonim explicitamente), mas compacte cada etapa a 1-2 frases, não parágrafos "
            "longos. Sem subtítulos. Ao comprimir, prefira manter frases-chave exatas do "
            "corpus (citações diretas, nomes de conceitos) em vez de parafraseá-las totalmente "
            "— a compressão deve cortar elaboração e exemplos, não a terminologia central. "
            "Alvo: um texto corrido, bem mais curto que o padrão, mas ainda reconhecível como "
            "a mesma travessia estruturada."
        ),
    },
    3: {
        "nome": "Essência prática",
        "max_tokens": 600,
        "instrucao": (
            "NÍVEL DE RESPOSTA SOLICITADO PARA ESTA CONSULTA: Essência prática.\n"
            "Isto sobrepõe SÓ a extensão/estrutura das instruções acima — as regras de "
            "conteúdo (fonte exclusiva nos trechos fornecidos, vocabulário, terminologia "
            "fixada, protocolo de lacuna) continuam valendo integralmente.\n"
            "Vá direto à resposta prática em 2-4 frases corridas: sem abrir necessariamente "
            "pela Fonte, sem percorrer cada etapa da cadeia estrutural, sem subtítulos — mas "
            "SEMPRE nomeando Dirá BeTachtonim explicitamente ao final, mesmo comprimido (é o "
            "fechamento-assinatura, não opcional em nenhum nível). Ainda assim a resposta "
            "precisa refletir fielmente o que os trechos fornecidos ensinam — comprimida ao "
            "essencial, nunca genérica ou vaga. Ao comprimir, prefira manter frases-chave "
            "exatas do corpus (citações diretas, nomes de conceitos) em vez de parafraseá-las "
            "totalmente. Se a pergunta cair em protocolo de lacuna, reconheça isso numa frase só."
        ),
    },
}


def _prompt_fixo(nivel: int) -> str:
    base = PROMPT_FIXO_PATH.read_text(encoding="utf-8")
    instrucao = NIVEIS.get(nivel, NIVEIS[NIVEL_PADRAO])["instrucao"]
    return base if instrucao is None else f"{base}\n\n{instrucao}"


def _filtrar_chunks_para_geracao(vizinhos: list[dict], alvos: set[str]) -> list[dict]:
    """Filtra os vizinhos JÁ BUSCADOS pela classificação — nenhuma consulta
    nova. Aqui queremos EXPRESSA também, não só DEFINE (diferente da etapa A
    da classificação), porque a geração precisa de exemplo aplicado, não só
    definição."""
    relevantes = [
        v for v in vizinhos
        if alvos & set(_dividir(v["meta"]["sefirot_define"]))
        or alvos & set(_dividir(v["meta"]["sefirot_expressa"]))
        or alvos & set(_dividir(v["meta"]["entidades"]))
    ]
    return relevantes[:N_CHUNKS_CONTEXTO]


def _formatar_relacoes(relacoes: dict) -> str | None:
    """Traduz a saída de expandir_por_grafo em texto pro contexto do LLM —
    fato estrutural do schema confirmado do projeto, não conhecimento geral
    do modelo, então pode entrar como informação disponível igual aos
    chunks."""
    linhas = []
    for s in relacoes["sinteses"]:
        a, b = s["par"]
        linhas.append(f"- {a} e {b} convergem estruturalmente em {s['destino']} (SINTETIZA).")
    for c in relacoes["canais"]:
        linhas.append(f"- {c['origem']} se canaliza para {c['destino']} (CANALIZA).")
    for g in relacoes["governancas"]:
        linhas.append(f"- {g['origem']} governa {g['destino']} nesta consulta (GOVERNA).")
    if not linhas:
        return None
    return "Relações estruturais do grafo ativadas nesta consulta:\n" + "\n".join(linhas)


def _conceitos_centrais_chunk(meta: dict) -> list[str]:
    """Lê os campos peso_<id> gravados por vetorizar.py e devolve uma nota
    por conceito estrutural com peso >= PESO_MINIMO_DESTAQUE — só para
    documentos já passados por sugerir_tags.py (os demais têm peso 0 em
    tudo, não geram nota nenhuma)."""
    notas = []
    for c in CONCEITOS_ESTRUTURAIS:
        peso = meta.get(f"peso_{c['id']}", 0)
        if peso >= PESO_MINIMO_DESTAQUE:
            notas.append(f"{c['nome']} (peso {peso}/5)")
    return notas


def _montar_contexto(classificacao: dict, chunks: list[dict], relacoes: dict) -> str:
    # Formatação deliberadamente SEM marcadores tipo "[1]" — isso induzia o
    # LLM a citar com colchetes numéricos no texto final, o que soava como
    # nota de rodapé acadêmica em vez de fala de quem ensina (feedback do
    # usuário, calibração 2026-07-24). A rastreabilidade continua existindo
    # via `chunks_usados` no retorno de gerar_resposta — só não aparece mais
    # dentro do texto da resposta.
    partes = [
        f"Sefirot ativadas por esta consulta: {', '.join(classificacao['sefirot']) or '(nenhuma)'}",
        f"Entidades ativadas: {', '.join(classificacao['entidades']) or '(nenhuma)'}",
    ]
    relacoes_texto = _formatar_relacoes(relacoes)
    if relacoes_texto:
        partes.append(relacoes_texto)
    partes += [
        "",
        "Trechos de fonte disponíveis para fundamentar a resposta (não os cite com números "
        "no texto — apenas use o conteúdo deles com naturalidade):",
    ]
    for c in chunks:
        conceitos = _conceitos_centrais_chunk(c["meta"])
        nota_conceitos = f" [expressa centralmente: {', '.join(conceitos)}]" if conceitos else ""
        partes.append(f"\n— De \"{c['meta']['documento']}\"{nota_conceitos}:\n{c['texto']}")
    return "\n".join(partes)


def _preparar_geracao(pergunta: str, nivel: int) -> tuple[dict, list[dict], dict, list[dict]]:
    """Classifica e recupera os chunks — parte compartilhada entre a geração
    normal e a de streaming. Retorna (classificacao, chunks_usados,
    relacoes_estruturais, mensagens_para_o_llm)."""
    classificacao, vizinhos = classificar_com_vizinhos(pergunta)
    relacoes = expandir_por_grafo(classificacao["sefirot"])

    if classificacao["protocolo_lacuna"]:
        chunks = []
    else:
        alvos = set(classificacao["sefirot"]) | set(classificacao["entidades"])
        alvos |= set(relacoes["sefirot_expandidas"])
        chunks = _filtrar_chunks_para_geracao(vizinhos, alvos)

    contexto = _montar_contexto(classificacao, chunks, relacoes)
    mensagens = [
        {"role": "system", "content": _prompt_fixo(nivel)},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\n{contexto}"},
    ]
    chunks_usados = [{"documento": c["meta"]["documento"], "texto": c["texto"]} for c in chunks]
    return classificacao, chunks_usados, relacoes, mensagens


def gerar_resposta(pergunta: str, nivel: int = NIVEL_PADRAO) -> dict:
    classificacao, chunks_usados, relacoes, mensagens = _preparar_geracao(pergunta, nivel)
    max_tokens = NIVEIS.get(nivel, NIVEIS[NIVEL_PADRAO])["max_tokens"]

    resp = post_com_retry(
        "/chat/completions",
        {"model": LLM_MODEL, "messages": mensagens, "max_tokens": max_tokens, "temperature": 0.4},
        timeout=90,
    )
    resposta_texto = resp.json()["choices"][0]["message"]["content"].strip()

    return {
        "pergunta": pergunta,
        "resposta": resposta_texto,
        "classificacao": classificacao,
        "chunks_usados": chunks_usados,
        "relacoes_estruturais": relacoes,
    }


def gerar_resposta_stream(pergunta: str, nivel: int = NIVEL_PADRAO):
    """Como gerar_resposta, mas devolve (classificacao, chunks_usados,
    relacoes_estruturais, gerador_de_texto) em vez do texto pronto — o
    gerador produz pedaços de texto conforme chegam do modelo, para a
    interface poder exibir a resposta sendo escrita progressivamente em vez
    de ficar em silêncio pelos ~20s+ que a geração completa costuma levar
    (feedback do usuário sobre demora, 2026-07-27)."""
    classificacao, chunks_usados, relacoes, mensagens = _preparar_geracao(pergunta, nivel)
    max_tokens = NIVEIS.get(nivel, NIVEIS[NIVEL_PADRAO])["max_tokens"]

    # A conexão inicial (até o primeiro byte) passa pelo retry normal de
    # post_com_retry. Depois que o streaming já começou, uma queda no meio
    # não é mais caso de retry (recomeçar do zero reenviaria todo o contexto
    # e produziria uma resposta diferente da que o usuário já viu em parte)
    # — em vez de estourar exceção dentro do gerador (que quebraria
    # st.write_stream sem aviso), avisa com uma nota curta.
    resp = post_com_retry(
        "/chat/completions",
        {"model": LLM_MODEL, "messages": mensagens, "max_tokens": max_tokens,
         "temperature": 0.4, "stream": True},
        timeout=90,
        stream=True,
    )

    def gerador():
        try:
            with resp:
                for linha in resp.iter_lines():
                    if not linha:
                        continue
                    linha = linha.decode("utf-8")
                    if not linha.startswith("data: "):
                        continue
                    dado = linha[len("data: "):]
                    if dado.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(dado)
                    except json.JSONDecodeError:
                        continue
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    pedaco = delta.get("content")
                    if pedaco:
                        yield pedaco
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
            yield ("\n\n_[a conexão com o modelo caiu no meio da resposta — "
                   "peço desculpas pela interrupção; tente enviar a pergunta de novo]_")

    return classificacao, chunks_usados, relacoes, gerador()


if __name__ == "__main__":
    pergunta = sys.argv[1] if len(sys.argv) > 1 else "Como equilibrar dar generosamente e saber colocar limites?"
    nivel = int(sys.argv[2]) if len(sys.argv) > 2 else NIVEL_PADRAO
    r = gerar_resposta(pergunta, nivel=nivel)
    print(f"PERGUNTA: {r['pergunta']}")
    print(f"NIVEL: {nivel} ({NIVEIS[nivel]['nome']})\n")
    print(f"SEFIROT: {r['classificacao']['sefirot']}")
    print(f"RELACOES ESTRUTURAIS: {r['relacoes_estruturais']}")
    print(f"CHUNKS USADOS: {[c['documento'] for c in r['chunks_usados']]}\n")
    print("RESPOSTA:")
    print(r["resposta"])
