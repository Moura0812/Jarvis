import base64
import io
import os
import wave

import sounddevice as sd
from openai import OpenAI

cliente = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODELO = "gemini-3.5-flash-lite"
TAXA = 16000


def gravar(segundos=5):
    print("Ouvindo...")
    audio = sd.rec(int(segundos * TAXA), samplerate=TAXA, channels=1, dtype="int16")
    sd.wait()
    memoria = io.BytesIO()
    with wave.open(memoria, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(audio.tobytes())
    return base64.b64encode(memoria.getvalue()).decode("utf-8")


def ouvir(segundos=5):
    dados = gravar(segundos)
    pedido = "Transcreva este audio em portugues. Responda apenas com o texto falado, sem comentarios. Se nao houver fala, responda vazio."
    resposta = cliente.chat.completions.create(
        model=MODELO,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": pedido},
                    {"type": "input_audio", "input_audio": {"data": dados, "format": "wav"}},
                ],
            }
        ],
    )
    return resposta.choices[0].message.content.strip()


if __name__ == "__main__":
    print("Voce disse:", ouvir())
