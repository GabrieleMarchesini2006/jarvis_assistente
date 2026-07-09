"""Web app Flask che riceve gli update di Telegram via webhook.

Su PythonAnywhere questa è l'app WSGI: il webhook di Telegram punta a
https://<tuoutente>.pythonanywhere.com/webhook/<WEBHOOK_SECRET>
"""
import logging
from collections import deque

from flask import Flask, abort, request
from google.genai import types

import config
from bot import agent, history, pending, telegram_api, voice
from bot.tools import calendar_tools, gmail_tools

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
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.WEBHOOK_SECRET:
        abort(403)

    update = request.get_json(silent=True) or {}
    update_id = update.get("update_id")
    if update_id is None or update_id in _seen_updates:
        return "ok"
    _seen_updates.append(update_id)

    if "callback_query" in update:
        _handle_callback(update["callback_query"])
        return "ok"

    message = update.get("message")
    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    user_id = message.get("from", {}).get("id")
    if config.ALLOWED_USER_ID and user_id != config.ALLOWED_USER_ID:
        telegram_api.send_message(chat_id, "Questo è un bot privato.")
        return "ok"

    try:
        _handle_message(chat_id, message)
    except agent.QuotaExhausted:
        telegram_api.send_message(
            chat_id,
            "⚠️ Ho esaurito la quota gratuita giornaliera di Gemini. "
            "Riprova più tardi (si azzera a mezzanotte, ora del Pacifico).",
        )
    except Exception:
        log.exception("Errore nel processare il messaggio")
        telegram_api.send_message(chat_id, "Si è verificato un errore, riprova tra poco.")
    return "ok"


def _handle_callback(cb: dict) -> None:
    """Gestisce il click sui bottoni di conferma (invio email, eliminazione evento)."""
    user_id = cb.get("from", {}).get("id")
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    telegram_api.answer_callback(cb["id"])
    telegram_api.edit_message_reply_markup(chat_id, message_id)

    if config.ALLOWED_USER_ID and user_id != config.ALLOWED_USER_ID:
        return

    decision, _, token = data.partition(":")
    action = pending.pop(token)
    if action is None:
        telegram_api.send_message(chat_id, "Questa richiesta è scaduta.")
        return
    if decision == "no":
        telegram_api.send_message(chat_id, "Annullato. ✅")
        return

    try:
        if action["type"] == "send_email":
            result = gmail_tools.do_send_email(action["to"], action["subject"], action["body"])
        elif action["type"] == "delete_event":
            result = calendar_tools.do_delete_event(action["event_id"])
        else:
            result = "Azione sconosciuta."
        telegram_api.send_message(chat_id, result)
    except Exception:
        log.exception("Errore nell'eseguire l'azione confermata")
        telegram_api.send_message(chat_id, "Non sono riuscito a completare l'azione.")


def _handle_message(chat_id: int, message: dict) -> None:
    telegram_api.send_chat_action(chat_id, "typing")
    media_parts = None
    text = ""

    if "voice" in message:
        try:
            text = voice.transcribe_voice(message["voice"]["file_id"])
        except Exception:
            log.exception("Trascrizione vocale fallita")
            telegram_api.send_message(chat_id, "Non sono riuscito a capire il vocale, riprova o scrivi.")
            return
        telegram_api.send_message(chat_id, f"🎙 Ho capito: “{text}”")
    elif "photo" in message:
        # Telegram manda più risoluzioni: prendiamo la più grande (l'ultima).
        file_id = message["photo"][-1]["file_id"]
        try:
            img = telegram_api.download_bytes(file_id)
        except Exception:
            log.exception("Download foto fallito")
            telegram_api.send_message(chat_id, "Non sono riuscito a scaricare l'immagine.")
            return
        media_parts = [types.Part.from_bytes(data=img, mime_type="image/jpeg")]
        text = message.get("caption", "") or "Guarda questa immagine e aiutami di conseguenza."
    elif "text" in message:
        text = message["text"]
    else:
        telegram_api.send_message(chat_id, "Per ora capisco testo, vocali e foto.")
        return

    stripped = text.strip()
    if stripped == "/start":
        telegram_api.send_message(
            chat_id,
            "Ciao! Sono Jarvis 🤖\nGestisco il tuo *Calendar*, la tua *Gmail* e il tuo "
            "*Notion*. Scrivimi, mandami un vocale o una foto.\n\n"
            "Comandi:\n/news – le notizie di oggi su AI e produttività\n"
            "/reset – azzera la memoria della conversazione",
        )
        return
    if stripped == "/reset":
        history.clear(chat_id)
        telegram_api.send_message(chat_id, "Memoria della conversazione azzerata. ✅")
        return
    if stripped == "/news":
        from bot import news
        news.send_daily_news(chat_id)
        return

    telegram_api.send_chat_action(chat_id, "typing")
    reply = agent.run_agent(chat_id, text, media_parts=media_parts)
    telegram_api.send_message(chat_id, reply)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
