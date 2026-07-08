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


def delete_event(event_id: str) -> str:
    _service().events().delete(calendarId="primary", eventId=event_id).execute()
    return f"Evento {event_id} eliminato."


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
        "name": "calendar_delete_event",
        "description": (
            "Elimina un evento dal calendario dato il suo id. Prima di eliminare, "
            "usa calendar_list_events per trovare l'id giusto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Id dell'evento da eliminare"},
            },
            "required": ["event_id"],
        },
    },
]

HANDLERS = {
    "calendar_list_events": list_events,
    "calendar_create_event": create_event,
    "calendar_delete_event": delete_event,
}
