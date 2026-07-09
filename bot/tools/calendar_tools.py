"""Tool Google Calendar per l'agente."""
import json

from googleapiclient.discovery import build

import config
from bot.google_auth import get_credentials


def _service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


def list_events(time_min: str, time_max: str, max_results: int = 20) -> str:
    events = (
        _service().events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    if not events:
        return "Nessun evento nel periodo indicato."
    out = []
    for ev in events:
        start = ev["start"].get("dateTime", ev["start"].get("date"))
        end = ev["end"].get("dateTime", ev["end"].get("date"))
        out.append({
            "id": ev["id"],
            "titolo": ev.get("summary", "(senza titolo)"),
            "inizio": start,
            "fine": end,
            "luogo": ev.get("location", ""),
            "descrizione": (ev.get("description") or "")[:200],
        })
    return json.dumps(out, ensure_ascii=False)


def create_event(summary: str, start: str, end: str,
                 description: str = "", location: str = "") -> str:
    body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start, "timeZone": config.TIMEZONE},
        "end": {"dateTime": end, "timeZone": config.TIMEZONE},
    }
    ev = _service().events().insert(calendarId="primary", body=body).execute()
    return f"Evento creato: {ev.get('summary')} (id: {ev.get('id')}, link: {ev.get('htmlLink')})"


def update_event(event_id: str, summary: str = "", start: str = "", end: str = "",
                 description: str = "", location: str = "") -> str:
    """Modifica i campi indicati di un evento esistente (gli altri restano invariati)."""
    svc = _service()
    ev = svc.events().get(calendarId="primary", eventId=event_id).execute()
    if summary:
        ev["summary"] = summary
    if description:
        ev["description"] = description
    if location:
        ev["location"] = location
    if start:
        ev["start"] = {"dateTime": start, "timeZone": config.TIMEZONE}
    if end:
        ev["end"] = {"dateTime": end, "timeZone": config.TIMEZONE}
    updated = svc.events().update(calendarId="primary", eventId=event_id, body=ev).execute()
    return f"Evento aggiornato: {updated.get('summary')} (id: {updated.get('id')})"


def delete_event(context: dict, event_id: str, summary: str = "") -> str:
    """Chiede conferma con i bottoni prima di eliminare (azione irreversibile)."""
    from bot import pending, telegram_api
    chat_id = context.get("chat_id")
    if not chat_id:
        # Senza contesto (es. chiamata di test): elimina direttamente.
        _service().events().delete(calendarId="primary", eventId=event_id).execute()
        return f"Evento {event_id} eliminato."
    token = pending.save({"type": "delete_event", "event_id": event_id})
    nome = summary or event_id
    telegram_api.send_confirmation(
        chat_id, f"🗑 Vuoi eliminare l'evento <b>{nome}</b>?", token
    )
    return "Ho chiesto conferma all'utente con i bottoni. Attendo la sua decisione, non fare altro."


def do_delete_event(event_id: str) -> str:
    """Esecuzione reale dell'eliminazione (chiamata dopo la conferma dai bottoni)."""
    _service().events().delete(calendarId="primary", eventId=event_id).execute()
    return "Evento eliminato."


DEFINITIONS = [
    {
        "name": "calendar_list_events",
        "description": (
            "Elenca gli eventi del Google Calendar principale in un intervallo di tempo. "
            "Usalo quando l'utente chiede cosa ha in programma, i suoi impegni, appuntamenti ecc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {
                    "type": "string",
                    "description": "Inizio intervallo in formato RFC3339, es. 2026-07-08T00:00:00+02:00",
                },
                "time_max": {
                    "type": "string",
                    "description": "Fine intervallo in formato RFC3339, es. 2026-07-09T00:00:00+02:00",
                },
                "max_results": {"type": "integer", "description": "Numero massimo di eventi (default 20)"},
            },
            "required": ["time_min", "time_max"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Crea un evento nel Google Calendar principale dell'utente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Titolo dell'evento"},
                "start": {
                    "type": "string",
                    "description": "Inizio in formato RFC3339 senza timezone esplicita, es. 2026-07-08T15:00:00",
                },
                "end": {"type": "string", "description": "Fine, stesso formato di start"},
                "description": {"type": "string", "description": "Descrizione (opzionale)"},
                "location": {"type": "string", "description": "Luogo (opzionale)"},
            },
            "required": ["summary", "start", "end"],
        },
    },
    {
        "name": "calendar_update_event",
        "description": (
            "Modifica un evento esistente (sposta orario, cambia titolo/luogo/descrizione). "
            "Usa prima calendar_list_events per trovare l'id. Passa solo i campi da cambiare."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Id dell'evento da modificare"},
                "summary": {"type": "string", "description": "Nuovo titolo (opzionale)"},
                "start": {"type": "string", "description": "Nuovo inizio RFC3339 senza timezone (opzionale)"},
                "end": {"type": "string", "description": "Nuova fine RFC3339 senza timezone (opzionale)"},
                "description": {"type": "string", "description": "Nuova descrizione (opzionale)"},
                "location": {"type": "string", "description": "Nuovo luogo (opzionale)"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_delete_event",
        "description": (
            "Elimina un evento dal calendario dato il suo id. Mostra all'utente un bottone "
            "di conferma. Usa prima calendar_list_events per trovare l'id giusto e passa anche "
            "il titolo dell'evento nel campo summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Id dell'evento da eliminare"},
                "summary": {"type": "string", "description": "Titolo dell'evento (per la conferma)"},
            },
            "required": ["event_id"],
        },
    },
]

HANDLERS = {
    "calendar_list_events": list_events,
    "calendar_create_event": create_event,
    "calendar_update_event": update_event,
    "calendar_delete_event": delete_event,
}
