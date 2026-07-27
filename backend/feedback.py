"""Armazenamento simples de feedback do usuário (avaliação + sugestões).

Grava em JSONL (uma linha = um registro), no mesmo espírito de
corpus_confirmado.json: um arquivo de texto simples, inspecionável
diretamente sem precisar rodar código. Fica em data/feedback.jsonl, já
coberto por .gitignore (a entrada "data/" já existe).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR
from backend.feedback_sheets import enviar_feedback_sheets

FEEDBACK_PATH = DATA_DIR / "feedback.jsonl"


def salvar_feedback(
    avaliacao: str,
    sugestao: str,
    pergunta: str | None = None,
    resposta: str | None = None,
) -> None:
    """Grava em dois lugares, independentemente: arquivo local (garantia,
    nunca falha por causa de rede) e Google Sheets via Form (acesso remoto,
    só ativo depois que backend/feedback_sheets.py for configurado com o
    FORM_ID e os ENTRY_* reais)."""
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "avaliacao": avaliacao,
        "sugestao": sugestao,
        "pergunta_relacionada": pergunta,
        "resposta_relacionada": resposta[:400] if resposta else None,
    }
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    enviar_feedback_sheets(avaliacao, sugestao, pergunta, resposta)


def carregar_feedback() -> list[dict]:
    if not FEEDBACK_PATH.exists():
        return []
    registros = []
    with FEEDBACK_PATH.open(encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                registros.append(json.loads(linha))
    return registros
