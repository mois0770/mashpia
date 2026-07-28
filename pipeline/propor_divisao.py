"""Proposta de divisão — Etapa 2 do fluxo planejado em 00_Estado_Atual.txt
("Como incluir textos novos no corpus", fluxo planejado 2026-07-28).

Só roda nos documentos sinalizados como "alta" pelo diagnóstico de dispersão
(pipeline/diagnostico_dispersao.py). Para cada um, propõe uma partição dos
chunks existentes (na ordem em que já aparecem no documento, por `posicao`)
em grupos contíguos, cada um virando um arquivo novo e focado.

Fidelidade é inegociável aqui: o LLM só decide ONDE cortar (juízo editorial),
nunca reescreve o texto — a montagem de cada arquivo novo é feita pelo
próprio script, concatenando o texto ORIGINAL dos chunks do grupo, verbatim.
Nada é gravado no corpus nem no pipeline de metadados; os arquivos propostos
vão para uma pasta de revisão, para o curador (usuário) aprovar antes de
qualquer coisa entrar de fato no fluxo de curadoria.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.openrouter_client import post_com_retry
from pipeline.diagnostico_dispersao import RELATORIO_JSON, _carregar_documentos

PASTA_REVISAO = Path(__file__).resolve().parent / "propostas_divisao"

PROMPT = """Você vai propor como dividir um documento longo do corpus de um projeto \
sobre Filosofia Chabad (Chassidut) em vários arquivos menores e focados — um por \
tópico/conceito coeso — para que cada arquivo resultante possa receber tags precisas \
de Sefirah/Tema/Entidade (hoje o documento inteiro tem só estas tags, insuficientes \
para a amplitude real do conteúdo): {tags_atuais}

O documento já está dividido em {n_chunks} trechos numerados de 0 a {ultimo_indice}, \
na ordem original do texto. Cada trecho aparece abaixo como "[N] texto".

{texto_numerado}

Tarefa: proponha uma partição desses {n_chunks} trechos em grupos CONTÍGUOS (sem \
pular nem repetir nenhum índice, cobrindo de 0 até {ultimo_indice} por completo) — \
cada grupo deve ser um bloco temático coeso, idealmente virando um arquivo de \
400 a 900 palavras (grupos de 1 trecho só são aceitáveis se o trecho já for \
substancial e autônomo). Dê um título específico e uma justificativa curta pra \
cada grupo.

Responda em JSON estrito, sem texto fora do JSON, no formato:
{{"grupos": [{{"titulo": "...", "inicio": 0, "fim": 5, "justificativa": "..."}}, ...]}}
onde "inicio" e "fim" são índices INCLUSIVOS de trecho.
"""


def _slug(texto: str) -> str:
    import re
    texto = texto.strip().lower()
    texto = re.sub(r"[^a-z0-9áàâãéêíóôõúüç\s-]", "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto[:60].strip("_")


def _validar_particao(grupos: list[dict], n_chunks: int) -> list[str]:
    erros = []
    cobertos = set()
    for g in grupos:
        if not isinstance(g.get("inicio"), int) or not isinstance(g.get("fim"), int):
            erros.append(f"grupo '{g.get('titulo')}' sem inicio/fim inteiros")
            continue
        if g["inicio"] > g["fim"]:
            erros.append(f"grupo '{g['titulo']}': inicio > fim")
            continue
        faixa = set(range(g["inicio"], g["fim"] + 1))
        sobreposto = faixa & cobertos
        if sobreposto:
            erros.append(f"grupo '{g['titulo']}': sobrepõe índices {sorted(sobreposto)}")
        cobertos |= faixa
    faltando = set(range(n_chunks)) - cobertos
    if faltando:
        erros.append(f"índices não cobertos por nenhum grupo: {sorted(faltando)}")
    return erros


def propor_divisao(nome_documento: str) -> dict:
    docs = _carregar_documentos()
    if nome_documento not in docs:
        raise ValueError(f"documento não encontrado no corpus: {nome_documento}")
    dados = docs[nome_documento]
    chunks = dados["chunks"]
    n_chunks = len(chunks)

    texto_numerado = "\n\n".join(f"[{i}] {c['texto']}" for i, c in enumerate(chunks))
    tags_atuais = (
        f"Temas={sorted(dados['temas'])}, Sefirot_DEFINE={sorted(dados['sefirot_define'])}, "
        f"Sefirot_EXPRESSA={sorted(dados['sefirot_expressa'])}, Entidades={sorted(dados['entidades'])}"
    )
    prompt = PROMPT.format(
        tags_atuais=tags_atuais, n_chunks=n_chunks, ultimo_indice=n_chunks - 1,
        texto_numerado=texto_numerado,
    )

    # O modelo gasta uma quantidade variável de "reasoning tokens" antes do
    # JSON final (630 numa rodada, o suficiente para truncar o JSON no meio
    # noutra, com o mesmo documento) — não dá pra prever, então tentamos de
    # novo em vez de só falhar na primeira resposta cortada.
    ultimo_erro = None
    for tentativa in range(1, 3 + 1):
        resp = post_com_retry(
            "/chat/completions",
            {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": 12000, "temperature": 0},
            timeout=240,
        )
        escolha = resp.json()["choices"][0]
        conteudo = (escolha["message"]["content"] or "").strip()
        if not conteudo:
            ultimo_erro = f"resposta vazia (finish_reason={escolha.get('finish_reason')})"
            continue
        if escolha.get("finish_reason") == "length":
            ultimo_erro = "resposta truncada (finish_reason=length, provável estouro de reasoning tokens)"
            continue
        conteudo_limpo = conteudo.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            proposta = json.loads(conteudo_limpo)
        except json.JSONDecodeError as e:
            ultimo_erro = f"JSON inválido: {e}"
            continue
        break
    else:
        raise RuntimeError(f"falhou após {tentativa} tentativas para '{nome_documento}': {ultimo_erro}")

    grupos = proposta["grupos"]

    erros = _validar_particao(grupos, n_chunks)
    if erros:
        raise ValueError(f"partição inválida proposta pelo LLM para '{nome_documento}':\n" + "\n".join(erros))

    pasta_doc = PASTA_REVISAO / _slug(Path(nome_documento).stem)
    pasta_doc.mkdir(parents=True, exist_ok=True)

    resumo = []
    for i, g in enumerate(grupos, 1):
        texto_grupo = "\n\n".join(chunks[j]["texto"] for j in range(g["inicio"], g["fim"] + 1))
        n_palavras = len(texto_grupo.split())
        nome_arquivo = f"{i:02d}_{_slug(g['titulo'])}.txt"
        (pasta_doc / nome_arquivo).write_text(
            f"{g['titulo']}\n\n{texto_grupo}\n", encoding="utf-8"
        )
        resumo.append({
            "arquivo": nome_arquivo, "titulo": g["titulo"],
            "trechos": f"{g['inicio']}-{g['fim']}", "n_palavras": n_palavras,
            "justificativa": g["justificativa"],
        })

    (pasta_doc / "_proposta.json").write_text(
        json.dumps({"documento_original": nome_documento, "grupos": resumo}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"documento_original": nome_documento, "pasta": str(pasta_doc), "grupos": resumo}


def _imprimir(resultado: dict) -> None:
    print(f"\n{'=' * 80}")
    print(f"'{resultado['documento_original']}' -> {len(resultado['grupos'])} arquivos propostos")
    print(f"Pasta: {resultado['pasta']}")
    print("=" * 80)
    for g in resultado["grupos"]:
        print(f"\n[{g['arquivo']}] ({g['n_palavras']} palavras, trechos {g['trechos']})")
        print(f"  Título: {g['titulo']}")
        print(f"  Justificativa: {g['justificativa']}")


if __name__ == "__main__":
    alvos = sys.argv[1:]
    if not alvos:
        relatorio = json.loads(RELATORIO_JSON.read_text(encoding="utf-8"))
        alvos = [r["documento"] for r in relatorio if r["veredito"] == "alta"]
        print(f"Nenhum documento passado — usando os {len(alvos)} sinalizados como 'alta'.")
    for nome in alvos:
        print(f"\nProcessando: {nome}...")
        resultado = propor_divisao(nome)
        _imprimir(resultado)
