"""Diagnóstico de dispersão temática — Etapa 1 do fluxo planejado em
00_Estado_Atual.txt ("Como incluir textos novos no corpus", fluxo
planejado 2026-07-28).

Para cada documento já curado, reconstitui o texto completo a partir dos
chunks, e pede a um LLM que liste os tópicos/conceitos que o texto REALMENTE
cobre, comparando com as tags de documento inteiro já atribuídas (Tema/
Sefirah/Entidade). Documentos onde a cobertura real excede muito as tags
atuais são candidatos a divisão em arquivos menores e focados — o mesmo
padrão identificado manualmente em Klalei.txt (17 seções/tópicos distintos,
tags de documento inteiro insuficientes para capturar isso).

Não decide nada sozinho e não divide nenhum arquivo — produz um relatório
(JSON + texto) para o curador revisar. A Etapa 2 (proposta de divisão) é
ferramenta separada, aplicada só aos documentos sinalizados aqui como "alta".
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.openrouter_client import post_com_retry

CORPUS_JSON = Path(__file__).resolve().parent / "corpus_confirmado.json"
RELATORIO_JSON = Path(__file__).resolve().parent / "diagnostico_dispersao.json"

PROMPT = """Você vai analisar um documento completo do corpus de um projeto sobre \
Filosofia Chabad (Chassidut), organizado por Sefirot, Temas e Entidades.

TAGS JÁ ATRIBUÍDAS a este documento inteiro (nível documento, não chunk):
- Temas: {temas}
- Sefirot (DEFINE): {sefirot_define}
- Sefirot (EXPRESSA): {sefirot_expressa}
- Entidades: {entidades}

TEXTO COMPLETO DO DOCUMENTO:
{texto}

Tarefa:
1. Liste os tópicos/conceitos/assuntos DISTINTOS que o texto realmente aborda — como \
se você fosse escrever um sumário. Seja específico (não "educação" genérico, mas \
"diferença entre educar e ensinar", "autocrítica do educador", etc., quando for o caso).
2. Avalie: as tags já atribuídas acima cobrem razoavelmente essa lista, ou o documento \
trata de muito mais coisa do que as tags capturam?
3. Dê um veredito de dispersão: "baixa" (documento focado, tags já bastam), "media" \
(alguma amplitude, mas gerenciável), ou "alta" (muitos assuntos distintos, tags \
claramente insuficientes — candidato a ser dividido em documentos menores e focados).

Responda em JSON estrito, sem texto fora do JSON, no formato:
{{"topicos": ["...", "..."], "veredito": "baixa|media|alta", "justificativa": "1-2 frases"}}
"""


def _carregar_documentos() -> dict[str, dict]:
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    docs: dict[str, dict] = {}
    for c in corpus["chunks"]:
        doc = c["documento"]
        if doc not in docs:
            docs[doc] = {
                "chunks": [],
                "temas": set(),
                "sefirot_define": set(),
                "sefirot_expressa": set(),
                "entidades": set(),
            }
        docs[doc]["chunks"].append(c)
        docs[doc]["temas"].update(c["temas"] or [])
        docs[doc]["sefirot_define"].update(c["sefirot_define"] or [])
        docs[doc]["sefirot_expressa"].update(c["sefirot_expressa"] or [])
        docs[doc]["entidades"].update(c["entidades"] or [])
    for doc in docs.values():
        doc["chunks"].sort(key=lambda c: c["posicao"])
    return docs


def diagnosticar_documento(nome: str, dados: dict) -> dict:
    texto_completo = "\n\n".join(c["texto"] for c in dados["chunks"])
    prompt = PROMPT.format(
        temas=", ".join(sorted(dados["temas"])) or "(nenhum)",
        sefirot_define=", ".join(sorted(dados["sefirot_define"])) or "(nenhum)",
        sefirot_expressa=", ".join(sorted(dados["sefirot_expressa"])) or "(nenhum)",
        entidades=", ".join(sorted(dados["entidades"])) or "(nenhum)",
        texto=texto_completo,
    )
    resp = post_com_retry(
        "/chat/completions",
        # max_tokens generoso: o modelo usa parte do orçamento em "reasoning"
        # (pensamento estendido) antes do JSON final — documentos grandes
        # (Klalei.txt, 8592 palavras) esgotavam 1500 tokens no meio do JSON.
        {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
         "max_tokens": 4000, "temperature": 0},
        timeout=120,
    )
    escolha = resp.json()["choices"][0]
    conteudo = (escolha["message"]["content"] or "").strip()
    if not conteudo:
        return {
            "documento": nome, "topicos": [], "veredito": "erro",
            "justificativa": f"resposta vazia do LLM (finish_reason={escolha.get('finish_reason')})",
            "n_chunks": len(dados["chunks"]),
            "n_palavras": sum(len(c["texto"].split()) for c in dados["chunks"]),
            "tags_atuais": {
                "temas": sorted(dados["temas"]), "sefirot_define": sorted(dados["sefirot_define"]),
                "sefirot_expressa": sorted(dados["sefirot_expressa"]), "entidades": sorted(dados["entidades"]),
            },
        }
    conteudo = conteudo.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        resultado = json.loads(conteudo)
    except json.JSONDecodeError:
        resultado = {
            "topicos": [], "veredito": "erro",
            "justificativa": f"resposta do LLM não era JSON válido: {conteudo[:200]}",
        }
    resultado["documento"] = nome
    resultado["n_chunks"] = len(dados["chunks"])
    resultado["n_palavras"] = sum(len(c["texto"].split()) for c in dados["chunks"])
    resultado["tags_atuais"] = {
        "temas": sorted(dados["temas"]),
        "sefirot_define": sorted(dados["sefirot_define"]),
        "sefirot_expressa": sorted(dados["sefirot_expressa"]),
        "entidades": sorted(dados["entidades"]),
    }
    return resultado


ORDEM_VEREDITO = {"alta": 0, "media": 1, "baixa": 2, "erro": 3}


def rodar_diagnostico(apenas_documentos: list[str] | None = None) -> list[dict]:
    docs = _carregar_documentos()
    if apenas_documentos:
        docs = {k: v for k, v in docs.items() if k in apenas_documentos}
    resultados = []
    total = len(docs)
    for i, (nome, dados) in enumerate(docs.items(), 1):
        print(f"[{i}/{total}] {nome} ({len(dados['chunks'])} chunks, "
              f"{sum(len(c['texto'].split()) for c in dados['chunks'])} palavras)...")
        resultado = diagnosticar_documento(nome, dados)
        resultados.append(resultado)
        print(f"  -> veredito: {resultado['veredito']}")

    # Quando rodado só num subconjunto (apenas_documentos), MESCLA com o
    # relatório já existente em vez de sobrescrever — mesmo bug real já
    # cometido e corrigido em sugerir_tags.py (rodar escopado a 1 pasta
    # apagou os 106 resultados anteriores, só não houve perda porque o
    # commit anterior já tinha essa versão no git).
    if apenas_documentos and RELATORIO_JSON.exists():
        existentes = json.loads(RELATORIO_JSON.read_text(encoding="utf-8"))
        nomes_novos = {r["documento"] for r in resultados if "documento" in r}
        existentes = [r for r in existentes if r.get("documento") not in nomes_novos]
        resultados = existentes + resultados

    resultados.sort(key=lambda r: ORDEM_VEREDITO.get(r["veredito"], 4))
    RELATORIO_JSON.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultados


def _imprimir_relatorio(resultados: list[dict]) -> None:
    print()
    print("=" * 80)
    print(f"RELATÓRIO ({len(resultados)} documentos) — salvo em {RELATORIO_JSON}")
    contagem = {}
    for r in resultados:
        contagem[r["veredito"]] = contagem.get(r["veredito"], 0) + 1
    print(f"Resumo: {contagem}")
    print("=" * 80)
    for r in resultados:
        print(f"\n[{r['veredito'].upper()}] {r['documento']} "
              f"({r['n_chunks']} chunks, {r['n_palavras']} palavras)")
        print(f"  Tags atuais: Temas={r['tags_atuais']['temas']}, "
              f"Sefirot_DEFINE={r['tags_atuais']['sefirot_define']}, "
              f"Entidades={r['tags_atuais']['entidades']}")
        print(f"  Tópicos identificados: {r['topicos']}")
        print(f"  Justificativa: {r['justificativa']}")


if __name__ == "__main__":
    alvo = sys.argv[1:] if len(sys.argv) > 1 else None
    resultados = rodar_diagnostico(alvo)
    _imprimir_relatorio(resultados)
