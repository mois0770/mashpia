# Mashpia

Chatbot GraphRAG fundamentado na Filosofia Chabad (Chassidut). Responde
perguntas classificando-as por Sefirot/Entidades/Temas (grafo estrutural em
`grafo/schema.py`), recupera trechos de um corpus curado (`pipeline/`) e gera
a resposta seguindo o molde retórico Adon Olam com um prompt fixo
(`00_Prompt_Sistema_Fixo.txt`).

Estado detalhado da implementação, o que já foi testado/calibrado e o que
ainda falta: ver `00_Estado_Atual.txt`.

## Rodar localmente

```bash
pip install -r requirements.txt
echo "SUA_CHAVE_AQUI" > Openrouter_Ket.txt   # ou export OPENROUTER_API_KEY=...
streamlit run interface/app.py
```

Para dirigir a interface via Playwright (screenshot, sem navegador manual),
ver `.claude/skills/run-mashpia/SKILL.md`.

## Deploy (Streamlit Community Cloud)

Arquivo principal: `interface/app.py`. A chave da OpenRouter é lida de
`st.secrets["OPENROUTER_API_KEY"]` quando `Openrouter_Ket.txt` não existe
(caso do Cloud, onde o repositório é a única coisa que sobe) — configurar em
Settings → Secrets do app no painel do Streamlit Cloud.

O índice ChromaDB (`data/chroma/`, gitignored) é reconstruído automaticamente
a partir de `pipeline/corpus_confirmado.json` (esse sim versionado) na
primeira execução do container.
