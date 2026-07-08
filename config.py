"""Configurazione centrale: carica le variabili dal file .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# ID numerico dell'utente Telegram autorizzato (il tuo). Il bot ignora tutti gli altri.
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))
# Stringa segreta usata nel path del webhook e come secret_token Telegram.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "cambiami")

# --- Gemini (il "cervello" dell'agente, gratis via Google AI Studio) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# flash-lite ha un limite gratuito molto più alto di flash (ideale per il bot).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# --- Notion ---
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
# Pagina Notion sotto cui creare le nuove pagine (ID della pagina "radice").
NOTION_PARENT_PAGE_ID = os.environ.get("NOTION_PARENT_PAGE_ID", "")

# --- Google (Calendar + Gmail) ---
GOOGLE_CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # scaricato da Google Cloud
GOOGLE_TOKEN_FILE = BASE_DIR / "token.json"              # generato da setup_google_auth.py
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Rome")

# --- Percorsi dati ---
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
