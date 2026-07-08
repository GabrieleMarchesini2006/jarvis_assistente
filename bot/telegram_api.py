"""Client minimale per la Bot API di Telegram (solo requests, nessuna libreria pesante)."""
import requests

import config

API_BASE = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"

# Telegram accetta messaggi fino a 4096 caratteri.
MAX_MESSAGE_LEN = 4096


def send_message(chat_id: int, text: str) -> None:
    """Invia un messaggio, spezzandolo se supera il limite di Telegram."""
    for start in range(0, len(text), MAX_MESSAGE_LEN):
        chunk = text[start:start + MAX_MESSAGE_LEN]
        resp = requests.post(
            f"{API_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            timeout=30,
        )
        if not resp.ok:
            # Il Markdown malformato fa fallire l'invio: riprova come testo semplice.
            requests.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": chunk},
                timeout=30,
            )


def send_chat_action(chat_id: int, action: str = "typing") -> None:
    try:
        requests.post(
            f"{API_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": action},
            timeout=10,
        )
    except requests.RequestException:
        pass  # azione puramente cosmetica


def download_file(file_id: str, dest_path: str) -> str:
    """Scarica un file di Telegram (es. un vocale) e lo salva su dest_path."""
    info = requests.get(
        f"{API_BASE}/getFile", params={"file_id": file_id}, timeout=30
    ).json()
    file_path = info["result"]["file_path"]
    data = requests.get(f"{FILE_BASE}/{file_path}", timeout=60)
    data.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(data.content)
    return dest_path
