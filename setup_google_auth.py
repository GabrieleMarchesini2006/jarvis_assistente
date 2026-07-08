"""Da eseguire UNA VOLTA sul tuo PC (non su PythonAnywhere).

Apre il browser per autorizzare l'accesso a Calendar e Gmail e genera
token.json, che poi va caricato nella cartella del progetto su PythonAnywhere.

Prerequisito: credentials.json scaricato da Google Cloud Console
(credenziali OAuth di tipo "App desktop") nella cartella del progetto.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

import config
from bot.google_auth import SCOPES


def main():
    if not config.GOOGLE_CREDENTIALS_FILE.exists():
        raise SystemExit(
            "credentials.json non trovato.\n"
            "Scaricalo da Google Cloud Console (OAuth client di tipo 'Desktop app') "
            "e mettilo nella cartella del progetto."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_CREDENTIALS_FILE), SCOPES
    )
    creds = flow.run_local_server(port=0)
    config.GOOGLE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nFatto! Token salvato in {config.GOOGLE_TOKEN_FILE}")
    print("Carica questo file su PythonAnywhere nella cartella del progetto.")


if __name__ == "__main__":
    main()
