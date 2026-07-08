"""Digest mattutino delle notizie su AI e produttività.

Usa Gemini con la ricerca Google (grounding) per raccogliere le notizie più
recenti e le relative fonti, poi invia tutto su Telegram. Pensato per essere
lanciato da uno scheduled task una volta al giorno.
"""
import html as html_lib
import re

from google import genai
from google.genai import types

import config
from bot import telegram_api

# Per il digest usiamo flash (migliore con la ricerca web); gira 1 volta al
# giorno, quindi consuma pochissime richieste.
NEWS_MODEL = "gemini-2.5-flash"

PROMPT = (
    "Cerca sul web le notizie più importanti e recenti delle ultime 24-48 ore "
    "sul mondo dell'intelligenza artificiale e della produttività personale/lavorativa. "
    "Selezionane da 5 a 7. Scrivi in italiano, in modo conciso e adatto a Telegram. "
    "Per ciascuna notizia: una riga con un titolo breve, poi una frase di riassunto. "
    "Non inventare nulla: basati solo sui risultati di ricerca. Non aggiungere una "
    "sezione fonti alla fine (i link li aggiungo io)."
)

client = genai.Client(api_key=config.GEMINI_API_KEY)


def _markdown_to_html(text: str) -> str:
    """Converte il markdown base di Gemini (già HTML-escaped) in HTML per Telegram."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)   # **grassetto**
    text = re.sub(r"(?m)^\s*[\*\-]\s+", "• ", text)         # bullet * / -
    return text


def build_digest() -> str:
    """Genera il digest HTML (testo + fonti) pronto da inviare su Telegram."""
    resp = client.models.generate_content(
        model=NEWS_MODEL,
        contents=PROMPT,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    testo = (resp.text or "").strip()

    # Raccoglie le fonti dai metadati di grounding (link reali usati da Gemini).
    fonti = []
    visti = set()
    cand = resp.candidates[0] if resp.candidates else None
    gm = getattr(cand, "grounding_metadata", None)
    if gm and gm.grounding_chunks:
        for ch in gm.grounding_chunks:
            if ch.web and ch.web.uri and ch.web.uri not in visti:
                visti.add(ch.web.uri)
                titolo = ch.web.title or ch.web.uri
                fonti.append((titolo, ch.web.uri))

    parti = ["☀️ <b>Buongiorno! Novità di oggi su AI e produttività</b>\n",
             _markdown_to_html(html_lib.escape(testo))]
    if fonti:
        parti.append("\n\n📎 <b>Fonti:</b>")
        for titolo, uri in fonti[:10]:
            parti.append(f'\n• <a href="{html_lib.escape(uri)}">{html_lib.escape(titolo)}</a>')
    return "".join(parti)


def send_daily_news(chat_id: int) -> None:
    try:
        message = build_digest()
    except Exception as exc:
        telegram_api.send_message(
            chat_id, f"Non sono riuscito a preparare le notizie di oggi ({exc})."
        )
        return
    telegram_api.send_html(chat_id, message)
