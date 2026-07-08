"""Registro dei tool esposti all'agente Claude.

Ogni tool ha una definizione JSON Schema (per l'API) e una funzione Python
che lo esegue. execute_tool() fa il dispatch per nome.
"""
from bot.tools import calendar_tools, gmail_tools, notion_tools

TOOL_DEFINITIONS = (
    calendar_tools.DEFINITIONS
    + gmail_tools.DEFINITIONS
    + notion_tools.DEFINITIONS
)

_HANDLERS = {}
_HANDLERS.update(calendar_tools.HANDLERS)
_HANDLERS.update(gmail_tools.HANDLERS)
_HANDLERS.update(notion_tools.HANDLERS)


def execute_tool(name: str, tool_input: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Tool sconosciuto: {name}")
    return handler(**tool_input)
