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
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL, OPENROUTER_BASE_URL, get_openrouter_key
from backend.adam_kadmon import _dividir, classificar_com_vizinhos
from grafo.schema import expandir_por_grafo

PROMPT_FIXO_PATH = Path(__file__).resolve().parent.parent / "00_Prompt_Sistema_Fixo.txt"
N_CHUNKS_CONTEXTO = 8


def _prompt_fixo() -> str:
    return PROMPT_FIXO_PATH.read_text(encoding="utf-8")


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
        partes.append(f"\n— De \"{c['meta']['documento']}\":\n{c['texto']}")
    return "\n".join(partes)


def _preparar_geracao(pergunta: str) -> tuple[dict, list[dict], dict, list[dict]]:
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
        {"role": "system", "content": _prompt_fixo()},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\n{contexto}"},
    ]
    chunks_usados = [{"documento": c["meta"]["documento"], "texto": c["texto"]} for c in chunks]
    return classificacao, chunks_usados, relacoes, mensagens


def gerar_resposta(pergunta: str) -> dict:
    classificacao, chunks_usados, relacoes, mensagens = _preparar_geracao(pergunta)

    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {get_openrouter_key()}"},
        json={"model": LLM_MODEL, "messages": mensagens, "max_tokens": 3000, "temperature": 0.4},
        timeout=90,
    )
    resp.raise_for_status()
    resposta_texto = resp.json()["choices"][0]["message"]["content"].strip()

    return {
        "pergunta": pergunta,
        "resposta": resposta_texto,
        "classificacao": classificacao,
        "chunks_usados": chunks_usados,
        "relacoes_estruturais": relacoes,
    }


def gerar_resposta_stream(pergunta: str):
    """Como gerar_resposta, mas devolve (classificacao, chunks_usados,
    relacoes_estruturais, gerador_de_texto) em vez do texto pronto — o
    gerador produz pedaços de texto conforme chegam do modelo, para a
    interface poder exibir a resposta sendo escrita progressivamente em vez
    de ficar em silêncio pelos ~20s+ que a geração completa costuma levar
    (feedback do usuário sobre demora, 2026-07-27)."""
    classificacao, chunks_usados, relacoes, mensagens = _preparar_geracao(pergunta)

    def gerador():
        with requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {get_openrouter_key()}"},
            json={"model": LLM_MODEL, "messages": mensagens, "max_tokens": 3000,
                  "temperature": 0.4, "stream": True},
            timeout=90,
            stream=True,
        ) as resp:
            resp.raise_for_status()
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

    return classificacao, chunks_usados, relacoes, gerador()


if __name__ == "__main__":
    pergunta = sys.argv[1] if len(sys.argv) > 1 else "Como equilibrar dar generosamente e saber colocar limites?"
    r = gerar_resposta(pergunta)
    print(f"PERGUNTA: {r['pergunta']}\n")
    print(f"SEFIROT: {r['classificacao']['sefirot']}")
    print(f"RELACOES ESTRUTURAIS: {r['relacoes_estruturais']}")
    print(f"CHUNKS USADOS: {[c['documento'] for c in r['chunks_usados']]}\n")
    print("RESPOSTA:")
    print(r["resposta"])
