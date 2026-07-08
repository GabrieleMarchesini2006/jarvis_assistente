"""L'agente: Gemini con function calling su Notion, Google Calendar e Gmail.

Loop agentico manuale: Gemini decide quali tool chiamare, noi li eseguiamo
e gli rimandiamo i risultati finché non produce la risposta finale.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

import config
from bot import history
from bot.tools import TOOL_DEFINITIONS, execute_tool

client = genai.Client(api_key=config.GEMINI_API_KEY)

MAX_AGENT_ITERATIONS = 15

SYSTEM_PROMPT = """Sei Jarvis, l'assistente personale di Gabriele su Telegram. Rispondi sempre in italiano, in modo diretto e conciso (i messaggi arrivano su Telegram: niente muri di testo).

Hai accesso a questi strumenti dell'utente:
- Google Calendar: leggere, creare ed eliminare eventi.
- Gmail: cercare, leggere e inviare email.
- Notion: cercare, leggere, creare pagine e aggiungere contenuti.

Linee guida:
- Usa gli strumenti quando servono, senza chiedere permesso per le operazioni di sola lettura.
- Per azioni difficili da annullare (inviare email, eliminare eventi) chiedi conferma prima, a meno che l'utente non l'abbia già chiesta esplicitamente in modo completo.
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

GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[GEMINI_TOOLS],
)


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


def run_agent(chat_id: int, user_text: str) -> str:
    """Processa un messaggio dell'utente e restituisce la risposta finale."""
    user_content = f"{_now_line()}\n{user_text}"
    contents = _history_to_contents(chat_id)
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_content)])
    )

    response = None
    for _ in range(MAX_AGENT_ITERATIONS):
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=contents,
            config=GENERATION_CONFIG,
        )

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
                output = execute_tool(call.name, dict(call.args or {}))
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

    history.append(chat_id, user_text, final_text)
    return final_text
