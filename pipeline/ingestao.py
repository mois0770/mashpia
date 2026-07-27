"""Ingestão de documentos: .odt/.txt -> texto -> chunks por parágrafo.

Não faz classificação nem grava nada em definitivo — isso é passo seguinte
(sugestao.py / confirmacao.py), porque nenhum chunk pode ser tratado como
EXPRESSA/DEFINE de verdade sem confirmação humana (ver critério 4.1 do
documento de arquitetura).
"""

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChunkBruto:
    id: str
    texto: str
    documento_origem: str
    caminho_origem: str
    posicao: int


def odt_para_texto(caminho_odt: Path) -> str:
    resultado = subprocess.run(
        ["pandoc", str(caminho_odt), "-t", "plain"],
        capture_output=True, text=True, check=True,
    )
    return resultado.stdout


def carregar_texto(caminho: Path) -> str:
    if caminho.suffix.lower() == ".odt":
        return odt_para_texto(caminho)
    return caminho.read_text(encoding="utf-8", errors="replace")


def chunkear_por_paragrafo(
    texto: str, tamanho_minimo: int = 40, tamanho_alvo: int = 150,
    tamanho_max_bloco: int = 2000,
) -> list[str]:
    """Divide em parágrafos e mescla fragmentos curtos com o seguinte, até
    atingir `tamanho_alvo` — evita chunks do tipo "…With regard to your
    inclination towards a feeling of sadness:" sem contexto suficiente.

    Primeiro separa por linha em branco (parágrafo "normal", como no texto
    vindo do pandoc). Qualquer bloco resultante maior que
    `tamanho_max_bloco` é, por sua vez, quebrado por linha simples — caso de
    .txt digitados manualmente onde cada ponto numerado ocupa uma linha
    (ex.: Klalei.txt), sem linha em branco real entre eles.
    """
    paragrafos = []
    for bloco in texto.split("\n\n"):
        bloco = bloco.strip()
        if not bloco:
            continue
        junto = " ".join(linha.strip() for linha in bloco.splitlines()).strip()
        if len(junto) <= tamanho_max_bloco:
            if junto:
                paragrafos.append(junto)
        else:
            for linha in bloco.splitlines():
                linha = linha.strip()
                if linha:
                    paragrafos.append(linha)

    mesclados: list[str] = []
    buffer = ""
    for p in paragrafos:
        buffer = f"{buffer} {p}".strip() if buffer else p
        if len(buffer) >= tamanho_alvo:
            mesclados.append(buffer)
            buffer = ""
    if buffer:
        if mesclados and len(buffer) < tamanho_minimo:
            mesclados[-1] = f"{mesclados[-1]} {buffer}".strip()
        elif len(buffer) >= tamanho_minimo:
            mesclados.append(buffer)

    return mesclados


def _id_estavel(documento: str, posicao: int, texto: str) -> str:
    """ID determinístico (documento + posição + hash do texto) — precisa ser
    estável entre execuções para que reprocessar o corpus faça `upsert` de
    verdade no ChromaDB, em vez de duplicar tudo a cada rodada."""
    resumo = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]
    base = documento.replace(" ", "_")
    return f"{base}__{posicao}__{resumo}"


def processar_documento(caminho: Path) -> list[ChunkBruto]:
    texto = carregar_texto(caminho)
    paragrafos = chunkear_por_paragrafo(texto)
    return [
        ChunkBruto(
            id=_id_estavel(caminho.name, i, paragrafo),
            texto=paragrafo,
            documento_origem=caminho.name,
            caminho_origem=str(caminho),
            posicao=i,
        )
        for i, paragrafo in enumerate(paragrafos)
    ]


def processar_pasta(pasta: Path, extensoes=(".odt", ".txt")) -> list[ChunkBruto]:
    chunks = []
    for caminho in sorted(pasta.iterdir()):
        if caminho.suffix.lower() in extensoes and not caminho.name.startswith("00_"):
            chunks.extend(processar_documento(caminho))
    return chunks


if __name__ == "__main__":
    import sys
    alvo = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if alvo is None:
        print("Uso: python3 ingestao.py <arquivo_ou_pasta>")
        sys.exit(1)
    resultado = processar_documento(alvo) if alvo.is_file() else processar_pasta(alvo)
    print(f"{len(resultado)} chunks extraídos de {alvo}")
    for c in resultado[:3]:
        print(f"  [{c.posicao}] {c.texto[:100]}...")
