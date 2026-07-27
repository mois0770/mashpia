"""Mostra todo o feedback recebido até agora. Rodar com:
    python3 backend/ver_feedback.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.feedback import carregar_feedback

if __name__ == "__main__":
    registros = carregar_feedback()
    if not registros:
        print("Nenhum feedback recebido ainda.")
    for i, r in enumerate(registros, 1):
        print(f"--- Feedback {i} ({r['timestamp']}) ---")
        print(f"Avaliação: {r['avaliacao']}")
        print(f"Sugestão: {r['sugestao'] or '(vazio)'}")
        if r.get("pergunta_relacionada"):
            print(f"Pergunta relacionada: {r['pergunta_relacionada']}")
        if r.get("resposta_relacionada"):
            print(f"Início da resposta relacionada: {r['resposta_relacionada'][:150]}…")
        print()
    print(f"Total: {len(registros)} feedback(s)")
