"""Entry point per la revisione settimanale PARA (task in ritardo e in arrivo).

Lanciato dal workflow GitHub Actions la domenica sera.
Test manuale: python weekly_review.py
"""
import config
from bot.briefing import send_weekly_review

if __name__ == "__main__":
    if not config.ALLOWED_USER_ID:
        raise SystemExit("ALLOWED_USER_ID non configurato.")
    send_weekly_review(config.ALLOWED_USER_ID)
    print("Revisione settimanale inviata.")
