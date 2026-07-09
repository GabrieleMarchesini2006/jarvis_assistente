"""Entry point per il briefing mattutino (eventi + task + notizie).

Lanciato dal workflow GitHub Actions ogni mattina.
Test manuale: python daily_briefing.py
"""
import config
from bot.briefing import send_morning_briefing

if __name__ == "__main__":
    if not config.ALLOWED_USER_ID:
        raise SystemExit("ALLOWED_USER_ID non configurato.")
    send_morning_briefing(config.ALLOWED_USER_ID)
    print("Briefing inviato.")
