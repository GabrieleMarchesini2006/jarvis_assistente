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


def _find_prop_name(db: dict, candidate_names: set, wanted_types: set):
    """Trova il nome reale di una proprietà del database per nome+tipo."""
    for pname, meta in db["props"].items():
        if pname.lower() in candidate_names and meta["type"] in wanted_types:
            return pname, meta
    return None, None


def _read_prop_value(meta: dict):
    """Estrae il valore leggibile di una proprietà da una pagina restituita da query."""
    t = meta["type"]
    if t == "title":
        return "".join(x.get("plain_text", "") for x in meta["title"])
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in meta["rich_text"])
    if t in ("status", "select"):
        return meta[t]["name"] if meta[t] else None
    if t == "date":
        return meta["date"]["start"] if meta["date"] else None
    if t == "url":
        return meta.get("url")
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
    find_prop = lambda names, types: _find_prop_name(db, names, types)

    # Stato: se non specificato, per i database che ce l'hanno prova "Next Action".
    status_pname, status_meta = find_prop({"status"}, {"status", "select"})
    if status_pname:
        wanted = status or "Next Action"
        match = _match_option(wanted, status_meta.get("options", []))
        if match:
            properties[status_pname] = {status_meta["type"]: {"name": match}}
        elif status:
            avvisi.append(f"stato '{status}' non valido (opzioni: {status_meta.get('options')})")
    elif status:
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


def query_database(database: str, due_before: str = "", due_after: str = "",
                   status: str = "", exclude_completed: bool = True, limit: int = 25) -> str:
    """Interroga un database filtrando per scadenza (Due Date) e/o stato."""
    dbs = _discover_databases()
    db = dbs.get(database.strip().lower())
    if db is None:
        disponibili = ", ".join(d["name"] for d in dbs.values())
        return f"Database '{database}' non trovato. Disponibili: {disponibili}"

    date_pname, _ = _find_prop_name(db, {"due date", "due", "scadenza", "date"}, {"date"})
    status_pname, status_meta = _find_prop_name(db, {"status"}, {"status", "select"})

    conditions = []
    if (due_before or due_after) and date_pname:
        date_filter = {}
        if due_after:
            date_filter["on_or_after"] = due_after
        if due_before:
            date_filter["on_or_before"] = due_before
        conditions.append({"property": date_pname, "date": date_filter})
    if status and status_pname:
        match = _match_option(status, status_meta.get("options", [])) or status
        conditions.append({"property": status_pname, status_meta["type"]: {"equals": match}})
    elif exclude_completed and status_pname and "Completed" in status_meta.get("options", []):
        conditions.append({"property": status_pname, status_meta["type"]: {"does_not_equal": "Completed"}})

    body = {"page_size": min(limit, 100)}
    if len(conditions) == 1:
        body["filter"] = conditions[0]
    elif len(conditions) > 1:
        body["filter"] = {"and": conditions}
    if date_pname:
        body["sorts"] = [{"property": date_pname, "direction": "ascending"}]

    results = _client().request(
        path=f"data_sources/{db['data_source_id']}/query", method="POST", body=body
    ).get("results", [])
    if not results:
        return f"Nessuna voce trovata nel database {db['name']} con questi criteri."

    prio_pname, _ = _find_prop_name(db, {"priority", "priorità"}, {"select", "status"})
    out = []
    for p in results:
        props = p.get("properties", {})
        row = {"titolo": _read_prop_value(props.get(db["title_prop"], {"type": "title", "title": []}))}
        if status_pname and status_pname in props:
            row["stato"] = _read_prop_value(props[status_pname])
        if prio_pname and prio_pname in props:
            row["priorità"] = _read_prop_value(props[prio_pname])
        if date_pname and date_pname in props:
            row["scadenza"] = _read_prop_value(props[date_pname])
        out.append(row)
    return json.dumps(out, ensure_ascii=False)


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
        "name": "notion_query_database",
        "description": (
            "Interroga un database Notion filtrando per scadenza (Due Date) e/o stato. "
            "Usalo quando l'utente chiede le sue task/attività per una certa data ('cosa devo "
            "fare domani', 'task di questa settimana', 'scadenze in arrivo'). Per un singolo "
            "giorno passa lo stesso valore in due_after e due_before. Di default esclude le "
            "voci già completate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "Nome del database: Tasks, Projects, Resources, ecc.",
                },
                "due_after": {"type": "string", "description": "Scadenza minima YYYY-MM-DD (opzionale)"},
                "due_before": {"type": "string", "description": "Scadenza massima YYYY-MM-DD (opzionale)"},
                "status": {"type": "string", "description": "Filtra per uno stato specifico (opzionale)"},
                "exclude_completed": {
                    "type": "boolean",
                    "description": "Se true (default) esclude le voci completate",
                },
                "limit": {"type": "integer", "description": "Numero massimo di risultati (default 25)"},
            },
            "required": ["database"],
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
    "notion_query_database": query_database,
    "notion_search": search,
    "notion_read_page": read_page,
}
