import asyncio
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import edge_tts
import miniaudio
import sounddevice as sd

VOZ = "pt-BR-AntonioNeural"
TENTATIVAS = 3
TAXA_VOZ = 24000
MARCAS = (".", "!", "?", ";", "\n")


async def _gerar(texto):
    comunicar = edge_tts.Communicate(texto, VOZ)
    dados = b""
    async for pedaco in comunicar.stream():
        if pedaco["type"] == "audio":
            dados += pedaco["data"]
    if not dados:
        raise RuntimeError("sem audio")
    return dados


def _gerar_som(texto):
    inicio = time.time()
    for _ in range(TENTATIVAS):
        try:
            dados = asyncio.run(_gerar(texto))
            som = miniaudio.decode(dados, nchannels=1, sample_rate=TAXA_VOZ)
            print("[tempo] voz gerada:", round(time.time() - inicio, 1), "s")
            return memoryview(som.samples).cast("B").cast("h")
        except Exception as erro:
            print("Voz falhou, tentando de novo:", erro)
    print("Nao consegui falar:", texto)
    return None


def _tocar_som(som):
    sd.play(som, samplerate=TAXA_VOZ)
    sd.wait()


def falar(texto):
    som = _gerar_som(texto)
    if som is not None:
        _tocar_som(som)


def _separar(buffer):
    frases = []
    while True:
        corte = -1
        for marca in MARCAS:
            i = buffer.find(marca)
            if i != -1 and (corte == -1 or i < corte):
                corte = i
        if corte == -1 and len(buffer) > 70:
            i = buffer.find(",", 30)
            if i != -1:
                corte = i
        if corte == -1:
            break
        frase = buffer[: corte + 1].strip()
        buffer = buffer[corte + 1 :]
        if frase:
            frases.append(frase)
    return frases, buffer


def falar_em_pedacos(pedacos):
    fila = queue.Queue()
    fim = object()
    executor = ThreadPoolExecutor(max_workers=3)

    def produtor():
        buffer = ""
        try:
            for pedaco in pedacos:
                buffer += pedaco
                frases, buffer = _separar(buffer)
                for frase in frases:
                    fila.put(executor.submit(_gerar_som, frase))
            if buffer.strip():
                fila.put(executor.submit(_gerar_som, buffer.strip()))
        finally:
            fila.put(fim)

    threading.Thread(target=produtor, daemon=True).start()
    while True:
        item = fila.get()
        if item is fim:
            break
        som = item.result()
        if som is not None:
            _tocar_som(som)
    executor.shutdown(wait=False)


if __name__ == "__main__":
    falar("Ola, eu sou o Jarvis. Estou pronto para ajudar.")