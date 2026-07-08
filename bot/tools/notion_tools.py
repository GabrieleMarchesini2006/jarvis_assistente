"""Tool Notion per l'agente.

La pagina radice dell'utente contiene un sistema PARA con più database
(Tasks, Projects, Areas, Resources, Archive). Quando l'utente chiede di
salvare qualcosa, il bot aggiunge una RIGA nel database giusto (non una
pagina sciolta). I database e i loro campi vengono scoperti dinamicamente.
"""
import json

from notion_client import Client

import config

# La nuova API di Notion crea le pagine dentro una "data source", non
# direttamente nel database. Scopriamo la struttura una volta e la teniamo
# in cache (si ripopola al primo uso dopo un riavvio della web app).
_DB_CACHE = None


def _client() -> Client:
    return Client(auth=config.NOTION_TOKEN)


def _rich_text_to_str(rich_text: list) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _discover_databases() -> dict:
    """Trova i database figli della pagina radice con i loro campi editabili.

    Ritorna: { nome_lower: {"name", "data_source_id", "title_prop", "props"} }
    dove "props" mappa nome_campo -> {"type", "options"?}.
    """
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE

    n = _client()
    result = {}
    blocks = n.blocks.children.list(
        block_id=config.NOTION_PARENT_PAGE_ID, page_size=100
    ).get("results", [])
    for b in blocks:
        if b.get("type") != "child_database":
            continue
        db = n.databases.retrieve(database_id=b["id"])
        sources = db.get("data_sources", [])
        if not sources:
            continue
        ds_id = sources[0]["id"]
        name = _rich_text_to_str(db.get("title", [])) or "(senza nome)"
        ds = n.request(path=f"data_sources/{ds_id}", method="GET")

        props = {}
        title_prop = "Name"
        for pname, meta in ds.get("properties", {}).items():
            ptype = meta["type"]
            if ptype == "title":
                title_prop = pname
                continue
            entry = {"type": ptype}
            if ptype in ("select", "status", "multi_select"):
                entry["options"] = [o["name"] for o in meta[ptype].get("options", [])]
            props[pname] = entry

        result[name.lower()] = {
            "name": name,
            "data_source_id": ds_id,
            "title_prop": title_prop,
            "props": props,
        }
    _DB_CACHE = result
    return result


def _match_option(value: str, options: list) -> str | None:
    """Trova l'opzione (select/status) che corrisponde al valore, ignorando maiuscole."""
    for opt in options:
        if opt.lower() == value.strip().lower():
            return opt
    return None


def list_databases() -> str:
    """Elenca i database disponibili con i campi che si possono compilare."""
    dbs = _discover_databases()
    if not dbs:
        return "Nessun database trovato nella pagina Notion configurata."
    out = []
    for db in dbs.values():
        campi = []
        for pname, meta in db["props"].items():
            if meta["type"] in ("select", "status"):
                campi.append(f"{pname} ({'/'.join(meta.get('options', []))})")
            elif meta["type"] in ("rich_text", "date", "url"):
                campi.append(pname)
        out.append({"database": db["name"], "campi_compilabili": campi})
    return json.dumps(out, ensure_ascii=False)


def create_entry(database: str, title: str, status: str = "", priority: str = "",
                 due_date: str = "", description: str = "", url: str = "") -> str:
    """Aggiunge una riga a un database PARA (Tasks, Projects, Resources, ...)."""
    dbs = _discover_databases()
    db = dbs.get(database.strip().lower())
    if db is None:
        disponibili = ", ".join(d["name"] for d in dbs.values())
        return f"Database '{database}' non trovato. Disponibili: {disponibili}"

    properties = {
        db["title_prop"]: {"title": [{"type": "text", "text": {"content": title}}]}
    }
    avvisi = []

    # Mappa i parametri "logici" ai campi reali del database (per nome, case-insensitive).
    def find_prop(candidate_names, wanted_types):
        for pname, meta in db["props"].items():
            if pname.lower() in candidate_names and meta["type"] in wanted_types:
                return pname, meta
        return None, None

    if status:
        pname, meta = find_prop({"status"}, {"status", "select"})
        if pname:
            match = _match_option(status, meta.get("options", []))
            if match:
                properties[pname] = {meta["type"]: {"name": match}}
            else:
                avvisi.append(f"stato '{status}' non valido (opzioni: {meta.get('options')})")
        else:
            avvisi.append("questo database non ha un campo Stato")

    if priority:
        pname, meta = find_prop({"priority", "priorità"}, {"select", "status"})
        if pname:
            match = _match_option(priority, meta.get("options", []))
            if match:
                properties[pname] = {meta["type"]: {"name": match}}
            else:
                avvisi.append(f"priorità '{priority}' non valida (opzioni: {meta.get('options')})")

    if due_date:
        pname, meta = find_prop({"due date", "due", "scadenza", "date"}, {"date"})
        if pname:
            properties[pname] = {"date": {"start": due_date}}
        else:
            avvisi.append("questo database non ha un campo Data")

    if description:
        pname, meta = find_prop({"description", "descrizione", "note", "notes"}, {"rich_text"})
        if pname:
            properties[pname] = {"rich_text": [{"type": "text", "text": {"content": description}}]}

    if url:
        pname, meta = find_prop({"url", "link"}, {"url"})
        if pname:
            properties[pname] = {"url": url}

    page = _client().pages.create(
        parent={"type": "data_source_id", "data_source_id": db["data_source_id"]},
        properties=properties,
    )
    msg = f"Aggiunto '{title}' al database {db['name']} di Notion: {page.get('url')}"
    if avvisi:
        msg += " (nota: " + "; ".join(avvisi) + ")"
    return msg


def search(query: str) -> str:
    results = _client().search(query=query, page_size=10).get("results", [])
    if not results:
        return "Nessun risultato su Notion per questa ricerca."
    out = []
    for r in results:
        title = ""
        if r["object"] == "page":
            for prop in r.get("properties", {}).values():
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


DEFINITIONS = [
    {
        "name": "notion_list_databases",
        "description": (
            "Elenca i database Notion dell'utente (sistema PARA: Tasks, Projects, Areas, "
            "Resources, Archive) e i campi compilabili di ciascuno. Usalo PRIMA di aggiungere "
            "una voce, se non sei sicuro di quale database usare o di quali stati/priorità esistano."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "notion_create_entry",
        "description": (
            "Aggiunge una RIGA a uno dei database Notion dell'utente. È il modo giusto per "
            "salvare cose su Notion (NON creare pagine sciolte). Scegli il database in base a "
            "cosa chiede l'utente: 'Tasks' per compiti/cose da fare, 'Projects' per progetti, "
            "'Resources' per link/articoli/risorse da salvare, 'Areas' per aree di responsabilità. "
            "Compila solo i campi pertinenti; se non sei sicuro dei valori di stato/priorità usa "
            "prima notion_list_databases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Nome del database: Tasks, Projects, Areas, Resources o Archive",
                },
                "title": {"type": "string", "description": "Titolo/nome della voce"},
                "status": {"type": "string", "description": "Stato (opzionale, deve essere un valore valido del database)"},
                "priority": {"type": "string", "description": "Priorità: Low, Medium, High, Urgent (opzionale)"},
                "due_date": {"type": "string", "description": "Scadenza in formato YYYY-MM-DD (opzionale)"},
                "description": {"type": "string", "description": "Descrizione/note (opzionale)"},
                "url": {"type": "string", "description": "Link, utile per le Resources (opzionale)"},
            },
            "required": ["database", "title"],
        },
    },
    {
        "name": "notion_search",
        "description": (
            "Cerca pagine e database su Notion per titolo/contenuto. Usalo per trovare "
            "l'id di una pagina prima di leggerla."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Testo da cercare"}},
            "required": ["query"],
        },
    },
    {
        "name": "notion_read_page",
        "description": "Legge il contenuto testuale di una pagina Notion dato il suo id.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string", "description": "Id della pagina (da notion_search)"}},
            "required": ["page_id"],
        },
    },
]

HANDLERS = {
    "notion_list_databases": list_databases,
    "notion_create_entry": create_entry,
    "notion_search": search,
    "notion_read_page": read_page,
}
