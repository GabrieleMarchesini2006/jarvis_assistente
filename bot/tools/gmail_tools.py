"""Tool Gmail per l'agente."""
import base64
import json
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from bot.google_auth import get_credentials


def _service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def _header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload: dict) -> str:
    """Estrae il testo del messaggio (preferendo text/plain)."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


def list_emails(query: str = "in:inbox", max_results: int = 10) -> str:
    svc = _service()
    resp = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    ids = [m["id"] for m in resp.get("messages", [])]
    if not ids:
        return "Nessuna email trovata per questa ricerca."
    out = []
    for msg_id in ids:
        msg = svc.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        out.append({
            "id": msg_id,
            "da": _header(msg["payload"], "From"),
            "oggetto": _header(msg["payload"], "Subject"),
            "data": _header(msg["payload"], "Date"),
            "anteprima": msg.get("snippet", ""),
            "non_letta": "UNREAD" in msg.get("labelIds", []),
        })
    return json.dumps(out, ensure_ascii=False)


def read_email(message_id: str) -> str:
    msg = _service().users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()
    body = _extract_body(msg["payload"]) or msg.get("snippet", "")
    result = {
        "da": _header(msg["payload"], "From"),
        "a": _header(msg["payload"], "To"),
        "oggetto": _header(msg["payload"], "Subject"),
        "data": _header(msg["payload"], "Date"),
        "testo": body[:8000],
    }
    return json.dumps(result, ensure_ascii=False)


def send_email(to: str, subject: str, body: str) -> str:
    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    sent = _service().users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return f"Email inviata a {to} (id: {sent.get('id')})."


DEFINITIONS = [
    {
        "name": "gmail_list_emails",
        "description": (
            "Cerca ed elenca le email su Gmail. Usalo quando l'utente chiede delle sue email, "
            "se ha messaggi nuovi, email da qualcuno, ecc. La query usa la sintassi di ricerca "
            "di Gmail, es. 'is:unread', 'from:mario@example.com', 'subject:fattura newer_than:7d'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query di ricerca Gmail (default 'in:inbox')"},
                "max_results": {"type": "integer", "description": "Numero massimo di risultati (default 10)"},
            },
            "required": [],
        },
    },
    {
        "name": "gmail_read_email",
        "description": "Legge il contenuto completo di una email dato il suo id (ottenuto da gmail_list_emails).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Id del messaggio"},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_send_email",
        "description": (
            "Invia una email dall'account Gmail dell'utente. Prima di inviare, mostra sempre "
            "all'utente la bozza (destinatario, oggetto, testo) e chiedi conferma, a meno che "
            "l'utente non abbia già dettato esplicitamente tutto il contenuto e chiesto di inviare."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Indirizzo email del destinatario"},
                "subject": {"type": "string", "description": "Oggetto"},
                "body": {"type": "string", "description": "Testo del messaggio"},
            },
            "required": ["to", "subject", "body"],
        },
    },
]

HANDLERS = {
    "gmail_list_emails": list_emails,
    "gmail_read_email": read_email,
    "gmail_send_email": send_email,
}
