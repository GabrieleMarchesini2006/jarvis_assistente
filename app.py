"""Web app Flask che riceve gli update di Telegram via webhook.

Su PythonAnywhere questa è l'app WSGI: il webhook di Telegram punta a
https://<tuoutente>.pythonanywhere.com/webhook/<WEBHOOK_SECRET>
"""
import logging
from collections import deque

from flask import Flask, abort, request

import config
from bot import agent, history, telegram_api, voice

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")

app = Flask(__name__)

# Telegram ritenta la consegna se non rispondiamo in fretta: teniamo traccia
# degli update già visti per non processarli due volte.
_seen_updates = deque(maxlen=300)


@app.route("/")
def index():
    return "Jarvis è attivo."


@app.route(f"/webhook/{config.WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    # Verifica il secret token impostato da set_webhook.py
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.WEBHOOK_SECRET:
        abort(403)

    update = request.get_json(silent=True) or {}
    update_id = update.get("update_id")
    if update_id is None or update_id in _seen_updates:
        return "ok"
    _seen_updates.append(update_id)

    message = update.get("message")
    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    user_id = message.get("from", {}).get("id")

    # Il bot è personale: risponde solo all'utente autorizzato.
    if config.ALLOWED_USER_ID and user_id != config.ALLOWED_USER_ID:
        telegram_api.send_message(chat_id, "Questo è un bot privato.")
        return "ok"

    try:
        _handle_message(chat_id, message)
    except Exception:
        log.exception("Errore nel processare il messaggio")
        telegram_api.send_message(
            chat_id, "Si è verificato un errore, riprova tra poco."
        )
    return "ok"


def _handle_message(chat_id: int, message: dict) -> None:
    telegram_api.send_chat_action(chat_id, "typing")

    if "voice" in message:
        try:
            text = voice.transcribe_voice(message["voice"]["file_id"])
        except Exception:
            log.exception("Trascrizione vocale fallita")
            telegram_api.send_message(
                chat_id, "Non sono riuscito a capire il vocale, puoi ripetere o scrivere?"
            )
            return
        telegram_api.send_message(chat_id, f"🎙 Ho capito: “{text}”")
    elif "text" in message:
        text = message["text"]
    else:
        telegram_api.send_message(chat_id, "Per ora capisco solo testo e vocali.")
        return

    if text.strip() == "/start":
        telegram_api.send_message(
            chat_id,
            "Ciao! Sono Jarvis 🤖\nPosso gestire il tuo *Calendar*, la tua *Gmail* "
            "e il tuo *Notion*. Scrivimi o mandami un vocale.\n"
            "Comandi: /reset per azzerare la memoria della conversazione.",
        )
        return
    if text.strip() == "/reset":
        history.clear(chat_id)
        telegram_api.send_message(chat_id, "Memoria della conversazione azzerata. ✅")
        return

    telegram_api.send_chat_action(chat_id, "typing")
    try:
        reply = agent.run_agent(chat_id, text)
    except agent.QuotaExhausted:
        telegram_api.send_message(
            chat_id,
            "⚠️ Ho esaurito la quota gratuita giornaliera di Gemini. "
            "Riprova più tardi (si azzera a mezzanotte, ora del Pacifico).",
        )
        return
    telegram_api.send_message(chat_id, reply)


if __name__ == "__main__":
    # Solo per test in locale (in produzione gira sotto WSGI su PythonAnywhere).
    app.run(port=5000, debug=True)
