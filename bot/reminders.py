"""Promemoria per eventi imminenti del calendario.

Pensato per girare ogni ~15 minuti (scheduled). Notifica gli eventi che
iniziano tra 15 e 30 minuti da adesso: con esecuzioni ogni 15 minuti, ogni
evento cade in un'unica finestra, quindi si evita di mandare doppioni senza
bisogno di memorizzare uno stato.
"""
import html as html_lib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
from bot import telegram_api
from bot.tools import calendar_tools


def send_upcoming_reminders(chat_id: int) -> None:
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    window_start = now + timedelta(minutes=15)
    window_end = now + timedelta(minutes=30)

    events = (
        calendar_tools._service().events()
        .list(calendarId="primary", timeMin=now.isoformat(), timeMax=window_end.isoformat(),
              singleEvents=True, orderBy="startTime")
        .execute().get("items", [])
    )
    for ev in events:
        start_iso = ev["start"].get("dateTime")
        if not start_iso:
            continue  # eventi tutto-il-giorno: niente promemoria a orario
        start = datetime.fromisoformat(start_iso)
        if window_start <= start < window_end:
            titolo = html_lib.escape(ev.get("summary", "(senza titolo)"))
            luogo = ev.get("location", "")
            testo = f"⏰ Tra poco ({start.strftime('%H:%M')}): <b>{titolo}</b>"
            if luogo:
                testo += f"\n📍 {html_lib.escape(luogo)}"
            telegram_api.send_html(chat_id, testo)
