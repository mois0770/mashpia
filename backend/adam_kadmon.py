"""Mecanismo de classificação de 3 eixos (Sefirah / Entidade / Tema) — seção 10
de 01_Arquitetura_e_Criterios.txt.

Etapa A: similaridade vetorial contra os chunks já recuperados — separa
candidatos de Sefirah/Entidade (só a partir de chunks marcados DEFINE, nunca
EXPRESSA sozinho, para não confundir aplicação com definição) dos candidatos
de Tema (que usam a vizinhança semântica geral, não só DEFINE).

Etapa B: um LLM decide quais candidatos realmente se aplicam, recebendo
SÓ o texto DEFINE recuperado — nunca conhecimento geral do modelo (regra do
critério 4.7 do documento: "o que algo é" só pode vir do corpus).

Se a etapa A não encontrar nenhum candidato de Sefirah/Entidade, aciona o
protocolo de lacuna (critério 4.6) em vez de forçar uma classificação.
"""

import json
import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHROMA_DIR, LLM_MODEL
from backend.openrouter_client import post_com_retry
from pipeline.vetorizar import NOME_COLECAO, embed_lote

N_CANDIDATOS_AMPLO = 30
N_CANDIDATOS_ESTREITO = 15
MAX_CANDIDATOS_ETAPA_B = 8


def _colecao():
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return cliente.get_collection(NOME_COLECAO)


_taxa_base_tema_cache: dict[str, float] | None = None


def _taxa_base_tema() -> dict[str, float]:
    """Frequência de cada Tema no corpus inteiro — usada para normalizar a
    contagem por vizinhança. Sem isso, Temas grandes (Fundamentos, Educacao)
    dominam qualquer busca só por volume, não por relevância real (bug
    observado: toda pergunta testada devolvia os mesmos 2 Temas, mesmo uma
    sobre dinheiro, que deveria ser Financas)."""
    global _taxa_base_tema_cache
    if _taxa_base_tema_cache is None:
        todos = _colecao().get(include=["metadatas"])
        contagem: dict[str, int] = {}
        total = len(todos["metadatas"])
        for m in todos["metadatas"]:
            for t in _dividir(m["temas"]):
                contagem[t] = contagem.get(t, 0) + 1
        _taxa_base_tema_cache = {t: n / total for t, n in contagem.items()}
    return _taxa_base_tema_cache


def _dividir(campo: str) -> list[str]:
    return [v for v in campo.split(",") if v]


def _traduzir_para_ingles(pergunta: str) -> str:
    """Boa parte do corpus (chabad.org, inner.org) está em inglês; uma
    pergunta em português busca pior nesses chunks por causa do gap
    entre idiomas no embedding (medido: mesma pergunta em inglês encontrou o
    chunk correto na posição 0; em português, na posição 132 — ver
    calibração de 2026-07-24). Traduzir a pergunta e buscar nos dois
    idiomas corrige isso sem precisar reprocessar o corpus inteiro."""
    resp = post_com_retry(
        "/chat/completions",
        {"model": LLM_MODEL, "temperature": 0, "max_tokens": 200,
         "messages": [{"role": "user", "content":
             f"Traduza para o inglês, só a tradução, nada mais:\n\n{pergunta}"}]},
        timeout=30,
    )
    return resp.json()["choices"][0]["message"]["content"].strip()


def _buscar_vizinhos(pergunta: str, n: int) -> list[dict]:
    pergunta_en = _traduzir_para_ingles(pergunta)
    embs = embed_lote([pergunta, pergunta_en])
    resultado = _colecao().query(query_embeddings=embs, n_results=n)

    melhor_por_id: dict[str, dict] = {}
    for busca in range(len(resultado["ids"])):
        for i in range(len(resultado["ids"][busca])):
            chunk_id = resultado["ids"][busca][i]
            dist = resultado["distances"][busca][i]
            if chunk_id not in melhor_por_id or dist < melhor_por_id[chunk_id]["distancia"]:
                melhor_por_id[chunk_id] = {
                    "texto": resultado["documents"][busca][i],
                    "distancia": dist,
                    "meta": resultado["metadatas"][busca][i],
                }

    return sorted(melhor_por_id.values(), key=lambda v: v["distancia"])[:n]


def etapa_a(pergunta: str, vizinhos: list[dict] | None = None) -> dict:
    """Retorna candidatos de Sefirah/Entidade (só DEFINE, janela estreita
    primeiro, expande se vier vazia) e candidatos de Tema (janela ampla,
    qualquer chunk).

    Busca UMA VEZ o conjunto amplo (N_CANDIDATOS_AMPLO) e deriva a janela
    estreita como um recorte dele (os N_CANDIDATOS_ESTREITO mais próximos já
    são um subconjunto dos N_CANDIDATOS_AMPLO mais próximos, por definição de
    "mais próximo") — evita duas buscas (duas traduções, dois embeddings)
    quando antes só a estreita bastava. Se `vizinhos` for passado (já buscado
    por outra chamada), reaproveita sem nenhuma consulta nova — usado por
    gerar_resposta.py para não repetir a mesma busca (ver calibração de
    performance, 2026-07-27)."""
    if vizinhos is None:
        vizinhos = _buscar_vizinhos(pergunta, N_CANDIDATOS_AMPLO)
    estreito = vizinhos[:N_CANDIDATOS_ESTREITO]
    amplo = vizinhos

    def extrair_define(vizinhos, textos_por_candidato_max=2):
        """Para cada Sefirah/Entidade candidata, guarda até
        `textos_por_candidato_max` textos dos chunks mais próximos que a
        definem — não só o único mais próximo. Um chunk de tabela-resumo
        (define várias Sefirot de uma vez) só entra no ranking pela sua
        própria distância, mas cada candidato pode reunir texto de mais de
        um chunk, para não perder uma definição melhor só porque não foi
        estritamente a mais próxima entre todas as ocorrências."""
        melhor_distancia = {}
        ocorrencias_por_candidato: dict[tuple, list] = {}
        for v in vizinhos:
            for campo, destino in (("sefirot_define", "sefirah"), ("entidades", "entidade")):
                for nome in _dividir(v["meta"][campo]):
                    chave = (destino, nome)
                    if chave not in melhor_distancia or v["distancia"] < melhor_distancia[chave]:
                        melhor_distancia[chave] = v["distancia"]
                    ocorrencias_por_candidato.setdefault(chave, []).append(v)

        # Prefere, para o texto mostrado na etapa B, chunks onde o nome do
        # candidato aparece de fato — um chunk só "conta" por herdar a tag do
        # documento inteiro (ex.: cabeçalho de Klalei.txt tagueado Pnimi/Makif
        # sem mencionar nenhum dos dois) pode enganar a etapa B sobre o que o
        # conceito realmente significa. Ver calibração 2026-07-24.
        textos_por_candidato: dict[tuple, list[str]] = {}
        for chave, ocorrencias in ocorrencias_por_candidato.items():
            _, nome = chave
            com_nome = [o for o in ocorrencias if nome.split("_")[0].lower() in o["texto"].lower()]
            ordenados = sorted(com_nome or ocorrencias, key=lambda o: o["distancia"])
            textos_por_candidato[chave] = [o["texto"] for o in ordenados[:textos_por_candidato_max]]

        ordenado = sorted(melhor_distancia.items(), key=lambda kv: kv[1])[:MAX_CANDIDATOS_ETAPA_B]
        sefirot = {nome: "\n---\n".join(textos_por_candidato[("sefirah", nome)])
                   for (tipo, nome), _ in ordenado if tipo == "sefirah"}
        entidades = {nome: "\n---\n".join(textos_por_candidato[("entidade", nome)])
                     for (tipo, nome), _ in ordenado if tipo == "entidade"}
        return sefirot, entidades

    sefirot, entidades = extrair_define(estreito)
    if not sefirot and not entidades:
        sefirot, entidades = extrair_define(amplo)

    vizinhos_tema = amplo
    contagem_bruta: dict[str, int] = {}
    for v in vizinhos_tema:
        for t in _dividir(v["meta"]["temas"]):
            contagem_bruta[t] = contagem_bruta.get(t, 0) + 1

    taxa_base = _taxa_base_tema()
    n = len(vizinhos_tema)
    # lift: quantas vezes mais frequente que o esperado ao acaso, dado o
    # tamanho do Tema no corpus inteiro — sem isso, Temas grandes (Fundamentos,
    # Educacao) vencem qualquer busca só por volume, nunca por relevância.
    # MIN_OCORRENCIAS evita que uma única ocorrência isolada de um Tema raro
    # (base rate baixo) domine o ranking por lift sem sinal real de repetição.
    MIN_OCORRENCIAS = 2
    temas_lift = {
        t: contagem / (taxa_base.get(t, 1e-6) * n)
        for t, contagem in contagem_bruta.items()
        if contagem >= MIN_OCORRENCIAS
    }
    if not temas_lift:
        temas_lift = {
            t: contagem / (taxa_base.get(t, 1e-6) * n)
            for t, contagem in contagem_bruta.items()
        }

    return {
        "sefirot_candidatos": sefirot,
        "entidades_candidatos": entidades,
        "temas_candidatos": temas_lift,
        "vizinhos": vizinhos,
    }


PROMPT_ETAPA_B = """Você vai decidir quais conceitos abaixo a pergunta do usuário realmente ativa.

Use EXCLUSIVAMENTE as definições fornecidas abaixo — nunca conhecimento geral seu sobre \
Cabala ou Chassidut. Seja seletivo: inclua só os conceitos CENTRAIS para responder a pergunta, \
não qualquer um com relação remota ou tangencial. Prefira 1 a 3 conceitos bem escolhidos a uma \
lista longa. Se a pergunta não tiver relação genuína com uma definição, não a inclua.

Pergunta do usuário: {pergunta}

Definições disponíveis:
{definicoes}

Responda em JSON estrito, sem nenhum texto fora do JSON, no formato:
{{"aplicaveis": ["nome1", "nome2"], "justificativa": "uma frase curta"}}
Se nenhuma definição se aplicar de verdade, responda {{"aplicaveis": [], "justificativa": "..."}}.
"""


def etapa_b(pergunta: str, candidatos: dict[str, str]) -> dict:
    if not candidatos:
        return {"aplicaveis": [], "justificativa": "sem candidatos para avaliar"}

    definicoes = "\n\n".join(f"[{nome}]\n{texto}" for nome, texto in candidatos.items())
    prompt = PROMPT_ETAPA_B.format(pergunta=pergunta, definicoes=definicoes)

    resp = post_com_retry(
        "/chat/completions",
        {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
         "max_tokens": 400, "temperature": 0},
        timeout=60,
    )
    conteudo = resp.json()["choices"][0]["message"]["content"].strip()
    conteudo = conteudo.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        return {"aplicaveis": [], "justificativa": f"resposta do LLM não era JSON válido: {conteudo[:200]}"}


def classificar(pergunta: str) -> dict:
    resultado, _vizinhos = classificar_com_vizinhos(pergunta)
    return resultado


def classificar_com_vizinhos(pergunta: str) -> tuple[dict, list[dict]]:
    """Igual a `classificar`, mas também devolve os vizinhos buscados — para
    quem (gerar_resposta.py) precisa filtrar chunks para geração logo em
    seguida, sem repetir a busca (tradução + embedding + consulta ao
    ChromaDB) do zero. `classificar` é só um atalho que descarta essa
    segunda parte, mantido para não mudar a assinatura já usada por
    main.py e teste_calibracao.py."""
    candidatos = etapa_a(pergunta)
    vizinhos = candidatos["vizinhos"]

    if not candidatos["sefirot_candidatos"] and not candidatos["entidades_candidatos"]:
        return {
            "protocolo_lacuna": True,
            "sefirot": [], "entidades": [], "temas": list(candidatos["temas_candidatos"].keys()),
            "justificativa": "Nenhuma Sefirah ou Entidade com definição no corpus se aproxima desta pergunta.",
        }, vizinhos

    todos_candidatos = {**candidatos["sefirot_candidatos"], **candidatos["entidades_candidatos"]}
    decisao = etapa_b(pergunta, todos_candidatos)
    aplicaveis = set(decisao.get("aplicaveis", []))

    sefirot_finais = [s for s in candidatos["sefirot_candidatos"] if s in aplicaveis]
    entidades_finais = [e for e in candidatos["entidades_candidatos"] if e in aplicaveis]
    temas_ordenados = sorted(candidatos["temas_candidatos"].items(), key=lambda kv: -kv[1])

    # Etapa A achou candidatos, mas a etapa B rejeitou todos como não
    # centrais o suficiente — do ponto de vista de quem gera a resposta,
    # isso é o mesmo caso da lacuna: não há Sefirah/Entidade para ancorar.
    if not sefirot_finais and not entidades_finais:
        return {
            "protocolo_lacuna": True,
            "sefirot": [], "entidades": [], "temas": [t for t, _ in temas_ordenados[:3]],
            "justificativa": decisao.get("justificativa", "Candidatos encontrados não se aplicam de fato à pergunta."),
        }, vizinhos

    return {
        "protocolo_lacuna": False,
        "sefirot": sefirot_finais,
        "entidades": entidades_finais,
        "temas": [t for t, _ in temas_ordenados[:3]],
        "justificativa": decisao.get("justificativa", ""),
    }, vizinhos


if __name__ == "__main__":
    pergunta = sys.argv[1] if len(sys.argv) > 1 else "Por que Deus quis criar o mundo material?"
    resultado = classificar(pergunta)
    print(f"Pergunta: {pergunta}\n")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
