"""Geração de resposta final — o módulo que efetivamente conversa com o
usuário. Para uma pergunta, em ordem:

1. Classifica (adam_kadmon.classificar_com_vizinhos) e recupera os chunks
   EXPRESSA/DEFINE relevantes às Sefirot/Entidades identificadas.
2. Expande por grafo (grafo.schema.expandir_por_grafo): SINTETIZA/CANALIZA/
   GOVERNA viram travessia real no NetworkX a partir das Sefirot ativadas,
   não inferência implícita do LLM a partir do texto dos chunks.
3. Monta o contexto: além do texto dos chunks, cada um ganha uma nota
   inline quando tem peso alto (>= PESO_MINIMO_DESTAQUE) num dos
   CONCEITOS_ESTRUTURAIS (Dirá BeTachtonim etc.) — mesmo princípio do
   grafo, sinalizar explicitamente em vez de depender de síntese implícita.
4. Gera com o prompt fixo (00_Prompt_Sistema_Fixo.txt) como system message,
   ajustado pelo nível de resposta escolhido (NIVEIS: extensão/estrutura
   variam, as regras de conteúdo do prompt fixo nunca).
5. Chama a OpenRouter via openrouter_client.post_com_retry (retry com
   backoff em timeout/desconexão/429/5xx). `gerar_resposta_stream` trata
   separadamente uma queda NO MEIO do streaming (depois que a resposta já
   começou a chegar) — não é caso de retry, gera uma nota de interrupção.

Antes de tudo isso, `limites.verificar_teto()` checa o teto diário de gasto
(backend/limites.py) — se já atingido, recusa a pergunta sem gastar mais
nada, em vez de deixar o pipeline inteiro rodar pra só então recusar.

Calibrado com checklist do prompt fixo + verificação de fidelidade de
citação — ver 00_Estado_Atual.txt seção 4.8 para o histórico de calibração.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.adam_kadmon import _dividir, classificar_com_vizinhos
from backend.limites import registrar_custo, verificar_teto
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


def _detectar_idioma(pergunta: str) -> str:
    """Nomeia o idioma da pergunta, para reforçar IDIOMA DA RESPOSTA de forma
    explícita (não apenas relativa, "a mesma língua") — só dizer "responda na
    mesma língua da pergunta" não bastou quando o contexto vem quase todo em
    português (protocolo_lacuna: chunks=[]); 5 de 6 amostras em inglês
    saíram em português mesmo com esse lembrete relativo. Chamada dedicada e
    barata (poucos tokens de saída); se falhar, devolve "" e quem chamar cai
    de volta no lembrete relativo genérico."""
    try:
        resp = post_com_retry(
            "/chat/completions",
            {"model": LLM_MODEL, "temperature": 0, "max_tokens": 30,
             "messages": [{"role": "user", "content":
                 "Em que idioma esta frase foi escrita? Responda só com o nome do idioma, em "
                 f"português (ex: português, inglês, espanhol, hebraico, francês):\n\n{pergunta}"}]},
            timeout=20,
        )
        conteudo = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        return conteudo.rstrip(".").lower()
    except (ErroOpenRouter, KeyError, IndexError):
        return ""


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
    verificar_teto()
    classificacao, vizinhos = classificar_com_vizinhos(pergunta)
    relacoes = expandir_por_grafo(classificacao["sefirot"])

    if classificacao["protocolo_lacuna"]:
        chunks = []
    else:
        alvos = set(classificacao["sefirot"]) | set(classificacao["entidades"])
        alvos |= set(relacoes["sefirot_expandidas"])
        chunks = _filtrar_chunks_para_geracao(vizinhos, alvos)

    contexto = _montar_contexto(classificacao, chunks, relacoes)
    # Reforço próximo à pergunta (não só no system prompt) — nomeando o
    # idioma explicitamente, não só "a mesma língua desta pergunta" (esse
    # lembrete relativo sozinho não bastou: 5 de 6 amostras em inglês
    # saíram em português quando a pergunta caía em protocolo_lacuna,
    # contexto quase todo em português sem texto em inglês pra ancorar).
    idioma = _detectar_idioma(pergunta)
    if idioma:
        lembrete_idioma = (
            f"(RESPONDA EM {idioma.upper()} — esta pergunta foi escrita em {idioma}, mesmo que "
            "o contexto abaixo esteja majoritariamente noutro idioma.)"
        )
    else:
        lembrete_idioma = "(Responda na mesma língua em que esta pergunta foi escrita.)"
    mensagens = [
        {"role": "system", "content": _prompt_fixo(nivel)},
        {"role": "user", "content": f"Pergunta: {pergunta}\n{lembrete_idioma}\n\n{contexto}"},
    ]
    chunks_usados = [{"documento": c["meta"]["documento"], "texto": c["texto"]} for c in chunks]
    return classificacao, chunks_usados, relacoes, mensagens


def gerar_resposta(pergunta: str, nivel: int = NIVEL_PADRAO) -> dict:
    classificacao, chunks_usados, relacoes, mensagens = _preparar_geracao(pergunta, nivel)
    max_tokens = NIVEIS.get(nivel, NIVEIS[NIVEL_PADRAO])["max_tokens"]

    # Mesmo risco de "reasoning tokens" estourando o max_tokens antes de
    # emitir conteúdo (content=None) — visto de forma reproduzível com
    # perguntas em hebraico (ver adam_kadmon.etapa_b, mesmo padrão de retry).
    ultimo_erro = None
    resposta_texto = None
    for _tentativa in range(1, 3 + 1):
        resp = post_com_retry(
            "/chat/completions",
            {"model": LLM_MODEL, "messages": mensagens, "max_tokens": max_tokens, "temperature": 0.4},
            timeout=90,
        )
        escolha = resp.json()["choices"][0]
        conteudo = (escolha["message"]["content"] or "").strip()
        if conteudo:
            resposta_texto = conteudo
            break
        ultimo_erro = f"resposta vazia (finish_reason={escolha.get('finish_reason')})"
    else:
        raise ErroOpenRouter(
            "Não consegui gerar uma resposta agora — o modelo não respondeu de forma "
            f"utilizável após {_tentativa} tentativas ({ultimo_erro}). Tente novamente."
        )

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
         "temperature": 0.4, "stream": True,
         # pede o resumo de uso (inclui "cost") no evento final do SSE —
         # sem isso o streaming não tem custo disponível em lugar nenhum,
         # ao contrário da chamada não-streaming (post_com_retry já registra
         # sozinho). Ver limites.py.
         "usage": {"include": True}},
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
                    custo = obj.get("usage", {}).get("cost")
                    if custo:
                        registrar_custo(custo)
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
