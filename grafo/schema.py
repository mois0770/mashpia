"""Schema estrutural do grafo — implementa a seção 3 de
GraphRAG/CHAT_NIVEL_2/01_Arquitetura_e_Criterios.txt.

Constrói o esqueleto fixo (EinSof, AdamKadmon, as 11 Sefirot, as Entidades e
Temas já confirmados, e as arestas estruturais entre eles). Chunks são
adicionados depois, pelo pipeline de curadoria — não fazem parte deste
módulo.
"""

import networkx as nx

SEFIROT = [
    {"id": "Keter", "coluna": "central", "ordem": 1, "tipo": "vontade"},
    {"id": "Chochmah", "coluna": "direita", "ordem": 2, "tipo": "mochin"},
    {"id": "Binah", "coluna": "esquerda", "ordem": 3, "tipo": "mochin"},
    {"id": "Daat", "coluna": "central", "ordem": 4, "tipo": "mochin"},
    {"id": "Chesed", "coluna": "direita", "ordem": 5, "tipo": "middah"},
    {"id": "Gevurah", "coluna": "esquerda", "ordem": 6, "tipo": "middah"},
    {"id": "Tiferet", "coluna": "central", "ordem": 7, "tipo": "middah"},
    {"id": "Netzach", "coluna": "direita", "ordem": 8, "tipo": "operacional"},
    {"id": "Hod", "coluna": "esquerda", "ordem": 9, "tipo": "operacional"},
    {"id": "Yesod", "coluna": "central", "ordem": 10, "tipo": "operacional"},
    {"id": "Malchut", "coluna": "central", "ordem": 11, "tipo": "expressao"},
]

# id interno único (evita a colisão de nome "Nefesh" entre nivel_alma e
# dimensao, já sinalizada no documento de arquitetura).
ENTIDADES = [
    {"id": "Nefesh_nivel", "nome": "Nefesh", "tipo": "nivel_alma"},
    {"id": "Ruach_nivel", "nome": "Ruach", "tipo": "nivel_alma"},
    {"id": "Neshamah_nivel", "nome": "Neshamah", "tipo": "nivel_alma"},
    {"id": "Chayah_nivel", "nome": "Chayah", "tipo": "nivel_alma"},
    {"id": "Yechidah_nivel", "nome": "Yechidah", "tipo": "nivel_alma"},
    {"id": "Pnimi", "nome": "Pnimi", "tipo": "par_estrutural"},
    {"id": "Makif", "nome": "Makif", "tipo": "par_estrutural"},
    {"id": "Olam_dimensao", "nome": "Olam (espaço)", "tipo": "dimensao"},
    {"id": "Shanah_dimensao", "nome": "Shanah (tempo)", "tipo": "dimensao"},
    {"id": "Nefesh_dimensao", "nome": "Nefesh (alma)", "tipo": "dimensao"},
    {"id": "Tzadik", "nome": "Tzadik", "tipo": "nivel_servico"},
    {"id": "Beinoni", "nome": "Beinoni", "tipo": "nivel_servico"},
    {"id": "Mashiach", "nome": "Mashiach", "tipo": "figura_messianica"},
    {"id": "Shechinah", "nome": "Shechinah", "tipo": "figura_messianica"},
]

TEMAS = [
    "Financas", "Casamento", "Lideranca", "Educacao", "Saude_Mental",
    "Autoestima", "Humildade", "Fundamentos", "Proposito",
]

# Conceitos centrais e sempre-ativos do projeto que frequentemente aparecem no
# corpus SEM usar o termo literal do projeto (achado de calibração 2026-07-28:
# "Dirá BeTachtonim" tem 0 ocorrências literais no corpus, mas o conceito
# subjacente aparece em 25 chunks em inglês, "dwelling in the lower realms").
# Lista extensível — adicionar aqui sempre que um novo conceito central for
# identificado como sofrendo o mesmo gap. Usada pela curadoria de peso
# (pipeline/sugerir_tags.py, passo 5 do fluxo em 00_Estado_Atual.txt).
CONCEITOS_ESTRUTURAIS = [
    {"id": "DiraBeTachtonim", "nome": "Dirá BeTachtonim",
     "definicao": "O Objetivo da Criação: que o mundo material se torne morada para a "
                   "Presença Divina. No corpus em inglês costuma aparecer sem o termo "
                   "literal, como \"a dwelling in the lower realms/worlds\", \"dwelling "
                   "below\"."},
    {"id": "MoachSholetAlHalev", "nome": "Moach Sholet Al HaLev",
     "definicao": "A Mente sempre governa o Sentimento (o \"Lev\"), nunca o contrário. "
                   "No corpus aparece como disciplina racional/intelectual sobre "
                   "impulso, emoção ou instinto, mesmo sem citar o termo hebraico."},
    {"id": "AdonOlam", "nome": "Adon Olam",
     "definicao": "Hino que explica a atuação Divina antes-durante-depois da Criação — "
                   "forma velada de se referir a Ein Sof, e nome dado ao próprio molde "
                   "retórico do projeto (abertura pela Fonte -> corpo -> fechamento na "
                   "Fonte). No corpus pode aparecer como discussão da atuação Divina "
                   "atemporal/eterna sem citar o hino pelo nome."},
]

# Nós do grafo usados como valor válido de sefirot_define/sefirot_expressa
# além dos 11 Sefirot nucleares — convenção já em uso em
# metadados_confirmados.py (ex.: "sefirot_define": ["EinSof", "AdamKadmon", "Keter"]).
SEFIROT_E_NOS_PONTE = [s["id"] for s in SEFIROT] + ["EinSof", "AdamKadmon"]

HISHTALSHELUT_ORDEM = [s["id"] for s in sorted(SEFIROT, key=lambda s: s["ordem"])]

MESMA_COLUNA_GRUPOS = {
    "direita": ["Chochmah", "Chesed", "Netzach"],
    "esquerda": ["Binah", "Gevurah", "Hod"],
    "central": ["Keter", "Daat", "Tiferet", "Yesod", "Malchut"],
}

SINTETIZA_TRIADES = [
    (("Chochmah", "Binah"), "Daat"),
    (("Chesed", "Gevurah"), "Tiferet"),
    (("Netzach", "Hod"), "Yesod"),
]

GOVERNA_ALVOS = ["Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"]

CANALIZA_PARES = [
    ("Chesed", "Netzach"),
    ("Gevurah", "Hod"),
    ("Tiferet", "Yesod"),
]


def construir_grafo() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()

    g.add_node("EinSof", categoria="EinSof")
    g.add_node("AdamKadmon", categoria="AdamKadmon")
    for s in SEFIROT:
        g.add_node(s["id"], categoria="Sefirah", coluna=s["coluna"],
                    ordem_hishtalshelut=s["ordem"], tipo=s["tipo"])
    for e in ENTIDADES:
        g.add_node(e["id"], categoria="Entidade", nome=e["nome"], tipo=e["tipo"])
    for t in TEMAS:
        g.add_node(t, categoria="Tema")

    g.add_edge("EinSof", "AdamKadmon", tipo="PONTE")
    g.add_edge("AdamKadmon", "Keter", tipo="PONTE")

    for origem, destino in zip(HISHTALSHELUT_ORDEM, HISHTALSHELUT_ORDEM[1:]):
        g.add_edge(origem, destino, tipo="HISHTALSHELUT")

    for grupo in MESMA_COLUNA_GRUPOS.values():
        for a, b in zip(grupo, grupo[1:]):
            g.add_edge(a, b, tipo="MESMA_COLUNA")
            g.add_edge(b, a, tipo="MESMA_COLUNA")

    for (a, b), destino in SINTETIZA_TRIADES:
        g.add_edge(a, destino, tipo="SINTETIZA", condicional=True, par=(a, b))
        g.add_edge(b, destino, tipo="SINTETIZA", condicional=True, par=(a, b))

    for alvo in GOVERNA_ALVOS:
        g.add_edge("Daat", alvo, tipo="GOVERNA")

    for origem, destino in CANALIZA_PARES:
        g.add_edge(origem, destino, tipo="CANALIZA")

    return g


_grafo_cache: nx.MultiDiGraph | None = None


def grafo_singleton() -> nx.MultiDiGraph:
    """Instância única do grafo por processo — evita reconstruir o esqueleto
    fixo a cada chamada de geração de resposta."""
    global _grafo_cache
    if _grafo_cache is None:
        _grafo_cache = construir_grafo()
    return _grafo_cache


def expandir_por_grafo(sefirot_ativas: list[str]) -> dict:
    """Traduz as Sefirot já ativadas pela classificação (adam_kadmon, etapas
    A/B) em relações estruturais do grafo que se aplicam de fato a ESTA
    consulta — travessia real, não regra genérica sempre-ativa.

    SINTETIZA só dispara quando os DOIS flancos da tríade estão entre as
    Sefirot ativas (critério confirmado: não forçar toda resposta a
    convergir em Daat/Tiferet/Yesod, ver 01_Arquitetura_e_Criterios.txt).
    CANALIZA é aresta fixa, surge sempre que a origem está ativa. GOVERNA já
    é princípio sempre-ativo no prompt fixo (Moach Sholet Al HaLev); aqui só
    instanciamos o alvo concreto quando Daat E esse alvo aparecem juntos
    entre as Sefirot ativas, tornando o princípio geral específico ao caso.
    """
    g = grafo_singleton()
    ativas = set(sefirot_ativas)

    sinteses = []
    vistos = set()
    for _, destino, dados in g.edges(data=True):
        if dados.get("tipo") != "SINTETIZA":
            continue
        par = dados["par"]
        if set(par) <= ativas and destino not in vistos:
            sinteses.append({"par": par, "destino": destino})
            vistos.add(destino)

    canais = [
        {"origem": origem, "destino": destino}
        for origem in ativas
        for _, destino, dados in g.out_edges(origem, data=True)
        if dados.get("tipo") == "CANALIZA"
    ]

    governancas = []
    if "Daat" in ativas:
        governancas = [
            {"origem": "Daat", "destino": destino}
            for _, destino, dados in g.out_edges("Daat", data=True)
            if dados.get("tipo") == "GOVERNA" and destino in ativas
        ]

    sefirot_expandidas = sorted(
        {s["destino"] for s in sinteses} | {c["destino"] for c in canais}
    )

    return {
        "sinteses": sinteses,
        "canais": canais,
        "governancas": governancas,
        "sefirot_expandidas": sefirot_expandidas,
    }


def resumo(g: nx.MultiDiGraph) -> str:
    por_categoria = {}
    for _, dados in g.nodes(data=True):
        cat = dados.get("categoria", "?")
        por_categoria[cat] = por_categoria.get(cat, 0) + 1
    por_tipo_aresta = {}
    for _, _, dados in g.edges(data=True):
        tipo = dados.get("tipo", "?")
        por_tipo_aresta[tipo] = por_tipo_aresta.get(tipo, 0) + 1
    linhas = ["Nos por categoria:"]
    linhas += [f"  {k}: {v}" for k, v in sorted(por_categoria.items())]
    linhas.append("Arestas por tipo:")
    linhas += [f"  {k}: {v}" for k, v in sorted(por_tipo_aresta.items())]
    return "\n".join(linhas)


if __name__ == "__main__":
    grafo = construir_grafo()
    print(resumo(grafo))
