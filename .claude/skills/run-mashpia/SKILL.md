---
name: run-mashpia
description: Build, run, and drive the Mashpia Streamlit chatbot (Filosofia Chabad). Use when asked to start Mashpia, launch the Streamlit app, take a screenshot of the chat UI, or verify a change (prompt, graph traversal, feedback form) shows up correctly in the running interface.
---

Mashpia is a Streamlit chat app (`interface/app.py`). It has no test
suite of its own for the UI — driving it means launching the real
server and controlling a headless Chromium against it with Playwright
(`.claude/skills/run-mashpia/driver.py`), since `chromium-cli` isn't
installed in this environment.

All paths below are relative to `MASHPIA/` (this skill's grandparent
directory).

## Prerequisites

No system packages were needed in this container — headless Chromium
ran without `--with-deps`. Playwright itself isn't preinstalled:

```bash
pip install playwright
python3 -m playwright install chromium
```

(`playwright install chromium --with-deps` FAILS here — it tries to
`sudo apt-get` and there's no terminal for the password prompt. Skip
`--with-deps`; the plain install works because the required shared
libs are already present.)

## Run (agent path)

1. Launch the app in the background and wait for it to actually serve
   (Streamlit's own log line isn't enough — poll the port):

```bash
lsof -ti:8501 -sTCP:LISTEN | xargs -r kill   # free the port if a previous run is still up
nohup streamlit run interface/app.py --server.port 8501 --server.headless true > /tmp/mashpia_streamlit.log 2>&1 &
disown
timeout 40 bash -c 'until curl -sf http://localhost:8501 >/dev/null; do sleep 1; done'
```

2. Drive it with the Playwright script:

```bash
python3 .claude/skills/run-mashpia/driver.py "sua pergunta aqui"
```

Argument is optional — defaults to a question known to activate a
SINTETIZA graph relation ("Como equilibrar dar generosamente e saber
colocar limites?"), useful for checking the graph-traversal feature
specifically.

The script: navigates to `localhost:8501`, waits for the `Mashpia`
title, fills the chat input (`get_by_placeholder("Sua pergunta...")`),
presses Enter, waits for the "Consultando as Sefirot..." spinner to
appear then detach (generation takes ~20-30s — don't `sleep`, wait for
the spinner), opens the "Classificação e fontes" expander, and prints
whether key strings appear in the page body (structural relations
shown, no stray "a tradição", console errors).

Screenshots land in `.claude/skills/run-mashpia/screenshots/`:
`01_inicial.png` (empty chat), `02_resposta.png` (answer streamed),
`03_expander.png` (classification/graph-relations expander open). Full
extracted page text is saved to `screenshots/pagina_texto.txt` for
grepping instead of re-reading images.

3. Stop the server when done:

```bash
lsof -ti:8501 -sTCP:LISTEN | xargs -r kill
```

## Run (human path)

```bash
streamlit run interface/app.py
```

Opens on `http://localhost:8501` (or prints the URL); Streamlit tries
to open a browser tab, which no-ops headless. `Ctrl-C` to stop.

## Test

No automated test suite for the UI. For the backend/generation logic:

```bash
python3 backend/teste_calibracao_geracao.py   # 5 questions, inspect output manually (not asserts)
```

---

## Gotchas

- **Don't `sleep()` for the response** — real generation takes
  ~20-30s (classification + LLM streaming). Wait for the "Consultando
  as Sefirot..." spinner to appear, then wait for it to `detach` —
  that's the actual completion signal, not a guessed delay.
- **`curl` readiness check, not the Streamlit log line** — the "You can
  now view your Streamlit app" message prints before the app is fully
  ready to accept the first request; poll the port instead.
- **Port reuse**: if a previous run is still bound to 8501, the new
  `streamlit run` silently picks a different port or errors — always
  `lsof -ti:8501 -sTCP:LISTEN | xargs -r kill` before relaunching.
- **`--with-deps` fails non-interactively** — it shells out to `sudo`
  which needs a TTY for the password. Just run `playwright install
  chromium` without it; this container already had what was needed.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'playwright'`**: not
  installed yet — `pip install playwright`.
- **`sudo: A terminal is required to authenticate`** during `playwright
  install chromium --with-deps`: drop `--with-deps`, plain `playwright
  install chromium` works in this container.
- **`curl: (7) Failed to connect`** in the readiness poll: Streamlit
  hasn't bound the port yet — the `timeout 40 bash -c 'until curl...'`
  loop handles this; if it still times out, check
  `/tmp/mashpia_streamlit.log` for a real startup error (e.g. missing
  `Openrouter_Ket.txt` / `OPENROUTER_API_KEY`).
