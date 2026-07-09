"""Tool per la memoria a lungo termine dell'agente."""
from bot import memory


def memory_save(fact: str) -> str:
    return memory.add_fact(fact)


def memory_forget(query: str) -> str:
    return memory.forget_fact(query)


def memory_list() -> str:
    facts = memory.load_facts()
    return "\n".join(f"- {f}" for f in facts) if facts else "Non ho ancora memorizzato nulla."


DEFINITIONS = [
    {
        "name": "memory_save",
        "description": (
            "Salva un fatto duraturo sull'utente da ricordare nelle conversazioni future "
            "(preferenze, persone ricorrenti, abitudini, dati fissi come indirizzi o nomi). "
            "Non usarlo per cose temporanee o banali."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"fact": {"type": "string", "description": "Il fatto da ricordare, conciso"}},
            "required": ["fact"],
        },
    },
    {
        "name": "memory_forget",
        "description": "Dimentica i fatti memorizzati che contengono un certo testo.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Testo da cercare tra i fatti da dimenticare"}},
            "required": ["query"],
        },
    },
    {
        "name": "memory_list",
        "description": "Elenca tutti i fatti che hai memorizzato sull'utente.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

HANDLERS = {
    "memory_save": memory_save,
    "memory_forget": memory_forget,
    "memory_list": memory_list,
}
