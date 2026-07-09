"""Briefing mattutino e revisione settimanale.

Assembla in un unico messaggio Telegram gli impegni del giorno (Calendar),
le task in scadenza (Notion) e le notizie (news.py).
"""
import html as html_lib
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config
from bot import news, telegram_api
from bot.tools import calendar_tools, notion_tools


def _tz():
    return ZoneInfo(config.TIMEZONE)


def _fmt_ora(iso: str) -> str:
    """Estrae HH:MM da un datetime ISO; '' se è un evento tutto il giorno (solo data)."""
    if "T" not in iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return ""


def today_events_html() -> str:
    now = datetime.now(_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = (
        calendar_tools._service().events()
        .list(calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
              singleEvents=True, orderBy="startTime")
        .execute().get("items", [])
    )
    if not events:
        return "📅 <b>Oggi</b>\nNessun evento in calendario."
    righe = ["📅 <b>Oggi</b>"]
    for ev in events:
        ora = _fmt_ora(ev["start"].get("dateTime", ev["start"].get("date", "")))
        titolo = html_lib.escape(ev.get("summary", "(senza titolo)"))
        righe.append(f"• {ora + ' ' if ora else ''}{titolo}")
    return "\n".join(righe)


def due_tasks_html() -> str:
    """Task in scadenza fino a oggi (comprese le arretrate), non completate."""
    oggi = date.today().isoformat()
    try:
        raw = notion_tools.query_database("Tasks", due_before=oggi, exclude_completed=True, limit=15)
        rows = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return ""
    if not isinstance(rows, list) or not rows:
        return "✅ <b>Task da fare</b>\nNiente in scadenza. Sei in pari!"
    righe = ["✅ <b>Task da fare</b>"]
    for r in rows:
        titolo = html_lib.escape(str(r.get("titolo", "")))
        scad = r.get("scadenza", "")
        marca = " ⚠️" if scad and scad < oggi else ""
        righe.append(f"• {titolo}{marca}")
    return "\n".join(righe)


def send_morning_briefing(chat_id: int) -> None:
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    now = datetime.now(_tz())
    intro = f"☀️ <b>Buongiorno!</b> È {giorni[now.weekday()]} {now.strftime('%d/%m')}."

    sezioni = [intro]
    for fn in (today_events_html, due_tasks_html):
        try:
            sezioni.append(fn())
        except Exception:
            pass  # una sezione che fallisce non deve bloccare le altre
    try:
        sezioni.append("🗞 <b>Notizie</b>\n" + news.news_section_html())
    except Exception:
        pass

    telegram_api.send_html(chat_id, "\n\n".join(sezioni))


def send_weekly_review(chat_id: int) -> None:
    oggi = date.today()
    fra_7 = (oggi + timedelta(days=7)).isoformat()
    sezioni = ["📊 <b>Revisione settimanale</b>"]

    # In arretrato (scadute e non completate)
    try:
        arretrate = json.loads(notion_tools.query_database(
            "Tasks", due_before=oggi.isoformat(), exclude_completed=True, limit=20))
        if arretrate:
            righe = ["⚠️ <b>In ritardo</b>"]
            for r in arretrate:
                righe.append("• " + html_lib.escape(str(r.get("titolo", ""))))
            sezioni.append("\n".join(righe))
    except Exception:
        pass

    # In arrivo nei prossimi 7 giorni
    try:
        prossime = json.loads(notion_tools.query_database(
            "Tasks", due_after=oggi.isoformat(), due_before=fra_7, exclude_completed=True, limit=20))
        if prossime:
            righe = ["🗓 <b>Prossimi 7 giorni</b>"]
            for r in prossime:
                scad = r.get("scadenza", "")
                righe.append(f"• {html_lib.escape(str(r.get('titolo', '')))}"
                             + (f" — {scad}" if scad else ""))
            sezioni.append("\n".join(righe))
    except Exception:
        pass

    if len(sezioni) == 1:
        sezioni.append("Nessuna task in ritardo o in arrivo. Ottimo lavoro! 🎉")
    telegram_api.send_html(chat_id, "\n\n".join(sezioni))
