"""Gera embeddings (OpenRouter) para os chunks de corpus_confirmado.json e
grava no ChromaDB local (fase 1 — ver seção 11.2 do documento de arquitetura).

Campos de metadado que são listas (temas, sefirot_define, sefirot_expressa,
entidades) são gravados como string separada por vírgula — o ChromaDB só
aceita valores escalares em metadado. Refinar para filtro por tag exata é
melhoria futura, não bloqueia o uso inicial.
"""

import json
import sys
import time
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHROMA_DIR, EMBEDDING_MODEL
from backend.openrouter_client import post_com_retry
from grafo.schema import CONCEITOS_ESTRUTURAIS

CORPUS_JSON = Path(__file__).resolve().parent / "corpus_confirmado.json"
NOME_COLECAO = "mashpia_chunks"
TAMANHO_LOTE = 50


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
    escalares "peso_<id>" (ChromaDB só aceita escalar em metadado) — um
    campo por conceito conhecido em CONCEITOS_ESTRUTURAIS, 0 se o chunk não
    tem pontuação para ele (documento ainda não passou por sugerir_tags.py)."""
    por_nome = {c["conceito"]: c["peso"] for c in (conceitos_estruturais or [])}
    return {
        f"peso_{c['id']}": por_nome.get(c["nome"], 0)
        for c in CONCEITOS_ESTRUTURAIS
    }


def popular_chromadb():
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    chunks = corpus["chunks"]

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
            metadatas=[{
                "documento": c["documento"],
                "pasta": c["pasta"],
                "autoria": c["autoria"] or "",
                "temas": _lista_para_str(c["temas"]),
                "sefirot_define": _lista_para_str(c["sefirot_define"]),
                "sefirot_expressa": _lista_para_str(c["sefirot_expressa"]),
                "entidades": _lista_para_str(c["entidades"]),
                "posicao": c["posicao"],
                **_pesos_conceitos(c.get("conceitos_estruturais")),
            } for c in lote],
        )
        print(f"  {min(inicio + TAMANHO_LOTE, total)}/{total} chunks vetorizados")
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


if __name__ == "__main__":
    popular_chromadb()
