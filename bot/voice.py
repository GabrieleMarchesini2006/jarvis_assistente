"""Trascrizione dei messaggi vocali di Telegram (OGG/Opus -> testo italiano).

Usa il riconoscimento vocale gratuito di Google tramite la libreria
SpeechRecognition. La conversione OGG -> WAV richiede ffmpeg, che su
PythonAnywhere è già installato.
"""
import tempfile
from pathlib import Path

import speech_recognition as sr
from pydub import AudioSegment

from bot import telegram_api


def transcribe_voice(file_id: str) -> str:
    """Scarica il vocale da Telegram e restituisce il testo trascritto (italiano)."""
    with tempfile.TemporaryDirectory() as tmp:
        ogg_path = Path(tmp) / "voice.ogg"
        wav_path = Path(tmp) / "voice.wav"

        telegram_api.download_file(file_id, str(ogg_path))
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(wav_path)) as source:
            audio = recognizer.record(source)

        return recognizer.recognize_google(audio, language="it-IT")
