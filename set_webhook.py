"""Registra il webhook del bot su Telegram.

Da eseguire una volta (dal PC o dalla console di PythonAnywhere) DOPO che la
web app è online:

    python set_webhook.py https://tuoutente.pythonanywhere.com
"""
import sys

import requests

import config


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python set_webhook.py https://tuoutente.pythonanywhere.com")
    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/webhook/{config.WEBHOOK_SECRET}"

    resp = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setWebhook",
        json={
            "url": webhook_url,
            "secret_token": config.WEBHOOK_SECRET,
            "drop_pending_updates": True,
        },
        timeout=30,
    )
    print(resp.json())
    if resp.json().get("ok"):
        print(f"\nWebhook registrato: {webhook_url}")


if __name__ == "__main__":
    main()
