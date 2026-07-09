"""Memoria a lungo termine: fatti duraturi sull'utente, salvati su file JSON.

Diversamente dalla cronologia (che tiene solo gli ultimi messaggi), questi
fatti persistono per sempre e vengono inseriti nel prompt di sistema a ogni
richiesta, così il bot "conosce" l'utente tra una sessione e l'altra.
"""
import json

import config

FACTS_FILE = config.DATA_DIR / "facts.json"
MAX_FACTS = 100


def load_facts() -> list:
    if not FACTS_FILE.exists():
        return []
    try:
        return json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(facts: list) -> None:
    FACTS_FILE.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")


def add_fact(fact: str) -> str:
    fact = fact.strip()
    if not fact:
        return "Fatto vuoto, niente da salvare."
    facts = load_facts()
    if any(f.lower() == fact.lower() for f in facts):
        return "Lo sapevo già."
    facts.append(fact)
    _save(facts[-MAX_FACTS:])
    return f"Memorizzato: {fact}"


def forget_fact(query: str) -> str:
    query = query.strip().lower()
    facts = load_facts()
    kept = [f for f in facts if query not in f.lower()]
    removed = len(facts) - len(kept)
    if removed == 0:
        return "Non ho trovato niente di simile da dimenticare."
    _save(kept)
    return f"Dimenticato ({removed} voce/i)."


def format_facts() -> str:
    return "\n".join(f"- {f}" for f in load_facts())
