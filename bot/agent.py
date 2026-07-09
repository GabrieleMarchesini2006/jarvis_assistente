"""L'agente: Gemini con function calling su Notion, Google Calendar e Gmail.

Loop agentico manuale: Gemini decide quali tool chiamare, noi li eseguiamo
e gli rimandiamo i risultati finché non produce la risposta finale.
Supporta input di testo, immagini (foto) e memoria a lungo termine.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

import config
from bot import history, memory
from bot.tools import TOOL_DEFINITIONS, execute_tool

client = genai.Client(api_key=config.GEMINI_API_KEY)

MAX_AGENT_ITERATIONS = 15
# Prova prima il modello configurato, poi gli altri come riserva (contro i 429/503).
MODEL_CHAIN = [config.GEMINI_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]

BASE_SYSTEM_PROMPT = """Sei Jarvis, l'assistente personale di Gabriele su Telegram. Rispondi sempre in italiano, in modo diretto e conciso (i messaggi arrivano su Telegram: niente muri di testo).

Hai accesso a questi strumenti dell'utente:
- Google Calendar: leggere, creare, modificare ed eliminare eventi.
- Gmail: cercare, leggere e inviare email.
- Notion: cercare e leggere pagine, aggiungere e aggiornare righe nei suoi database (sistema PARA: Tasks, Projects, Areas, Resources, Archive).
- Memoria: puoi ricordare fatti duraturi sull'utente tra una conversazione e l'altra.

Linee guida:
- Usa gli strumenti quando servono, senza chiedere permesso per le operazioni di sola lettura.
- Quando l'utente ti chiede di creare/modificare un evento o salvare/aggiornare/completare una task, ESEGUI SUBITO l'azione senza chiedere conferma a parole (sono azioni reversibili), poi conferma cosa hai fatto. Non fare domande del tipo "vuoi che lo salvi?" se l'utente te l'ha già chiesto: fallo e basta.
- Le UNICHE azioni per cui serve conferma sono inviare un'email ed eliminare un evento: per quelle usa direttamente il tool, che mostrerà all'utente dei bottoni ✅/❌. Non chiedere tu a parole.
- DOPO ogni azione (creazione/modifica evento, salvataggio su Notion) rispondi SEMPRE con un breve messaggio di conferma, riepilogando cosa hai fatto. Non restare mai in silenzio dopo aver usato un tool.
- Per salvare qualcosa su Notion usa notion_create_entry aggiungendo una riga al database giusto (Tasks per compiti/promemoria, Projects per progetti, Resources per link e articoli). Non creare mai pagine sciolte. Se non sei sicuro dei valori di stato/priorità disponibili, controlla prima con notion_list_databases.
- Quando l'utente chiede le sue task o attività per una data, usa notion_query_database sul database Tasks filtrando per scadenza (Due Date). Per un singolo giorno metti la stessa data in due_after e due_before. Le righe restituite includono un id: usalo con notion_update_entry per segnare una task come completata o cambiarne stato/priorità/scadenza.
- Se crei una task senza che l'utente specifichi lo stato, lascia il valore predefinito (il tool imposta "Next Action").
- Quando impari qualcosa di duraturo e utile sull'utente (preferenze, persone ricorrenti, abitudini, dati fissi), salvalo con memory_save. Non salvare cose banali o temporanee.
- Quando l'utente usa date relative ("domani", "venerdì prossimo"), calcolale a partire dalla data corrente indicata nel messaggio.
- Se un tool restituisce un errore, spiega il problema in modo semplice.
- Formatta le risposte per Telegram: elenchi puntati, grassetto con *asterischi*, niente tabelle."""

# Le definizioni dei tool usano lo schema "input_schema" (stile Anthropic);
# Gemini vuole lo stesso JSON Schema sotto la chiave "parameters".
GEMINI_TOOLS = types.Tool(function_declarations=[
    {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["input_schema"],
    }
    for t in TOOL_DEFINITIONS
])


class QuotaExhausted(Exception):
    """Quota giornaliera gratuita di Gemini esaurita su tutti i modelli."""


def _system_prompt() -> str:
    """Prompt di sistema con la memoria a lungo termine dell'utente."""
    facts = memory.format_facts()
    if facts:
        return BASE_SYSTEM_PROMPT + "\n\nCosa sai sull'utente (memoria):\n" + facts
    return BASE_SYSTEM_PROMPT


def _generate(contents):
    """Chiama Gemini provando i modelli in catena e gestendo i 429."""
    quota_hit = False
    for model in dict.fromkeys(MODEL_CHAIN):  # ordine preservato, senza duplicati
        cfg = types.GenerateContentConfig(
            system_instruction=_system_prompt(), tools=[GEMINI_TOOLS]
        )
        for attempt in range(2):
            try:
                return client.models.generate_content(model=model, contents=contents, config=cfg)
            except genai_errors.ClientError as exc:
                if getattr(exc, "code", None) != 429:
                    raise
                quota_hit = True
                msg = str(exc)
                if "PerDay" in msg or "per day" in msg.lower():
                    break  # quota giornaliera del modello finita: passa al prossimo modello
                if attempt == 0:
                    time.sleep(3)  # limite al minuto: aspetta e riprova
            except genai_errors.ServerError:
                break  # 503/500: prova il prossimo modello
    if quota_hit:
        raise QuotaExhausted()
    raise RuntimeError("Nessun modello Gemini disponibile.")


def _now_line() -> str:
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    return (
        f"(Adesso è {giorni[now.weekday()]} {now.strftime('%d/%m/%Y, ore %H:%M')}, "
        f"fuso {config.TIMEZONE})"
    )


def _history_to_contents(chat_id: int) -> list:
    contents = []
    for msg in history.load(chat_id):
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
        )
    return contents


def run_agent(chat_id: int, user_text: str, media_parts=None) -> str:
    """Processa un messaggio dell'utente (testo + eventuali immagini) e risponde.

    media_parts: lista opzionale di types.Part (es. immagini) da allegare al messaggio.
    """
    context = {"chat_id": chat_id}
    user_content = f"{_now_line()}\n{user_text}"
    parts = [types.Part.from_text(text=user_content)]
    if media_parts:
        parts.extend(media_parts)

    contents = _history_to_contents(chat_id)
    contents.append(types.Content(role="user", parts=parts))

    response = None
    for _ in range(MAX_AGENT_ITERATIONS):
        response = _generate(contents)

        candidate = response.candidates[0]
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if p.function_call]
        if not function_calls:
            break

        # Gemini ha chiesto uno o più tool: eseguili e rimanda i risultati.
        contents.append(candidate.content)
        result_parts = []
        for call in function_calls:
            try:
                output = execute_tool(call.name, dict(call.args or {}), context)
            except Exception as exc:  # l'errore torna a Gemini, che lo spiega all'utente
                output = f"Errore durante l'esecuzione: {exc}"
            result_parts.append(
                types.Part.from_function_response(
                    name=call.name, response={"result": output}
                )
            )
        contents.append(types.Content(role="user", parts=result_parts))

    final_parts = response.candidates[0].content.parts or []
    final_text = "".join(p.text for p in final_parts if p.text).strip() or "Fatto."

    history.append(chat_id, user_text or "[media]", final_text)
    return final_text
