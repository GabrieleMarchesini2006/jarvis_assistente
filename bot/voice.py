"""Trascrizione dei messaggi vocali di Telegram tramite Gemini.

Gemini capisce l'audio direttamente: niente ffmpeg né librerie di
riconoscimento vocale da installare, e la qualità sull'italiano è migliore.
"""
from google import genai
from google.genai import types

import config
from bot import telegram_api

client = genai.Client(api_key=config.GEMINI_API_KEY)


def transcribe_voice(file_id: str) -> str:
    """Scarica il vocale da Telegram e restituisce il testo trascritto."""
    audio_bytes = telegram_api.download_bytes(file_id)
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[
            "Trascrivi esattamente questo audio in italiano. "
            "Restituisci SOLO il testo trascritto, senza commenti.",
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
        ],
    )
    return (resp.text or "").strip()
