"""Client minimale per la Bot API di Telegram (solo requests, nessuna libreria pesante)."""
import time

import requests

import config

API_BASE = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"

# Telegram accetta messaggi fino a 4096 caratteri.
MAX_MESSAGE_LEN = 4096

# Il proxy del piano free di PythonAnywhere ogni tanto restituisce 503: riproviamo.
MAX_RETRIES = 4


def _post(endpoint: str, payload: dict, timeout: int = 30):
    """POST con qualche tentativo, per resistere ai 503 temporanei del proxy."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(f"{API_BASE}/{endpoint}", json=payload, timeout=timeout)
            if resp.ok:
                return resp
            # 429/5xx: aspetta e riprova; 4xx client-side: inutile insistere.
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(1.5 * (attempt + 1))
    if last_exc:
        raise last_exc
    return resp


def send_message(chat_id: int, text: str) -> None:
    """Invia un messaggio, spezzandolo se supera il limite di Telegram."""
    for start in range(0, len(text), MAX_MESSAGE_LEN):
        chunk = text[start:start + MAX_MESSAGE_LEN]
        resp = _post("sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"})
        if resp is None or not resp.ok:
            # Il Markdown malformato fa fallire l'invio: riprova come testo semplice.
            _post("sendMessage", {"chat_id": chat_id, "text": chunk})


def _split_on_lines(text: str, limit: int) -> list:
    """Spezza il testo in blocchi <= limit senza mai tagliare a metà una riga
    (così non si spezza un tag HTML come <a>...</a>)."""
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit and current:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    return chunks


def send_html(chat_id: int, html: str) -> None:
    """Invia un messaggio in formato HTML (per link cliccabili affidabili)."""
    for chunk in _split_on_lines(html, MAX_MESSAGE_LEN):
        _post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })


def send_chat_action(chat_id: int, action: str = "typing") -> None:
    try:
        requests.post(
            f"{API_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": action},
            timeout=10,
        )
    except requests.RequestException:
        pass  # azione puramente cosmetica (nessun retry: non è importante)


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
