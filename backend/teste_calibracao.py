"""Conjunto de perguntas de teste para calibração do mecanismo de 3 eixos —
não é suíte de testes automatizada com asserts, é ferramenta de inspeção
manual (o "correto" aqui depende de julgamento humano, não é checável
programaticamente)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.adam_kadmon import classificar

PERGUNTAS = [
    "Por que Deus quis criar o mundo material?",
    "Estou exausto depois de um dia ruim no trabalho e briguei com minha familia. O que faco?",
    "Como equilibrar dar generosamente e saber colocar limites?",
    "O que e a alma humana e quantos niveis ela tem?",
    "Como devo educar meus filhos segundo a Filosofia Chabad?",
    "Tenho medo de nao ter dinheiro suficiente no futuro.",
    "O que significa ter fe quando as coisas parecem nao fazer sentido?",
    "Como um lider deve se relacionar com quem ele lidera?",
]

if __name__ == "__main__":
    for pergunta in PERGUNTAS:
        r = classificar(pergunta)
        print(f"P: {pergunta}")
        print(f"  lacuna={r['protocolo_lacuna']} sefirot={r['sefirot']} entidades={r['entidades']} temas={r['temas']}")
        print(f"  justificativa: {r['justificativa']}")
        print()
