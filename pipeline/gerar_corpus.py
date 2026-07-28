"""Combina os metadados confirmados (metadados_confirmados.py) com o texto real
dos documentos (via ingestao.py) e grava o corpus estruturado final.

Cada Chunk de saída carrega TODAS as tags do documento de origem (Sefirah,
Tema, autoria, Entidade) — simplificação documentada em
metadados_confirmados.py: não há, ainda, granularidade de tag por parágrafo.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.ingestao import processar_documento
from pipeline.metadados_confirmados import DOCUMENTOS

RAIZ_CORPUS = Path("/home/m/GraphRAG/CHAT_NIVEL_2")


def resolver_arquivo(pasta: str, chave: str) -> Path:
    diretorio = RAIZ_CORPUS / pasta
    todos = [p for p in diretorio.iterdir() if p.suffix.lower() in (".odt", ".txt")]

    exatos = [p for p in todos if p.name == chave]
    if len(exatos) == 1:
        return exatos[0]

    candidatos = [p for p in todos if chave in p.name]
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo com chave '{chave}' em {diretorio}")
    if len(candidatos) > 1:
        raise ValueError(f"Chave '{chave}' ambígua em {diretorio}: {[c.name for c in candidatos]}")
    return candidatos[0]


def gerar() -> dict:
    saida = {"_nota": (
        "Corpus gerado combinando metadados confirmados na conversa de design "
        "com o texto real dos documentos, chunkeado por parágrafo. Tags são "
        "aplicadas por documento inteiro (ver metadados_confirmados.py)."
    ), "chunks": []}

    erros = []
    for doc in DOCUMENTOS:
        try:
            caminho = resolver_arquivo(doc["pasta"], doc["chave"])
        except (FileNotFoundError, ValueError) as e:
            erros.append(str(e))
            continue

        chunks_brutos = processar_documento(caminho)
        entidades_doc = doc.get("entidades", [])
        for c in chunks_brutos:
            # Entidade só é aplicada ao chunk se o nome dela aparecer de fato
            # no texto — ao contrário de Sefirah/Tema, aplicar a TODOS os
            # chunks do documento (como fazíamos antes) fazia a etapa B do
            # classificador ver texto que não menciona a Entidade nenhuma vez
            # (achado na calibração de 2026-07-24: chunk do cabeçalho de
            # Klalei.txt marcado Pnimi/Makif sem citar nenhum dos dois).
            entidades_chunk = [
                e for e in entidades_doc
                if e.split("_")[0].lower() in c.texto.lower()
            ]
            saida["chunks"].append({
                "id": c.id,
                "texto": c.texto,
                "posicao": c.posicao,
                "documento": caminho.name,
                "pasta": doc["pasta"],
                "caminho": str(caminho),
                "autoria": doc["autoria"],
                "temas": doc["temas"],
                "sefirot_define": doc["sefirot_define"],
                "sefirot_expressa": doc["sefirot_expressa"],
                "entidades": entidades_chunk,
                "conceitos_estruturais": doc.get("conceitos_estruturais", []),
                "observacoes_documento": doc["observacoes"],
            })

    if erros:
        print(f"AVISO: {len(erros)} documento(s) não resolvidos:", file=sys.stderr)
        for e in erros:
            print(f"  - {e}", file=sys.stderr)

    return saida


if __name__ == "__main__":
    resultado = gerar()
    destino = Path(__file__).resolve().parent / "corpus_confirmado.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(resultado['chunks'])} chunks gravados em {destino}")

    docs_unicos = {c["documento"] for c in resultado["chunks"]}
    print(f"{len(docs_unicos)} documentos processados com sucesso de {len(DOCUMENTOS)} esperados")
