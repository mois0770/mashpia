"""Gera embeddings (OpenRouter) para os chunks de corpus_confirmado.json e
grava no índice vetorial — Qdrant Cloud quando configurado (QDRANT_URL/
QDRANT_API_KEY, ver config.get_qdrant_config), senão ChromaDB local (mesmo
fallback já usado em backend/limites.py pro Supabase).

Migração 2026-08-10: testado com reboot manual do Streamlit Community Cloud
que data/chroma/ NÃO sobrevive a reboot/redeploy — cada reboot disparava
reembedding automático do corpus inteiro (custo real medido: ~US$0,02 por
vez). Qdrant Cloud resolve isso (índice vive fora do container).

Campos de metadado que são listas (temas, sefirot_define, sefirot_expressa,
entidades) são gravados como string separada por vírgula em ambos os
backends — o ChromaDB só aceita valores escalares em metadado, e mantive o
mesmo formato no Qdrant por simetria (facilita comparar/migrar dados).
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHROMA_DIR, EMBEDDING_MODEL, get_qdrant_config
from backend.openrouter_client import post_com_retry
from grafo.schema import CONCEITOS_ESTRUTURAIS

CORPUS_JSON = Path(__file__).resolve().parent / "corpus_confirmado.json"
NOME_COLECAO = "mashpia_chunks"
TAMANHO_LOTE = 50

# Dimensão de saída do openai/text-embedding-3-large (medido: len(embedding) == 3072)
# — só usado para criar a coleção no Qdrant, que precisa do tamanho do vetor
# de antemão (ChromaDB infere sozinho, não precisa disso).
DIMENSAO_EMBEDDING = 3072


def embed_lote(textos: list[str]) -> list[list[float]]:
    resp = post_com_retry(
        "/embeddings",
        {"model": EMBEDDING_MODEL, "input": textos},
        timeout=60,
    )
    dados = resp.json()["data"]
    return [item["embedding"] for item in dados]


def _lista_para_str(valor) -> str:
    return ",".join(valor) if valor else ""


def _pesos_conceitos(conceitos_estruturais) -> dict[str, int]:
    """Achata a lista [{conceito, peso, justificativa}, ...] em campos
    escalares "peso_<id>" — um campo por conceito conhecido em
    CONCEITOS_ESTRUTURAIS, 0 se o chunk não tem pontuação para ele (documento
    ainda não passou por sugerir_tags.py)."""
    por_nome = {c["conceito"]: c["peso"] for c in (conceitos_estruturais or [])}
    return {
        f"peso_{c['id']}": por_nome.get(c["nome"], 0)
        for c in CONCEITOS_ESTRUTURAIS
    }


def _metadados_chunk(c: dict) -> dict:
    return {
        "documento": c["documento"],
        "pasta": c["pasta"],
        "autoria": c["autoria"] or "",
        "temas": _lista_para_str(c["temas"]),
        "sefirot_define": _lista_para_str(c["sefirot_define"]),
        "sefirot_expressa": _lista_para_str(c["sefirot_expressa"]),
        "entidades": _lista_para_str(c["entidades"]),
        "posicao": c["posicao"],
        **_pesos_conceitos(c.get("conceitos_estruturais")),
    }


# --- Backend Qdrant ----------------------------------------------------

def _cliente_qdrant():
    from qdrant_client import QdrantClient
    url, chave = get_qdrant_config()
    return QdrantClient(url=url, api_key=chave)


def _uuid_do_chunk(chunk_id: str) -> str:
    """Qdrant só aceita ID de ponto inteiro ou UUID — os ids do corpus são
    strings arbitrárias (ex. '01_Keter.odt__0__743dbe509e'). Gera um UUID
    determinístico a partir da string (mesmo id sempre vira o mesmo UUID,
    upsert continua idempotente) e guarda o id original no payload
    ("id_original") pra recuperar depois nas buscas."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _popular_qdrant(chunks: list[dict]) -> None:
    from qdrant_client import models

    cliente = _cliente_qdrant()
    if not cliente.collection_exists(NOME_COLECAO):
        cliente.create_collection(
            NOME_COLECAO,
            vectors_config=models.VectorParams(size=DIMENSAO_EMBEDDING, distance=models.Distance.COSINE),
        )

    total = len(chunks)
    for inicio in range(0, total, TAMANHO_LOTE):
        lote = chunks[inicio:inicio + TAMANHO_LOTE]
        textos = [c["texto"] for c in lote]
        embeddings = embed_lote(textos)

        cliente.upsert(
            collection_name=NOME_COLECAO,
            points=[
                models.PointStruct(
                    id=_uuid_do_chunk(c["id"]),
                    vector=emb,
                    payload={"id_original": c["id"], "texto": c["texto"], **_metadados_chunk(c)},
                )
                for c, emb in zip(lote, embeddings)
            ],
        )
        print(f"  {min(inicio + TAMANHO_LOTE, total)}/{total} chunks vetorizados (Qdrant)")
        time.sleep(0.2)

    ids_atuais = {_uuid_do_chunk(c["id"]) for c in chunks}
    ids_na_colecao: set[str] = set()
    deslocamento = None
    while True:
        pontos, deslocamento = cliente.scroll(
            NOME_COLECAO, limit=1000, offset=deslocamento, with_payload=False, with_vectors=False,
        )
        ids_na_colecao.update(str(p.id) for p in pontos)
        if deslocamento is None:
            break
    orfaos = list(ids_na_colecao - ids_atuais)
    if orfaos:
        cliente.delete(NOME_COLECAO, points_selector=orfaos)
        print(f"Removidos {len(orfaos)} chunks órfãos (Qdrant).")

    total_final = cliente.count(NOME_COLECAO).count
    print(f"Concluído: {total_final} chunks na coleção '{NOME_COLECAO}' (Qdrant)")


# --- Backend ChromaDB local (fallback sem Qdrant configurado) ----------

def _popular_chroma(chunks: list[dict]) -> None:
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    colecao = cliente.get_or_create_collection(NOME_COLECAO)

    total = len(chunks)
    for inicio in range(0, total, TAMANHO_LOTE):
        lote = chunks[inicio:inicio + TAMANHO_LOTE]
        textos = [c["texto"] for c in lote]
        embeddings = embed_lote(textos)

        colecao.upsert(
            ids=[c["id"] for c in lote],
            embeddings=embeddings,
            documents=textos,
            metadatas=[_metadados_chunk(c) for c in lote],
        )
        print(f"  {min(inicio + TAMANHO_LOTE, total)}/{total} chunks vetorizados (Chroma local)")
        time.sleep(0.2)

    # upsert só adiciona/atualiza — nunca remove. Se um documento saiu do
    # corpus (removido/dividido em metadados_confirmados.py), seus chunks
    # antigos ficam órfãos na coleção para sempre sem isto (achado real:
    # 826 chunks órfãos de 13 documentos divididos em 2026-07-28, coleção
    # com 2312 quando o corpus tinha só 1486).
    ids_atuais = {c["id"] for c in chunks}
    ids_na_colecao = set(colecao.get(include=[])["ids"])
    orfaos = list(ids_na_colecao - ids_atuais)
    if orfaos:
        colecao.delete(ids=orfaos)
        print(f"Removidos {len(orfaos)} chunks órfãos (documentos que saíram do corpus).")

    print(f"Concluído: {colecao.count()} chunks na coleção '{NOME_COLECAO}' em {CHROMA_DIR}")


# --- Interface pública, agnóstica de backend ----------------------------

def popular_indice() -> None:
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    chunks = corpus["chunks"]
    if get_qdrant_config():
        _popular_qdrant(chunks)
    else:
        _popular_chroma(chunks)


def contagem_atual() -> int:
    """Usado por interface/app.py pra decidir se precisa repopular o índice
    (achado 2026-08-10: um recontagem "count == esperado" é bem mais barata
    que reembedar tudo de novo à toa a cada rerun)."""
    if get_qdrant_config():
        cliente = _cliente_qdrant()
        if not cliente.collection_exists(NOME_COLECAO):
            return 0
        return cliente.count(NOME_COLECAO).count

    if not CHROMA_DIR.exists():
        return 0
    import chromadb
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        return cliente.get_collection(NOME_COLECAO).count()
    except Exception:
        return 0


def todas_metadatas() -> list[dict]:
    """Usado por backend/adam_kadmon.py (_taxa_base_tema) — metadado de
    TODOS os chunks da coleção, sem busca vetorial."""
    if get_qdrant_config():
        cliente = _cliente_qdrant()
        metadatas = []
        deslocamento = None
        while True:
            pontos, deslocamento = cliente.scroll(
                NOME_COLECAO, limit=1000, offset=deslocamento, with_payload=True, with_vectors=False,
            )
            metadatas.extend(p.payload for p in pontos)
            if deslocamento is None:
                break
        return metadatas

    import chromadb
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return cliente.get_collection(NOME_COLECAO).get(include=["metadatas"])["metadatas"]


def buscar_por_embeddings(embeddings: list[list[float]], n: int) -> list[list[dict]]:
    """Busca de similaridade — devolve, para CADA embedding de consulta, uma
    lista de até n resultados {"id", "texto", "distancia", "meta"}, MENOR
    distância = mais parecido (convenção do ChromaDB; Qdrant devolve
    similaridade de cosseno, onde MAIOR = mais parecido, então convertido
    aqui via `1 - score` pra manter a mesma convenção nos dois backends —
    backend/adam_kadmon.py._buscar_vizinhos não sabe qual banco está ativo)."""
    if get_qdrant_config():
        cliente = _cliente_qdrant()
        resultados = []
        for emb in embeddings:
            pontos = cliente.query_points(NOME_COLECAO, query=emb, limit=n, with_payload=True).points
            resultados.append([
                {
                    "id": p.payload["id_original"],
                    "texto": p.payload["texto"],
                    "distancia": 1 - p.score,
                    "meta": p.payload,
                }
                for p in pontos
            ])
        return resultados

    import chromadb
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    colecao = cliente.get_collection(NOME_COLECAO)
    resultado = colecao.query(query_embeddings=embeddings, n_results=n)
    resultados = []
    for busca in range(len(resultado["ids"])):
        resultados.append([
            {
                "id": resultado["ids"][busca][i],
                "texto": resultado["documents"][busca][i],
                "distancia": resultado["distances"][busca][i],
                "meta": resultado["metadatas"][busca][i],
            }
            for i in range(len(resultado["ids"][busca]))
        ])
    return resultados


if __name__ == "__main__":
    popular_indice()
