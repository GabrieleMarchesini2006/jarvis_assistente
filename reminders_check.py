"""Entry point per i promemoria di eventi imminenti.

Lanciato dal workflow GitHub Actions ogni ~15 minuti.
Test manuale: python reminders_check.py
"""
import config
from bot.reminders import send_upcoming_reminders

if __name__ == "__main__":
    if not config.ALLOWED_USER_ID:
        raise SystemExit("ALLOWED_USER_ID non configurato.")
    send_upcoming_reminders(config.ALLOWED_USER_ID)
    print("Controllo promemoria completato.")
