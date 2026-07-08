"""Entry point per lo scheduled task giornaliero: invia il digest di notizie.

Su PythonAnywhere: tab Tasks -> aggiungi un task giornaliero che esegue
    /home/GabryMar/.virtualenvs/jarvis/bin/python /home/GabryMar/jarvis_assistente/daily_news.py
all'orario desiderato (in UTC).

Test manuale dalla console Bash:
    workon jarvis && python ~/jarvis_assistente/daily_news.py
"""
import config
from bot.news import send_daily_news

if __name__ == "__main__":
    if not config.ALLOWED_USER_ID:
        raise SystemExit("ALLOWED_USER_ID non configurato nel .env.")
    send_daily_news(config.ALLOWED_USER_ID)
    print("Digest inviato.")
