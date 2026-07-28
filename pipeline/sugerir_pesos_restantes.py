"""Estende a curadoria de peso de conceitos estruturais (ver sugerir_tags.py,
seção 4.16/4.17 de 00_Estado_Atual.txt) aos 39 documentos que NÃO passaram
pela divisão (dispersão média/baixa) — só o eixo de peso, não Sefirah/Tema/
Entidade, que já existem e não são o alvo aqui.

Granularidade por DOCUMENTO INTEIRO (não por chunk) — consistente com como
Sefirah/Tema/Entidade já funcionam para estes 39 documentos (simplificação
já documentada no projeto), e mais defensável aqui do que era para os 13
divididos: estes têm dispersão média/baixa, ou seja, são coesos o
suficiente para uma pontuação por documento fazer sentido.

Mesmo padrão "IA sugere, curador confirma". Produz um relatório para
revisão — não grava em metadados_confirmados.py sozinho.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.openrouter_client import post_com_retry
from grafo.schema import CONCEITOS_ESTRUTURAIS
from pipeline.diagnostico_dispersao import _carregar_documentos
from pipeline.metadados_confirmados import DOCUMENTOS

RELATORIO_JSON = Path(__file__).resolve().parent / "pesos_documentos_restantes.json"

_CONCEITOS_LISTA = "\n".join(f"  - {c['nome']}: {c['definicao']}" for c in CONCEITOS_ESTRUTURAIS)

PROMPT = """Você vai avaliar um documento completo do corpus de um projeto sobre \
Filosofia Chabad (Chassidut), para um eixo específico: conceitos estruturais centrais \
do projeto que frequentemente aparecem no texto SEM usar o termo literal.

TÍTULO/DOCUMENTO: {documento}

TEXTO COMPLETO:
{texto}

CONCEITOS ESTRUTURAIS A AVALIAR:
{conceitos_lista}

Tarefa: para CADA conceito da lista, dê um peso de 0 a 5 (0 = não relacionado, 5 = o \
documento expressa centralmente esse conceito, mesmo sem usar o termo literal do \
projeto) + justificativa curta. Avalie o documento como um todo — se o conceito \
aparece só numa parte pequena e não é central ao documento, isso deve se refletir num \
peso mais baixo, não em 5.

Responda em JSON estrito, sem texto fora do JSON:
{{"conceitos_estruturais": [{{"conceito": "...", "peso": N, "justificativa": "..."}}]}}
"""


def _documentos_restantes() -> list[dict]:
    return [d for d in DOCUMENTOS if not d["pasta"].startswith("Divididos/")]


def sugerir_pesos_documento(nome_documento: str, dados: dict) -> dict:
    texto_completo = "\n\n".join(c["texto"] for c in dados["chunks"])
    prompt = PROMPT.format(
        documento=nome_documento, texto=texto_completo, conceitos_lista=_CONCEITOS_LISTA,
    )

    ultimo_erro = None
    for _tentativa in range(1, 3 + 1):
        resp = post_com_retry(
            "/chat/completions",
            {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": 3000, "temperature": 0},
            timeout=120,
        )
        escolha = resp.json()["choices"][0]
        conteudo = (escolha["message"]["content"] or "").strip()
        if not conteudo or escolha.get("finish_reason") == "length":
            ultimo_erro = f"resposta vazia/truncada (finish_reason={escolha.get('finish_reason')})"
            continue
        conteudo = conteudo.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            resultado = json.loads(conteudo)
        except json.JSONDecodeError as e:
            ultimo_erro = f"JSON inválido: {e}"
            continue
        resultado["documento"] = nome_documento
        return resultado

    return {"documento": nome_documento, "erro": ultimo_erro}


def rodar(apenas_documentos: list[str] | None = None) -> list[dict]:
    docs_restantes = {d["pasta"] + "|" + d["chave"] for d in _documentos_restantes()}
    todos_docs = _carregar_documentos()

    # mapeia nome de arquivo real -> (pasta, chave) para saber quais chunks
    # pertencem aos 39 documentos restantes
    from pipeline.gerar_corpus import resolver_arquivo
    nome_para_chave = {}
    for d in _documentos_restantes():
        try:
            caminho = resolver_arquivo(d["pasta"], d["chave"])
        except (FileNotFoundError, ValueError):
            continue
        nome_para_chave[caminho.name] = d

    alvos = list(nome_para_chave.keys())
    if apenas_documentos:
        alvos = [a for a in alvos if a in apenas_documentos]

    resultados = []
    total = len(alvos)
    for i, nome in enumerate(alvos, 1):
        dados = todos_docs[nome]
        print(f"[{i}/{total}] {nome} ({len(dados['chunks'])} chunks)...")
        resultado = sugerir_pesos_documento(nome, dados)
        resultados.append(resultado)
        if "erro" in resultado:
            print(f"  -> ERRO: {resultado['erro']}")
        else:
            pesos = {c["conceito"]: c["peso"] for c in resultado["conceitos_estruturais"]}
            print(f"  -> {pesos}")

    # Mescla com o relatório existente quando escopado a um subconjunto —
    # mesmo bug real já cometido e corrigido em sugerir_tags.py e
    # diagnostico_dispersao.py.
    if apenas_documentos and RELATORIO_JSON.exists():
        existentes = json.loads(RELATORIO_JSON.read_text(encoding="utf-8"))
        nomes_novos = {r["documento"] for r in resultados if "documento" in r}
        existentes = [r for r in existentes if r.get("documento") not in nomes_novos]
        resultados = existentes + resultados

    RELATORIO_JSON.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultados


if __name__ == "__main__":
    alvo = sys.argv[1:] if len(sys.argv) > 1 else None
    resultados = rodar(alvo)
    erros = [r for r in resultados if "erro" in r]
    print(f"\n{len(resultados)} documentos processados, {len(erros)} com erro.")
    print(f"Relatório salvo em {RELATORIO_JSON}")
