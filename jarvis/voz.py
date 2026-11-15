import asyncio

import edge_tts
import miniaudio
import sounddevice as sd

VOZ = "pt-BR-AntonioNeural"
TENTATIVAS = 3


async def _gerar(texto):
    comunicar = edge_tts.Communicate(texto, VOZ)
    dados = b""
    async for pedaco in comunicar.stream():
        if pedaco["type"] == "audio":
            dados += pedaco["data"]
    if not dados:
        raise RuntimeError("sem audio")
    return dados


def falar(texto):
    dados = None
    for tentativa in range(TENTATIVAS):
        try:
            dados = asyncio.run(_gerar(texto))
            break
        except Exception as erro:
            print("Voz falhou, tentando de novo:", erro)
    if dados is None:
        print("Nao consegui falar:", texto)
        return
    som = miniaudio.decode(dados, nchannels=1, sample_rate=24000)
    sd.play(memoryview(som.samples).cast("B").cast("h"), samplerate=24000)
    sd.wait()


if __name__ == "__main__":
    falar("Ola, eu sou o Jarvis. Estou pronto para ajudar.")
