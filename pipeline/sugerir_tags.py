"""Sugestão automática de tags — passos 4 (Sefirah/Tema/Entidade) e 5 (peso de
conceitos estruturais) do fluxo planejado em 00_Estado_Atual.txt, aplicados
aos arquivos gerados pela Etapa 2 (pipeline/propor_divisao.py).

Mesmo padrão "IA sugere, curador confirma" já usado desde o início do
projeto para classificar Sefirah/Tema por documento. Produz um relatório
(JSON) para revisão — não grava nada em metadados_confirmados.py sozinho, e
não decide `autoria`, que é herdada automaticamente do documento original
(dividir um texto não muda quem o escreveu).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LLM_MODEL
from backend.openrouter_client import post_com_retry
from grafo.schema import CONCEITOS_ESTRUTURAIS, ENTIDADES, SEFIROT_E_NOS_PONTE, TEMAS
from pipeline.metadados_confirmados import DOCUMENTOS

PASTA_DIVIDIDOS = Path("/home/m/GraphRAG/CHAT_NIVEL_2/Divididos")
RELATORIO_JSON = Path(__file__).resolve().parent / "sugestao_tags.json"

_SEFIROT_LISTA = ", ".join(SEFIROT_E_NOS_PONTE)
_ENTIDADES_LISTA = "\n".join(f"  - {e['nome']} (tipo: {e['tipo']})" for e in ENTIDADES)
_TEMAS_LISTA = ", ".join(TEMAS)
_CONCEITOS_LISTA = "\n".join(f"  - {c['nome']}: {c['definicao']}" for c in CONCEITOS_ESTRUTURAIS)
_NOME_PARA_ID_ENTIDADE = {e["nome"]: e["id"] for e in ENTIDADES}

PROMPT = """Você vai classificar um trecho do corpus de um projeto sobre Filosofia \
Chabad (Chassidut), organizado por Sefirot/Temas/Entidades/Conceitos Estruturais.

TÍTULO DO TRECHO: {titulo}

TEXTO:
{texto}

LISTAS VÁLIDAS (use só valores exatos destas listas, nunca invente um novo):
- Sefirot: {sefirot_lista}
- Temas: {temas_lista}
- Entidades:
{entidades_lista}
- Conceitos estruturais:
{conceitos_lista}

Tarefa — classifique este trecho:
1. sefirot_define: quais Sefirot da lista este texto DEFINE (explica o que ela É), \
se houver. Vazio se nenhuma.
2. sefirot_expressa: quais Sefirot da lista este texto EXPRESSA/aplica (exemplo \
prático, sem necessariamente defini-la), se houver. Vazio se nenhuma.
3. temas: seja seletivo — inclua só os Temas CENTRAIS ao trecho, não qualquer um com \
relação remota ou tangencial. Prefira 1 tema bem escolhido a vários; "Fundamentos" e \
"Proposito" em especial só devem ser usados quando o trecho for GENUINAMENTE sobre \
conceitos fundacionais (EinSof, Tzimtzum, Sefirot em si) ou o propósito da Criação como \
tema central — não porque todo ensinamento chassídico toca nisso em algum grau. Pode \
ser vazio se genuinamente nenhum tema central se aplicar.
4. entidades: quais Entidades da lista são mencionadas de fato no texto (nome exato \
da lista, não o id).
5. conceitos_estruturais: para CADA conceito da lista, um peso de 0 a 5 (0 = não \
relacionado, 5 = o texto expressa centralmente esse conceito, mesmo sem usar o termo \
literal do projeto) + justificativa curta.
6. observacoes: uma frase resumindo o foco do trecho, no mesmo espírito das \
observações já usadas no projeto.

Responda em JSON estrito, sem texto fora do JSON:
{{"sefirot_define": [...], "sefirot_expressa": [...], "temas": [...], "entidades": [...], \
"conceitos_estruturais": [{{"conceito": "...", "peso": N, "justificativa": "..."}}], \
"observacoes": "..."}}
"""


def _mapa_autoria_por_documento_original() -> dict[str, str]:
    from pipeline.gerar_corpus import resolver_arquivo
    mapa = {}
    for doc in DOCUMENTOS:
        try:
            caminho = resolver_arquivo(doc["pasta"], doc["chave"])
        except (FileNotFoundError, ValueError):
            continue
        mapa[caminho.name] = doc["autoria"]
    return mapa


def _listar_arquivos_divididos() -> list[Path]:
    return sorted(PASTA_DIVIDIDOS.glob("*/*.txt"))


def sugerir_tags_arquivo(caminho: Path) -> dict:
    texto_completo = caminho.read_text(encoding="utf-8")
    titulo, _, corpo = texto_completo.partition("\n\n")
    prompt = PROMPT.format(
        titulo=titulo.strip(), texto=corpo.strip() or texto_completo,
        sefirot_lista=_SEFIROT_LISTA, temas_lista=_TEMAS_LISTA,
        entidades_lista=_ENTIDADES_LISTA, conceitos_lista=_CONCEITOS_LISTA,
    )

    ultimo_erro = None
    for _tentativa in range(1, 3 + 1):
        resp = post_com_retry(
            "/chat/completions",
            {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": 4000, "temperature": 0},
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
        break
    else:
        return {"erro": ultimo_erro, "arquivo": str(caminho)}

    # normaliza nomes de Entidade -> id (formato usado em metadados_confirmados.py)
    resultado["entidades"] = [
        _NOME_PARA_ID_ENTIDADE.get(nome, nome) for nome in resultado.get("entidades", [])
    ]
    resultado["arquivo"] = str(caminho.relative_to(PASTA_DIVIDIDOS))
    resultado["titulo"] = titulo.strip()
    return resultado


def rodar(apenas_pastas: list[str] | None = None) -> list[dict]:
    arquivos = _listar_arquivos_divididos()
    if apenas_pastas:
        arquivos = [a for a in arquivos if a.parent.name in apenas_pastas]
    autoria_por_original = _mapa_autoria_por_documento_original()

    resultados = []
    total = len(arquivos)
    for i, caminho in enumerate(arquivos, 1):
        pasta = caminho.parent
        proposta_path = pasta / "_proposta.json"
        doc_original = None
        if proposta_path.exists():
            doc_original = json.loads(proposta_path.read_text(encoding="utf-8")).get("documento_original")
        autoria = autoria_por_original.get(doc_original, "fonte_externa")

        print(f"[{i}/{total}] {caminho.relative_to(PASTA_DIVIDIDOS)}...")
        resultado = sugerir_tags_arquivo(caminho)
        resultado["documento_original"] = doc_original
        resultado["autoria"] = autoria
        resultado["pasta_relativa"] = f"Divididos/{pasta.name}"
        resultados.append(resultado)
        if "erro" in resultado:
            print(f"  -> ERRO: {resultado['erro']}")
        else:
            print(f"  -> temas={resultado['temas']}, sefirot_define={resultado['sefirot_define']}")

    RELATORIO_JSON.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultados


if __name__ == "__main__":
    alvo = sys.argv[1:] if len(sys.argv) > 1 else None
    resultados = rodar(alvo)
    erros = [r for r in resultados if "erro" in r]
    print(f"\n{len(resultados)} arquivos processados, {len(erros)} com erro.")
    print(f"Relatório salvo em {RELATORIO_JSON}")
