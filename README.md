# Jarvis — Assistente personale su Telegram (24h)

Bot Telegram che funziona da agente AI: capisce **testo e vocali** in italiano e agisce su **Google Calendar**, **Gmail** e **Notion**. Il cervello è **Gemini** (Google) con *function calling* — **gratis** con la API key di Google AI Studio — e decide da solo quali strumenti usare per eseguire quello che gli chiedi.

Esempi di cosa puoi chiedergli:
- «Che impegni ho domani?» / «Crea un evento venerdì alle 15 dal dentista»
- «Ho email non lette?» / «Rispondi a Mario che confermo per giovedì»
- «Salvami su Notion questa idea…» / «Cosa c'è scritto nella pagina Spesa?»

## Architettura

```
Telegram ──webhook──▶ Flask (app.py) ──▶ agent.py (Gemini + function calling)
                                            ├── tools/calendar_tools.py  (Google Calendar)
                                            ├── tools/gmail_tools.py     (Gmail)
                                            └── tools/notion_tools.py    (Notion)
              vocali ──▶ voice.py (ffmpeg + Google Speech, gratis)
```

Su PythonAnywhere non si possono tenere processi sempre accesi (polling), ma una **web app Flask** sì: per questo il bot usa il **webhook** di Telegram, che è comunque attivo 24h.

---

## 1. Prerequisiti (chiavi e account)

1. **Bot Telegram** — scrivi a [@BotFather](https://t.me/BotFather) → `/newbot` → copia il token.
2. **Il tuo ID Telegram** — scrivi a [@userinfobot](https://t.me/userinfobot) e copia l'id numerico.
3. **Chiave Gemini (gratis)** — vai su [aistudio.google.com/apikey](https://aistudio.google.com/apikey), accedi con l'account Google e clicca *Create API key*. Il piano gratuito non richiede carta di credito.
4. **Notion** — su [notion.so/my-integrations](https://www.notion.so/my-integrations) crea una integrazione interna e copia il token. Poi apri la pagina Notion che vuoi usare come "radice" → menu ⋯ → *Connections* → aggiungi la tua integrazione. L'ID della pagina è la parte finale dell'URL.
5. **Google Cloud** (per Calendar + Gmail):
   - Vai su [console.cloud.google.com](https://console.cloud.google.com), crea un progetto.
   - Abilita le API **Google Calendar API** e **Gmail API**.
   - *APIs & Services → OAuth consent screen*: tipo **External**, aggiungi la tua email come **test user**.
   - *Credentials → Create credentials → OAuth client ID → Desktop app* → scarica il JSON e salvalo come `credentials.json` nella cartella del progetto.

## 2. Configurazione in locale

```bash
cd jarvis_assistente
python -m venv venv
venv\Scripts\activate          # Windows (su Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env         # e compila tutti i valori
python setup_google_auth.py    # apre il browser: autorizza Calendar e Gmail
```

`setup_google_auth.py` genera `token.json`: servirà su PythonAnywhere.

Test in locale (facoltativo): `python app.py` e usa un tunnel tipo ngrok per il webhook — oppure salta direttamente al deploy.

## 3. Deploy su PythonAnywhere

> ℹ️ **Piano gratuito**: i free account di PythonAnywhere possono fare richieste esterne solo verso una whitelist di domini, ma tutto ciò che serve a questo bot (`api.telegram.org`, `*.googleapis.com` — che copre anche Gemini — e `api.notion.com`) è incluso. Se in futuro una chiamata fallisse con errore di proxy, controlla la [whitelist](https://www.pythonanywhere.com/whitelist/) o passa al piano Hacker (~5$/mese).

1. **Carica il codice**: dalla dashboard → *Files* carica la cartella del progetto (oppure `git clone` dalla console Bash). Assicurati di caricare anche `.env` e `token.json` (NON sono nel repository per sicurezza).

2. **Crea il virtualenv** (console Bash su PythonAnywhere):
   ```bash
   mkvirtualenv jarvis --python=python3.10
   cd ~/jarvis_assistente
   pip install -r requirements.txt
   ```

3. **Crea la web app**: tab *Web* → *Add a new web app* → **Manual configuration** → Python 3.10.
   - **Virtualenv**: `/home/TUOUTENTE/.virtualenvs/jarvis`
   - **Source code**: `/home/TUOUTENTE/jarvis_assistente`

4. **Modifica il file WSGI** (link nel tab Web) sostituendo tutto con:
   ```python
   import sys
   sys.path.insert(0, "/home/TUOUTENTE/jarvis_assistente")

   from app import app as application
   ```

5. **Reload** della web app (bottone verde). Visita `https://TUOUTENTE.pythonanywhere.com` → deve rispondere «Jarvis è attivo.»

6. **Registra il webhook** (dalla console Bash di PythonAnywhere, con il virtualenv attivo):
   ```bash
   cd ~/jarvis_assistente
   python set_webhook.py https://TUOUTENTE.pythonanywhere.com
   ```

7. Scrivi `/start` al tuo bot su Telegram. 🎉

## 4. Comandi del bot

| Comando | Effetto |
|---|---|
| `/start` | Messaggio di benvenuto |
| `/reset` | Azzera la memoria della conversazione |

Tutto il resto è linguaggio naturale, scritto o vocale.

## Risoluzione problemi

- **Il bot non risponde** → tab *Web* → *Error log* su PythonAnywhere. Controlla anche `https://api.telegram.org/bot<TOKEN>/getWebhookInfo` (campo `last_error_message`).
- **Errore Google "invalid_grant"** → il token è scaduto/revocato: rilancia `setup_google_auth.py` in locale e ricarica `token.json`.
- **Notion "object not found"** → la pagina non è condivisa con l'integrazione (menu ⋯ → Connections).
- **Vocali non trascritti** → verifica che ffmpeg sia disponibile (`ffmpeg -version` in console; su PythonAnywhere c'è di default).

## Sicurezza

- Il bot risponde **solo** all'`ALLOWED_USER_ID` configurato.
- Il webhook è protetto da un path segreto **e** dall'header `X-Telegram-Bot-Api-Secret-Token`.
- `.env`, `token.json` e `credentials.json` non vanno mai committati (vedi `.gitignore`).
