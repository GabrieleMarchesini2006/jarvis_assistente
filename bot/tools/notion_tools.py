"""Tool Notion per l'agente."""
import json

from notion_client import Client

import config


def _client() -> Client:
    return Client(auth=config.NOTION_TOKEN)


def _rich_text_to_str(rich_text: list) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _paragraph_blocks(content: str) -> list:
    """Converte testo semplice in blocchi paragrafo Notion (uno per riga non vuota)."""
    blocks = []
    for line in content.split("\n"):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        })
    return blocks


def search(query: str) -> str:
    results = _client().search(query=query, page_size=10).get("results", [])
    if not results:
        return "Nessun risultato su Notion per questa ricerca."
    out = []
    for r in results:
        title = ""
        if r["object"] == "page":
            props = r.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title = _rich_text_to_str(prop["title"])
                    break
        elif r["object"] == "database":
            title = _rich_text_to_str(r.get("title", []))
        out.append({"id": r["id"], "tipo": r["object"], "titolo": title, "url": r.get("url", "")})
    return json.dumps(out, ensure_ascii=False)


def read_page(page_id: str) -> str:
    blocks = _client().blocks.children.list(block_id=page_id, page_size=100).get("results", [])
    lines = []
    for b in blocks:
        btype = b.get("type", "")
        data = b.get(btype, {})
        if "rich_text" in data:
            text = _rich_text_to_str(data["rich_text"])
            if btype == "to_do":
                mark = "x" if data.get("checked") else " "
                text = f"[{mark}] {text}"
            lines.append(text)
    return "\n".join(lines) or "(pagina vuota)"


def create_page(title: str, content: str = "") -> str:
    if not config.NOTION_PARENT_PAGE_ID:
        return "Errore: NOTION_PARENT_PAGE_ID non configurato nel file .env."
    page = _client().pages.create(
        parent={"page_id": config.NOTION_PARENT_PAGE_ID},
        properties={"title": [{"type": "text", "text": {"content": title}}]},
        children=_paragraph_blocks(content) if content else [],
    )
    return f"Pagina '{title}' creata su Notion: {page.get('url')}"


def append_to_page(page_id: str, content: str) -> str:
    _client().blocks.children.append(block_id=page_id, children=_paragraph_blocks(content))
    return "Contenuto aggiunto alla pagina."


DEFINITIONS = [
    {
        "name": "notion_search",
        "description": (
            "Cerca pagine e database su Notion per titolo/contenuto. Usalo per trovare "
            "l'id di una pagina prima di leggerla o modificarla."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Testo da cercare"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "notion_read_page",
        "description": "Legge il contenuto testuale di una pagina Notion dato il suo id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Id della pagina (da notion_search)"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_create_page",
        "description": (
            "Crea una nuova pagina su Notion (sotto la pagina radice configurata). "
            "Usalo quando l'utente chiede di salvare note, appunti, liste, idee."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titolo della pagina"},
                "content": {"type": "string", "description": "Contenuto testuale (una riga per paragrafo)"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "notion_append_to_page",
        "description": "Aggiunge testo in fondo a una pagina Notion esistente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Id della pagina"},
                "content": {"type": "string", "description": "Testo da aggiungere"},
            },
            "required": ["page_id", "content"],
        },
    },
]

HANDLERS = {
    "notion_search": search,
    "notion_read_page": read_page,
    "notion_create_page": create_page,
    "notion_append_to_page": append_to_page,
}
