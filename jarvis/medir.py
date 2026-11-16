import asyncio
import os
import time

import edge_tts
from openai import OpenAI

cliente = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
MODELO = "gemini-3.5-flash-lite"
PERGUNTA = "Diga ola em uma frase curta."


def medir_gemini(extra=None):
    parametros = dict(
        model=MODELO,
        messages=[{"role": "user", "content": PERGUNTA}],
        stream=True,
    )
    if extra:
        parametros.update(extra)
    inicio = time.time()
    primeiro = None
    fluxo = cliente.chat.completions.create(**parametros)
    for parte in fluxo:
        if primeiro is None and parte.choices and parte.choices[0].delta.content:
            primeiro = time.time() - inicio
    return primeiro, time.time() - inicio


async def medir_voz():
    comunicar = edge_tts.Communicate("Ola, eu sou o Jarvis.", "pt-BR-AntonioNeural")
    inicio = time.time()
    primeiro = None
    async for pedaco in comunicar.stream():
        if primeiro is None and pedaco["type"] == "audio":
            primeiro = time.time() - inicio
    return primeiro, time.time() - inicio


def mostrar(nome, resultado):
    primeiro, total = resultado
    print(nome, "- primeira parte:", round(primeiro or 0, 1), "s - total:", round(total, 1), "s")


if __name__ == "__main__":
    print("Medindo, aguarde...")
    mostrar("Gemini normal", medir_gemini())
    try:
        mostrar("Gemini com pensamento baixo", medir_gemini({"reasoning_effort": "low"}))
    except Exception as erro:
        print("Gemini com pensamento baixo: nao aceitou:", str(erro)[:150])
    mostrar("Voz Antonio", asyncio.run(medir_voz()))