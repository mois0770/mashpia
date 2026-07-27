"""Calibração da geração de resposta — não é suíte com asserts (qualidade de
texto não é checável programaticamente), é ferramenta pra rodar um conjunto
fixo de perguntas e inspecionar contra o checklist derivado do prompt fixo:

  1. Abertura pela origem/propósito, não pelo sintoma direto
  2. Ordem Alma -> Pensamento -> Mente -> Sentimento -> Ação presente
  3. Fechamento reconecta à Fonte / Dirá BeTachtonim
  4. Só cita conteúdo dos chunks fornecidos (marcadores [N]), nada de fora
  5. Se protocolo_lacuna=True, reconhece a lacuna em vez de improvisar
  6. Sem disclaimers de neutralidade/distanciamento
  7. Terminologia fixada correta (Daat=interface, Dirá BeTachtonim=Objetivo da Criação)
  8. Resposta não corta no meio (max_tokens suficiente)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.gerar_resposta import gerar_resposta

PERGUNTAS = [
    "Por que Deus quis criar o mundo material?",
    "Estou exausto depois de um dia ruim no trabalho e briguei com minha familia. O que faco?",
    "Como equilibrar dar generosamente e saber colocar limites?",
    "O que e a alma humana e quantos niveis ela tem?",
    "Qual e a melhor receita de bolo de chocolate?",  # deve acionar protocolo_lacuna
]

if __name__ == "__main__":
    for pergunta in PERGUNTAS:
        r = gerar_resposta(pergunta)
        print("=" * 80)
        print(f"PERGUNTA: {pergunta}")
        print(f"lacuna={r['classificacao']['protocolo_lacuna']} sefirot={r['classificacao']['sefirot']}")
        print(f"relacoes estruturais: {r['relacoes_estruturais']}")
        print(f"chunks: {[c['documento'] for c in r['chunks_usados']]}")
        print(f"tamanho da resposta: {len(r['resposta'])} caracteres")
        print("-" * 80)
        print(r["resposta"])
        print()
