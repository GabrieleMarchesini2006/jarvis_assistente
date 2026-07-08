"""Credenziali Google condivise tra Calendar e Gmail.

Il file token.json viene generato UNA VOLTA in locale con setup_google_auth.py
e poi caricato su PythonAnywhere. Qui viene solo letto e rinfrescato.
"""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import config

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_credentials() -> Credentials:
    if not config.GOOGLE_TOKEN_FILE.exists():
        raise RuntimeError(
            "token.json mancante: esegui setup_google_auth.py sul tuo PC "
            "e carica il file generato nella cartella del progetto."
        )
    creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        config.GOOGLE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds
