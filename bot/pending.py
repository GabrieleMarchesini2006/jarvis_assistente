"""Azioni in sospeso in attesa di conferma dell'utente (bottoni Telegram).

Quando l'agente vuole compiere un'azione irreversibile (inviare un'email,
eliminare un evento), la salva qui e mostra i bottoni ✅/❌. Al click,
l'azione viene recuperata ed eseguita (o scartata).
"""
import json
import secrets

import config

PENDING_FILE = config.DATA_DIR / "pending.json"


def _load() -> dict:
    if not PENDING_FILE.exists():
        return {}
    try:
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def save(action: dict) -> str:
    """Salva un'azione in sospeso e restituisce un token breve (per il callback)."""
    token = secrets.token_urlsafe(6)
    data = _load()
    data[token] = action
    _save(data)
    return token


def pop(token: str):
    """Recupera ed elimina un'azione in sospeso (None se non esiste)."""
    data = _load()
    action = data.pop(token, None)
    if action is not None:
        _save(data)
    return action
