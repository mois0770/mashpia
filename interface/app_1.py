"""Interface Streamlit do Mashpia. Rodar com:
    streamlit run interface/app.py

Chama as funções do backend diretamente (não passa pela API FastAPI) — mais
simples de rodar localmente, um processo só. Se quiser testar o caminho real
via HTTP, dá pra trocar por chamadas requests ao servidor uvicorn depois.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.feedback import salvar_feedback
from backend.gerar_resposta import NIVEIS, gerar_resposta
from backend.limites import MAX_PERGUNTAS_POR_SESSAO, TetoDeCustoAtingido
from backend.openrouter_client import ErroOpenRouter

st.set_page_config(page_title="Mashpia", page_icon="✡", layout="wide")

# Ordenado por número de nível (1, 2, 3) para o radio aparecer nessa ordem.
NIVEL_NOMES_PARA_NUMERO = {v["nome"]: k for k, v in sorted(NIVEIS.items())}

AVISO_PARAGRAFOS = [
    "Chat baseado na Filosofia Chabad. Respostas segundo o conceito de Sefirot.",
    "A Filosofia Chassídica Chabad é parte integrante da Torá, em cujo paradigma o Espiritual "
    "domina, e dá Forma, ao Material.",
    "A Mente, que é regida pelo Espiritual, é a origem do Pensamento. Pensamento é o início da "
    "ação. A Mente dirige os Sentimentos.",
]
AVISO_HTML = "".join(f"<p style='margin-bottom:0.6em;'>{p}</p>" for p in AVISO_PARAGRAFOS)

CAIXA_FEEDBACK_CSS = """
<style>
div.st-key-caixa_feedback {
    border: 2px solid #B08D57 !important;
    border-radius: 10px;
    background-color: rgba(176, 141, 87, 0.08);
    padding: 0.6rem 0.8rem;
}
div.st-key-caixa_nivel {
    border: 2px solid #4A7A8C !important;
    border-radius: 10px;
    background-color: rgba(74, 122, 140, 0.08);
    padding: 0.6rem 0.8rem;
}
</style>
"""

with st.sidebar:
    st.markdown(
        f"<div style='font-size:0.8rem; line-height:1.35;'>{AVISO_HTML}</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(CAIXA_FEEDBACK_CSS, unsafe_allow_html=True)

    with st.container(border=True, key="caixa_nivel"):
        st.subheader("Nível de resposta")
        nivel_nome = st.radio(
            "Escolha antes de perguntar",
            list(NIVEL_NOMES_PARA_NUMERO.keys()),
            index=0, key="nivel_input",
        )
    nivel = NIVEL_NOMES_PARA_NUMERO[nivel_nome]

    st.divider()
    with st.container(border=True, key="caixa_feedback"):
        st.subheader("Sua opinião importa")
        st.caption("Este chat está em desenvolvimento — avalie e deixe sugestões.")
        avaliacao = st.radio(
            "Avaliação geral", ["Muito boa", "Boa", "Regular", "Ruim"],
            index=None, key="avaliacao_input",
        )
        sugestao = st.text_area("Sugestões ou comentários", key="sugestao_input")
        if st.button("Enviar feedback"):
            if avaliacao or sugestao:
                ultimo = st.session_state.get("historico", [])
                ultimo = ultimo[-1] if ultimo else None
                salvar_feedback(
                    avaliacao=avaliacao or "(não informada)",
                    sugestao=sugestao,
                    pergunta=ultimo["pergunta"] if ultimo else None,
                    resposta=ultimo["resposta"] if ultimo else None,
                )
                st.success("Obrigado! Seu feedback foi registrado.")
            else:
                st.warning("Preencha ao menos a avaliação ou a sugestão antes de enviar.")

        st.divider()
        if st.button("Limpar conversa"):
            st.session_state.historico = []
            st.rerun()

st.title("Mashpia")
st.caption("Pergunte algo à luz da Filosofia Chabad.")

if "historico" not in st.session_state:
    st.session_state.historico = []

def _exibir_relacoes(relacoes: dict) -> None:
    linhas = []
    for s in relacoes["sinteses"]:
        a, b = s["par"]
        linhas.append(f"- {a} + {b} → **{s['destino']}** (SINTETIZA)")
    for c in relacoes["canais"]:
        linhas.append(f"- {c['origem']} → {c['destino']} (CANALIZA)")
    for g in relacoes["governancas"]:
        linhas.append(f"- {g['origem']} governa {g['destino']} (GOVERNA)")
    if linhas:
        st.write("**Relações estruturais do grafo:**")
        st.markdown("\n".join(linhas))


for turno in st.session_state.historico:
    with st.chat_message("user"):
        st.markdown(turno["pergunta"])
    with st.chat_message("assistant"):
        st.markdown(turno["resposta"])
        with st.expander("Classificação e fontes"):
            c = turno["classificacao"]
            st.write(f"**Nível de resposta:** {turno['nivel_nome']}")
            st.write(f"**Lacuna:** {c['protocolo_lacuna']}")
            st.write(f"**Sefirot:** {', '.join(c['sefirot']) or '—'}")
            st.write(f"**Entidades:** {', '.join(c['entidades']) or '—'}")
            st.write(f"**Temas:** {', '.join(c['temas']) or '—'}")
            st.write(f"**Justificativa:** {c['justificativa']}")
            _exibir_relacoes(turno["relacoes_estruturais"])
            if turno["chunks_usados"]:
                st.write("**Trechos consultados:**")
                for chunk in turno["chunks_usados"]:
                    st.markdown(f"- {chunk['texto'][:150]}…")

pergunta = st.chat_input("Sua pergunta...")
if pergunta:
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        if st.session_state.get("perguntas_nesta_sessao", 0) >= MAX_PERGUNTAS_POR_SESSAO:
            st.error(
                f"Você atingiu o limite de {MAX_PERGUNTAS_POR_SESSAO} perguntas nesta "
                "sessão. Recarregue a página para começar uma nova sessão."
            )
            st.stop()
        st.session_state["perguntas_nesta_sessao"] = st.session_state.get("perguntas_nesta_sessao", 0) + 1
        try:
            with st.spinner("Consultando as Sefirot..."):
                resultado = gerar_resposta(pergunta, nivel=nivel)
            resultado["nivel_nome"] = nivel_nome
            st.markdown(resultado["resposta"])
            with st.expander("Classificação e fontes"):
                c = resultado["classificacao"]
                st.write(f"**Nível de resposta:** {nivel_nome}")
                st.write(f"**Lacuna:** {c['protocolo_lacuna']}")
                st.write(f"**Sefirot:** {', '.join(c['sefirot']) or '—'}")
                st.write(f"**Entidades:** {', '.join(c['entidades']) or '—'}")
                st.write(f"**Temas:** {', '.join(c['temas']) or '—'}")
                st.write(f"**Justificativa:** {c['justificativa']}")
                _exibir_relacoes(resultado["relacoes_estruturais"])
                if resultado["chunks_usados"]:
                    st.write("**Trechos consultados:**")
                    for chunk in resultado["chunks_usados"]:
                        st.markdown(f"- {chunk['texto'][:150]}…")
        except TetoDeCustoAtingido as e:
            st.error(str(e))
            st.stop()
        except ErroOpenRouter as e:
            st.error(f"Não consegui gerar uma resposta agora: {e}")
            st.stop()
    st.session_state.historico.append(resultado)
