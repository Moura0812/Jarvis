import base64
import io
import os
import unicodedata
import wave

import numpy as np
import sounddevice as sd
from openai import OpenAI

cliente = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODELO = "gemini-3.5-flash-lite"
TAXA = 16000
LIMIAR = 500
IGNORAR = ("vazio", "silencio", "sem fala", "nenhuma fala")


def gravar(segundos=5):
    print("Ouvindo...")
    audio = sd.rec(int(segundos * TAXA), samplerate=TAXA, channels=1, dtype="int16")
    sd.wait()
    return audio


def tem_fala(audio):
    volume = float(np.abs(audio.astype(np.int32)).max())
    return volume >= LIMIAR


def para_base64(audio):
    memoria = io.BytesIO()
    with wave.open(memoria, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(audio.tobytes())
    return base64.b64encode(memoria.getvalue()).decode("utf-8")


def sem_acento(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def limpar_texto(texto):
    t = sem_acento(texto).strip().strip(".").strip()
    if t in IGNORAR:
        return ""
    return texto.strip()


def ouvir(segundos=5):
    audio = gravar(segundos)
    if not tem_fala(audio):
        return ""
    pedido = "Transcreva este audio em portugues. Responda apenas com o texto falado, sem comentarios. Se nao houver fala, responda vazio."
    resposta = cliente.chat.completions.create(
        model=MODELO,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": pedido},
                    {"type": "input_audio", "input_audio": {"data": para_base64(audio), "format": "wav"}},
                ],
            }
        ],
    )
    return limpar_texto(resposta.choices[0].message.content)


if __name__ == "__main__":
    print("Voce disse:", ouvir())
