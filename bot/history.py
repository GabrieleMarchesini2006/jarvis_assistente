"""Cronologia conversazione per chat, salvata su file JSON.

Si salvano solo gli scambi testuali finali (utente -> risposta), non i blocchi
di tool use intermedi: basta per dare memoria al bot tra un messaggio e l'altro
e sopravvive ai riavvii della web app.
"""
import json

import config

MAX_TURNS = 20  # numero massimo di messaggi (user+assistant) conservati


def _path(chat_id: int):
    return config.DATA_DIR / f"history_{chat_id}.json"


def load(chat_id: int) -> list:
    path = _path(chat_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def append(chat_id: int, user_text: str, assistant_text: str) -> None:
    history = load(chat_id)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})
    history = history[-MAX_TURNS:]
    _path(chat_id).write_text(
        json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def clear(chat_id: int) -> None:
    path = _path(chat_id)
    if path.exists():
        path.unlink()
