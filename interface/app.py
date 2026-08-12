"""Interface Streamlit do Mashpia. Rodar com:
    streamlit run interface/app.py

Chama as funções do backend diretamente (não passa pela API FastAPI) — mais
simples de rodar localmente, um processo só. Se quiser testar o caminho real
via HTTP, dá pra trocar por chamadas requests ao servidor uvicorn depois.
"""

import sys
from pathlib import Path

import sentry_sdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.cadastro import CadastroIndisponivel, UsuarioJaExiste, criar_conta, verificar_login
from backend.feedback import salvar_feedback
from backend.gerar_resposta import NIVEIS, gerar_resposta_stream
from backend.limites import (
    MAX_PERGUNTAS_POR_USUARIO_DIA,
    LimiteDiarioAtingido,
    TetoDeCustoAtingido,
    perguntas_hoje,
    registrar_pergunta,
    verificar_limite_diario,
)
from backend.openrouter_client import ErroOpenRouter
from config import get_sentry_dsn

# Monitoramento de erro (2026-08-11) — sem isso, uma falha em produção só
# aparece se alguém reclamar. Sem SENTRY_DSN configurado, não inicializa
# (não trava uso local sem conta no Sentry). traces_sample_rate=0 porque só
# queremos captura de erro, não rastreamento de performance (economiza cota
# do tier grátis, 5.000 eventos/mês).
_sentry_dsn = get_sentry_dsn()
if _sentry_dsn:
    sentry_sdk.init(dsn=_sentry_dsn, traces_sample_rate=0.0, send_default_pii=False)

st.set_page_config(page_title="Mashpia", page_icon="✡", layout="wide")

_BASE_DIR = Path(__file__).resolve().parent.parent
TERMOS_PATH = _BASE_DIR / "Termos_de_Uso.txt"
POLITICA_PATH = _BASE_DIR / "Politica_de_Privacidade.txt"


def _verificar_senha() -> bool:
    """Gate de acesso — duas origens de conta:
    1. Manual, via [usuarios] nos Secrets (eu edito por assinante, senha em
       texto puro — aceitável só pra um punhado de contas).
    2. Self-service (2026-08-11, fase de teste), via backend/cadastro.py —
       conta no Supabase com senha com hash (bcrypt), qualquer um cria
       sozinho pela aba "Criar conta". Ainda sem cobrança associada: toda
       conta nova já entra ativa, só pra validar o mecanismo.

    Nos dois casos, MAX_PERGUNTAS_POR_USUARIO_DIA passa a valer por
    usuario_id de verdade, não só por sessão de navegador (bypassável
    recarregando a página).
    """
    if st.session_state.get("usuario_id"):
        return True

    st.title("Mashpia")

    aba_entrar, aba_criar = st.tabs(["Entrar", "Criar conta (teste)"])

    with aba_entrar:
        st.caption("Acesso restrito — informe suas credenciais para continuar.")
        usuario_id_input = st.text_input("Usuário", key="login_usuario_input")
        senha = st.text_input("Senha", type="password", key="login_senha_input")
        if st.button("Entrar"):
            usuarios_manuais = st.secrets.get("usuarios", {})
            if usuarios_manuais.get(usuario_id_input) == senha or verificar_login(usuario_id_input, senha):
                st.session_state["usuario_id"] = usuario_id_input
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    with aba_criar:
        st.caption(
            "Cadastro de teste — cria uma conta nova, sem cobrança associada ainda "
            "(fase de validação do mecanismo)."
        )
        with st.expander("Termos de Uso"):
            st.text(TERMOS_PATH.read_text(encoding="utf-8"))
        with st.expander("Política de Privacidade"):
            st.text(POLITICA_PATH.read_text(encoding="utf-8"))
        concorda = st.checkbox(
            "Li e concordo com os Termos de Uso e a Política de Privacidade",
            key="concorda_termos_input",
        )
        novo_id = st.text_input("Escolha um nome de usuário", key="cadastro_usuario_input")
        nova_senha = st.text_input("Escolha uma senha", type="password", key="cadastro_senha_input")
        confirmar = st.text_input("Confirme a senha", type="password", key="cadastro_confirmar_input")
        if st.button("Criar conta"):
            if not concorda:
                st.error("É necessário concordar com os Termos de Uso e a Política de Privacidade.")
            elif not novo_id or not nova_senha:
                st.error("Preencha usuário e senha.")
            elif nova_senha != confirmar:
                st.error("As senhas não coincidem.")
            else:
                try:
                    criar_conta(novo_id, nova_senha)
                    st.success('Conta criada! Use a aba "Entrar" com as credenciais que você escolheu.')
                except (UsuarioJaExiste, CadastroIndisponivel) as e:
                    st.error(str(e))

    return False


if not _verificar_senha():
    st.stop()

usuario_id = st.session_state["usuario_id"]

# Ordenado por número de nível (1, 2, 3) para o radio aparecer nessa ordem.
NIVEL_NOMES_PARA_NUMERO = {v["nome"]: k for k, v in sorted(NIVEIS.items())}


@st.cache_resource
def _garantir_indice() -> None:
    """Sem Qdrant configurado, o índice é o ChromaDB local, e no Streamlit
    Community Cloud o container sobe do zero a cada deploy — data/chroma/
    (gitignored, nunca commitado) não existe lá, por isso reconstrói a
    partir do corpus_confirmado.json (esse sim commitado) se estiver ausente
    ou desatualizado. Com Qdrant configurado (ver config.get_qdrant_config)
    ou com o índice local já pronto, isso é só uma checagem rápida de
    contagem, não refaz nada. `st.cache_resource` garante que isso roda uma
    vez por processo, não a cada pergunta."""
    import json

    from pipeline.vetorizar import CORPUS_JSON, contagem_atual, popular_indice

    esperado = len(json.loads(CORPUS_JSON.read_text(encoding="utf-8"))["chunks"])
    if contagem_atual() == esperado:
        return
    popular_indice()


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
div.st-key-caixa_nivel {
    border: 2px solid #4A7A8C !important; border-radius: 8px;
    background-color: rgba(74, 122, 140, 0.10); padding: 0.3rem 0.6rem;
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
    st.caption(
        f"Perguntas hoje: {perguntas_hoje(usuario_id)}/{MAX_PERGUNTAS_POR_USUARIO_DIA}"
    )
    st.markdown(
        f"<div style='font-size:0.8rem; line-height:1.35;'>{AVISO_HTML}</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(CAIXAS_CSS, unsafe_allow_html=True)

    with st.container(border=True, key="caixa_nivel"):
        st.subheader("Nível de resposta")
        nivel_nome = st.radio(
            "Escolha antes de perguntar",
            list(NIVEL_NOMES_PARA_NUMERO.keys()),
            index=0, key="nivel_input",
        )
    nivel = NIVEL_NOMES_PARA_NUMERO[nivel_nome]

    st.divider()

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
        try:
            verificar_limite_diario(usuario_id)
        except LimiteDiarioAtingido as e:
            st.error(str(e))
            st.stop()
        try:
            with st.spinner("Consultando as Sefirot..."):
                classificacao, chunks_usados, relacoes_estruturais, gerador = gerar_resposta_stream(pergunta, nivel=nivel)
            # A partir daqui o texto vai aparecendo progressivamente (streaming),
            # em vez de ficar em silêncio pelos ~20s+ que a geração completa leva.
            resposta_texto = st.write_stream(gerador)
            with st.expander("Classificação e fontes"):
                st.write(f"**Nível de resposta:** {nivel_nome}")
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
        except TetoDeCustoAtingido as e:
            st.error(str(e))
            st.stop()
        except ErroOpenRouter as e:
            sentry_sdk.capture_exception(e)
            st.error(f"Não consegui gerar uma resposta agora: {e}")
            st.stop()
        # Só registra a pergunta pro teto diário DEPOIS de gerar com sucesso
        # — uma falha da OpenRouter não deveria consumir a cota do usuário.
        registrar_pergunta(usuario_id)
    st.session_state.historico.append({
        "pergunta": pergunta,
        "resposta": resposta_texto,
        "classificacao": classificacao,
        "chunks_usados": chunks_usados,
        "relacoes_estruturais": relacoes_estruturais,
        "nivel_nome": nivel_nome,
    })
    # Sem isso, a sidebar (renderizada ANTES deste bloco no script) mostra o
    # contador de "perguntas hoje" de uma rodada atrás (achado real no Mentor,
    # 2026-08-09): o registro já tem o número certo, só a tela ficava
    # defasada até a próxima interação.
    st.rerun()
