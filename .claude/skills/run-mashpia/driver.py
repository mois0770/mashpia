"""Drives the Mashpia Streamlit app with Playwright and takes screenshots.

Usage (from MASHPIA/ directory, with the app already launched — see SKILL.md):
    python3 .claude/skills/run-mashpia/driver.py ["pergunta opcional"] ["nivel opcional"]

`nivel` is the exact radio label: "Completo" (default), "Resumido", or
"Essência prática" (2026-07-27: 3 níveis de resposta, ver backend/gerar_resposta.py NIVEIS).

Screenshots are written next to this script, in ./screenshots/.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

PERGUNTA = sys.argv[1] if len(sys.argv) > 1 else (
    "Como equilibrar dar generosamente e saber colocar limites?"
)
NIVEL = sys.argv[2] if len(sys.argv) > 2 else "Completo"

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1400, "height": 1600})
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    page.goto("http://localhost:8501", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("text=Mashpia", timeout=30000)
    page.screenshot(path=str(SCREENSHOT_DIR / "01_inicial.png"), full_page=True)

    if NIVEL != "Completo":
        page.get_by_text(NIVEL, exact=True).click()

    chat_input = page.get_by_placeholder("Sua pergunta...")
    chat_input.click()
    chat_input.fill(PERGUNTA)
    chat_input.press("Enter")

    # o spinner "Consultando as Sefirot..." aparece durante classificação+geração
    # e desaparece (detach) quando o streaming termina — mais confiável que sleep
    # porque a geração real leva ~20-30s.
    page.wait_for_selector("text=Consultando as Sefirot", timeout=15000)
    print("spinner apareceu, aguardando terminar o streaming...")
    page.wait_for_selector("text=Consultando as Sefirot", state="detached", timeout=120000)
    print("spinner sumiu, resposta deve estar completa")

    time.sleep(3)  # folga para o streaming assentar antes do screenshot/clique
    page.screenshot(path=str(SCREENSHOT_DIR / "02_resposta.png"), full_page=True)

    expander = page.get_by_text("Classificação e fontes")
    expander.click()
    time.sleep(1)
    page.screenshot(path=str(SCREENSHOT_DIR / "03_expander.png"), full_page=True)

    corpo = page.inner_text("body")
    (SCREENSHOT_DIR / "pagina_texto.txt").write_text(corpo)

    print("CONTÉM 'Relações estruturais':", "Relações estruturais" in corpo)
    print("CONTÉM 'a tradição' (minúsculo, solto):", "a tradição" in corpo.lower())
    print("CONTÉM 'Chabad':", "Chabad" in corpo)
    print("ERROS DE CONSOLE:", console_errors)
    print("Screenshots em:", SCREENSHOT_DIR)

    browser.close()
