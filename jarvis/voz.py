import asyncio
import hashlib
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import edge_tts
import maos
import miniaudio
import sounddevice as sd

VOZ = "pt-BR-AntonioNeural"
TENTATIVAS = 3
TAXA_VOZ = 24000
MARCAS = (".", "!", "?", ";", "\n")
PASTA_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_voz")
LIMITE_CACHE = 80


async def _gerar(texto):
    comunicar = edge_tts.Communicate(texto, VOZ)
    dados = b""
    async for pedaco in comunicar.stream():
        if pedaco["type"] == "audio":
            dados += pedaco["data"]
    if not dados:
        raise RuntimeError("sem audio")
    return dados


def _arquivo_cache(texto):
    chave = hashlib.md5((VOZ + "|" + texto).encode("utf-8")).hexdigest()
    return os.path.join(PASTA_CACHE, chave + ".mp3")


def _dados_da_voz(texto, silencioso=False):
    guardavel = len(texto) <= LIMITE_CACHE
    arquivo = _arquivo_cache(texto)
    if guardavel and os.path.exists(arquivo):
        with open(arquivo, "rb") as f:
            return f.read()
    for _ in range(TENTATIVAS):
        try:
            dados = asyncio.run(_gerar(texto))
            if guardavel:
                os.makedirs(PASTA_CACHE, exist_ok=True)
                temporario = arquivo + "." + str(threading.get_ident()) + ".tmp"
                with open(temporario, "wb") as f:
                    f.write(dados)
                os.replace(temporario, arquivo)
            return dados
        except Exception as erro:
            if not silencioso:
                print("Voz falhou, tentando de novo:", erro)
    return None


def _gerar_som(texto):
    inicio = time.time()
    dados = _dados_da_voz(texto)
    if dados is None:
        print("Nao consegui falar:", texto)
        return None
    try:
        som = miniaudio.decode(dados, nchannels=1, sample_rate=TAXA_VOZ)
    except Exception as erro:
        print("Audio invalido:", erro)
        try:
            os.remove(_arquivo_cache(texto))
        except OSError:
            pass
        return None
    print("[tempo] voz pronta:", round(time.time() - inicio, 1), "s")
    return memoryview(som.samples).cast("B").cast("h")


def _tocar_som(som):
    sd.play(som, samplerate=TAXA_VOZ)
    sd.wait()


def falar(texto):
    som = _gerar_som(texto)
    if som is not None:
        _tocar_som(som)


def _separar(buffer, primeiro=False):
    frases = []
    while True:
        corte = -1
        for marca in MARCAS:
            i = buffer.find(marca)
            if i != -1 and (corte == -1 or i < corte):
                corte = i
        if corte == -1:
            if primeiro and not frases:
                i = buffer.find(",", 20)
                if i == -1 and len(buffer) > 50:
                    i = buffer.find(" ", 40)
                corte = i
            elif len(buffer) > 70:
                corte = buffer.find(",", 30)
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
        primeiro = True
        try:
            for pedaco in pedacos:
                buffer += pedaco
                frases, buffer = _separar(buffer, primeiro)
                for frase in frases:
                    primeiro = False
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


def _frases_comuns():
    frases = [
        "Encerrando. Ate logo.",
        "Isso nao esta na minha lista de permissoes.",
        "Tive um problema para responder.",
    ]
    for nome in maos.PROGRAMAS:
        frases.append("Abrindo " + nome + ".")
    for nome in maos.SITES:
        frases.append("Abrindo " + nome + ".")
    for nome in maos.PASTAS:
        frases.append("Abrindo a pasta " + nome + ".")
    return frases


def _pre_aquecer():
    for frase in _frases_comuns():
        if not os.path.exists(_arquivo_cache(frase)):
            _dados_da_voz(frase, silencioso=True)


threading.Thread(target=_pre_aquecer, daemon=True).start()


if __name__ == "__main__":
    falar("Ola, eu sou o Jarvis. Estou pronto para ajudar.")