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
from backend.gerar_resposta import gerar_resposta_stream

st.set_page_config(page_title="Mashpia", page_icon="✡", layout="wide")


@st.cache_resource
def _garantir_indice() -> None:
    """No Streamlit Community Cloud o container sobe do zero a cada deploy —
    data/chroma/ (gitignored, nunca commitado) não existe lá. Reconstrói o
    índice a partir do corpus_confirmado.json (esse sim commitado) se ele
    estiver ausente ou desatualizado. Local, com o índice já pronto, isso é
    só uma checagem rápida (contagem bate, não refaz nada). `st.cache_resource`
    garante que isso roda uma vez por processo, não a cada pergunta."""
    import json

    import chromadb

    from config import CHROMA_DIR
    from pipeline.vetorizar import CORPUS_JSON, NOME_COLECAO, popular_chromadb

    esperado = len(json.loads(CORPUS_JSON.read_text(encoding="utf-8"))["chunks"])
    cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        colecao = cliente.get_collection(NOME_COLECAO)
        if colecao.count() == esperado:
            return
    except Exception:
        pass
    popular_chromadb()


with st.spinner("Preparando a base de conhecimento…"):
    _garantir_indice()

AVISO_PARAGRAFOS = [
    "Chat baseado na Filosofia Chabad. Respostas segundo o conceito de Sefirot.",
    "A Filosofia Chassídica Chabad é parte integrante da Torá, em cujo paradigma o Espiritual "
    "domina, e dá Forma, ao Material.",
    "A Mente, que é regida pelo Espiritual, é a origem do Pensamento. Pensamento é o início da "
    "ação. A Mente dirige os Sentimentos.",
    "Quanto mais se entende a essência, melhor se resolve o problema.",
]
AVISO_HTML = "".join(f"<p style='margin-bottom:0.6em;'>{p}</p>" for p in AVISO_PARAGRAFOS)

# Reduz o espaço em branco padrão do Streamlit no topo da sidebar (reservado
# originalmente para o ícone de recolher) e o espaçamento dos divisores —
# pedido explícito de subir todo o conteúdo, aproximando-o do topo.
ESPACAMENTO_CSS = """
<style>
section[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
section[data-testid="stSidebar"] hr { margin: 0.5rem 0; }
</style>
"""

# Uma cor por caixa, para distinguir os 5 blocos visualmente. Também reduz o
# padding padrão do st.container(border=True) (que é generoso demais, ~1rem)
# e o espaçamento vertical entre blocos dentro do grupo — pedido explícito de
# aproximar as caixas.
CAIXAS_CSS = """
<style>
div.st-key-grupo_feedback [data-testid="stVerticalBlock"] { gap: 0.4rem; }

div.st-key-caixa_titulo {
    border: 2px solid #B08D57 !important; border-radius: 8px;
    background-color: rgba(176, 141, 87, 0.10); padding: 0.3rem 0.6rem;
}
div.st-key-caixa_avaliacao {
    border: 2px solid #6B8E9E !important; border-radius: 8px;
    background-color: rgba(107, 142, 158, 0.10); padding: 0.3rem 0.6rem;
}
div.st-key-caixa_sugestao {
    border: 2px solid #8E6B9E !important; border-radius: 8px;
    background-color: rgba(142, 107, 158, 0.10); padding: 0.3rem 0.6rem;
}
div.st-key-caixa_enviar {
    border: 2px solid #6B9E7A !important; border-radius: 8px;
    background-color: rgba(107, 158, 122, 0.10); padding: 0.3rem 0.6rem;
}
div.st-key-caixa_limpar {
    border: 2px solid #9E6B6B !important; border-radius: 8px;
    background-color: rgba(158, 107, 107, 0.10); padding: 0.3rem 0.6rem;
}
</style>
"""

with st.sidebar:
    st.markdown(ESPACAMENTO_CSS, unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.8rem; line-height:1.35;'>{AVISO_HTML}</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(CAIXAS_CSS, unsafe_allow_html=True)
    with st.container(key="grupo_feedback"):
        with st.container(border=True, key="caixa_titulo"):
            st.subheader("Sua opinião importa")

        with st.container(border=True, key="caixa_avaliacao"):
            avaliacao = st.radio(
                "Avaliação geral", ["Muito boa", "Boa", "Regular", "Ruim"],
                index=None, key="avaliacao_input",
            )

        with st.container(border=True, key="caixa_sugestao"):
            sugestao = st.text_area("Sugestões ou comentários", key="sugestao_input")

        with st.container(border=True, key="caixa_enviar"):
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

        with st.container(border=True, key="caixa_limpar"):
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
        with st.spinner("Consultando as Sefirot..."):
            classificacao, chunks_usados, relacoes_estruturais, gerador = gerar_resposta_stream(pergunta)
        # A partir daqui o texto vai aparecendo progressivamente (streaming),
        # em vez de ficar em silêncio pelos ~20s+ que a geração completa leva.
        resposta_texto = st.write_stream(gerador)
        with st.expander("Classificação e fontes"):
            st.write(f"**Lacuna:** {classificacao['protocolo_lacuna']}")
            st.write(f"**Sefirot:** {', '.join(classificacao['sefirot']) or '—'}")
            st.write(f"**Entidades:** {', '.join(classificacao['entidades']) or '—'}")
            st.write(f"**Temas:** {', '.join(classificacao['temas']) or '—'}")
            st.write(f"**Justificativa:** {classificacao['justificativa']}")
            _exibir_relacoes(relacoes_estruturais)
            if chunks_usados:
                st.write("**Trechos consultados:**")
                for chunk in chunks_usados:
                    st.markdown(f"- {chunk['texto'][:150]}…")
    st.session_state.historico.append({
        "pergunta": pergunta,
        "resposta": resposta_texto,
        "classificacao": classificacao,
        "chunks_usados": chunks_usados,
        "relacoes_estruturais": relacoes_estruturais,
    })
