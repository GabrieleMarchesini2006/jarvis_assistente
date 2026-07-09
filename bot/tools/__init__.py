"""Registro dei tool esposti all'agente Gemini.

Ogni tool ha una definizione JSON Schema (per l'API) e una funzione Python
che lo esegue. execute_tool() fa il dispatch per nome.

Alcuni tool sono "context-aware": ricevono un dizionario di contesto (con il
chat_id) perché devono interagire con l'utente (es. mostrare bottoni di
conferma). Sono elencati in CONTEXT_AWARE.
"""
from bot.tools import calendar_tools, gmail_tools, notion_tools, memory_tools

TOOL_DEFINITIONS = (
    calendar_tools.DEFINITIONS
    + gmail_tools.DEFINITIONS
    + notion_tools.DEFINITIONS
    + memory_tools.DEFINITIONS
)

_HANDLERS = {}
_HANDLERS.update(calendar_tools.HANDLERS)
_HANDLERS.update(gmail_tools.HANDLERS)
_HANDLERS.update(notion_tools.HANDLERS)
_HANDLERS.update(memory_tools.HANDLERS)

# Tool che ricevono il contesto (chat_id) come primo argomento.
CONTEXT_AWARE = {"gmail_send_email", "calendar_delete_event"}


def execute_tool(name: str, tool_input: dict, context: dict = None) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Tool sconosciuto: {name}")
    if name in CONTEXT_AWARE:
        return handler(context or {}, **tool_input)
    return handler(**tool_input)
