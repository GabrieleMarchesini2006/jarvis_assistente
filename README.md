# Jarvis — Assistente personale su Telegram (24h)

Bot Telegram che funziona da agente AI: capisce **testo, vocali e foto** in italiano e agisce su **Google Calendar**, **Gmail** e **Notion**. Il cervello è **Gemini** (Google) con *function calling* — **gratis** con la API key di Google AI Studio — e decide da solo quali strumenti usare per eseguire quello che gli chiedi.

Cosa sa fare:
- **Calendar**: leggere, creare, **modificare** ed eliminare eventi. «Sposta il dentista alle 17».
- **Gmail**: cercare, leggere e inviare email (con **conferma a bottoni** prima dell'invio).
- **Notion** (sistema PARA): aggiungere righe ai database, interrogarli per scadenza, **completare/aggiornare** task. «Segna fatto tagliare i capelli».
- **Memoria a lungo termine**: ricorda fatti su di te tra le conversazioni. «Ricordati che sono vegetariano».
- **Vocali e foto**: capisce i messaggi vocali e le immagini (le legge con Gemini multimodale).
- **Automazioni** (via GitHub Actions, gratis): briefing mattutino, revisione settimanale, promemoria eventi.

## Architettura

```
Telegram ──webhook──▶ Flask (app.py) ──▶ agent.py (Gemini + function calling)
                                            ├── tools/calendar_tools.py  (Calendar: CRUD)
                                            ├── tools/gmail_tools.py     (Gmail, conferma bottoni)
                                            ├── tools/notion_tools.py    (Notion database PARA)
                                            └── tools/memory_tools.py    (memoria lungo termine)
        vocali/foto ──▶ Gemini multimodale (voice.py / immagini inline)

GitHub Actions (schedulati, gratis):
   daily_briefing.py   → eventi + task + notizie ogni mattina
   weekly_review.py    → task in ritardo/in arrivo, domenica sera
   reminders_check.py  → promemoria eventi imminenti, ogni 15 min
```

Su PythonAnywhere non si possono tenere processi sempre accesi (polling), ma una **web app Flask** sì: per questo il bot usa il **webhook** di Telegram, che è comunque attivo 24h. Le automazioni girano su **GitHub Actions** (schedulate) perché i Tasks di PythonAnywhere sono a pagamento.

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
| `/news` | Le notizie di oggi su AI e produttività, a richiesta |
| `/reset` | Azzera la memoria della conversazione |

Tutto il resto è linguaggio naturale: scrivi, manda un vocale o una foto.

## 5. Automazioni (GitHub Actions, gratis)

Tre workflow schedulati inviano messaggi automatici su Telegram senza bisogno che il bot sia "sveglio":

| Workflow | Quando | Cosa manda |
|---|---|---|
| `morning-briefing.yml` | ogni giorno 06:00 UTC (8:00 IT estate) | eventi di oggi + task in scadenza + notizie |
| `weekly-review.yml` | domenica 18:00 UTC | task in ritardo e dei prossimi 7 giorni |
| `reminders.yml` | ogni 15 min | avviso per eventi che iniziano tra 15-30 min |

**Per attivarli** servono dei **secret** nel repository GitHub (Settings → Secrets and variables → Actions → New repository secret):

| Secret | Valore |
|---|---|
| `GEMINI_API_KEY` | la tua chiave Gemini |
| `TELEGRAM_BOT_TOKEN` | il token del bot |
| `ALLOWED_USER_ID` | il tuo id Telegram |
| `NOTION_TOKEN` | il token dell'integrazione Notion |
| `NOTION_PARENT_PAGE_ID` | l'id della pagina radice Notion |
| `GOOGLE_TOKEN_JSON` | **tutto il contenuto** del file `token.json` (aprilo, copia-incolla) |

Per provarli subito senza aspettare l'orario: tab **Actions** → scegli il workflow → **Run workflow**.

> ⚠️ Gli orari dei workflow sono in **UTC** e non seguono l'ora legale. Da fine ottobre arriveranno un'ora prima; per correggerli cambia il `cron` nei file `.github/workflows/*.yml`. GitHub Actions inoltre può ritardare i job schedulati di qualche minuto.

## Risoluzione problemi

- **Il bot non risponde** → tab *Web* → *Error log* su PythonAnywhere. Controlla anche `https://api.telegram.org/bot<TOKEN>/getWebhookInfo` (campo `last_error_message`).
- **Errore Google "invalid_grant"** → il token è scaduto/revocato: rilancia `setup_google_auth.py` in locale, ricarica `token.json` sul server e aggiorna il secret `GOOGLE_TOKEN_JSON` su GitHub.
- **Notion "object not found"** → la pagina non è condivisa con l'integrazione (menu ⋯ → Connections).
- **Automazioni non partono** → tab *Actions* su GitHub: apri l'ultimo run e leggi il log. Di solito è un secret mancante o la quota Gemini.

## Sicurezza

- Il bot risponde **solo** all'`ALLOWED_USER_ID` configurato.
- Il webhook è protetto da un path segreto **e** dall'header `X-Telegram-Bot-Api-Secret-Token`.
- `.env`, `token.json` e `credentials.json` non vanno mai committati (vedi `.gitignore`).
