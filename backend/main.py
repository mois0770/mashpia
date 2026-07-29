"""API HTTP do MASHPIA. Rodar com:
    uvicorn backend.main:app --reload --port 8000
"""

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.adam_kadmon import classificar
from backend.gerar_resposta import NIVEL_PADRAO, gerar_resposta
from backend.limites import TetoDeCustoAtingido
from backend.openrouter_client import ErroOpenRouter
from grafo.schema import grafo_singleton

app = FastAPI(title="Mashpia", description="Chatbot Filosofia Chabad — API")

_grafo = grafo_singleton()


@app.exception_handler(ErroOpenRouter)
def erro_openrouter_handler(request: Request, exc: ErroOpenRouter):
    return JSONResponse(status_code=503, content={"erro": str(exc)})


@app.exception_handler(TetoDeCustoAtingido)
def teto_custo_handler(request: Request, exc: TetoDeCustoAtingido):
    return JSONResponse(status_code=429, content={"erro": str(exc)})


class PerguntaRequest(BaseModel):
    pergunta: str
    nivel: int = NIVEL_PADRAO


@app.get("/estatisticas")
def estatisticas():
    import chromadb
    from config import CHROMA_DIR
    from pipeline.vetorizar import NOME_COLECAO

    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    colecao = cliente.get_collection(NOME_COLECAO)
    todos = colecao.get(include=["metadatas"])

    por_pasta: dict[str, int] = {}
    por_tema: dict[str, int] = {}
    for m in todos["metadatas"]:
        por_pasta[m["pasta"]] = por_pasta.get(m["pasta"], 0) + 1
        for t in m["temas"].split(","):
            if t:
                por_tema[t] = por_tema.get(t, 0) + 1

    return {
        "total_chunks": colecao.count(),
        "chunks_por_pasta": por_pasta,
        "chunks_por_tema": por_tema,
    }


@app.get("/grafo")
def grafo():
    por_categoria: dict[str, int] = {}
    for _, dados in _grafo.nodes(data=True):
        cat = dados.get("categoria", "?")
        por_categoria[cat] = por_categoria.get(cat, 0) + 1

    por_tipo_aresta: dict[str, int] = {}
    for _, _, dados in _grafo.edges(data=True):
        tipo = dados.get("tipo", "?")
        por_tipo_aresta[tipo] = por_tipo_aresta.get(tipo, 0) + 1

    return {
        "nos_por_categoria": por_categoria,
        "arestas_por_tipo": por_tipo_aresta,
        "total_nos": _grafo.number_of_nodes(),
        "total_arestas": _grafo.number_of_edges(),
    }


@app.post("/classificar")
def classificar_endpoint(req: PerguntaRequest):
    return classificar(req.pergunta)


@app.post("/responder")
def responder_endpoint(req: PerguntaRequest):
    return gerar_resposta(req.pergunta, nivel=req.nivel)


@app.get("/")
def raiz():
    return {
        "servico": "Mashpia — Chatbot Filosofia Chabad",
        "endpoints": ["GET /estatisticas", "GET /grafo", "POST /classificar", "POST /responder"],
    }
