import os
import time
import unicodedata

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

TAMANHO_MODELO = "small"
TAXA = 16000
BLOCO = 0.1
LIMIAR = 500
SILENCIO_FIM = 0.6
ESPERA_MAX = 6
FALA_MAX = 10
DICA = "Jarvis. Abra a calculadora. Abra o bloco de notas. Abra o YouTube."
IGNORAR = ("vazio", "silencio", "sem fala", "nenhuma fala", "legendas pela comunidade amara.org")


def carregar_modelo():
    print("Carregando o modelo de voz local, aguarde...")
    inicio = time.time()
    try:
        modelo = WhisperModel(TAMANHO_MODELO, device="cpu", compute_type="int8")
    except ValueError:
        modelo = WhisperModel(TAMANHO_MODELO, device="cpu", compute_type="float32")
    print("[tempo] modelo carregado:", round(time.time() - inicio, 1), "s")
    return modelo


modelo = carregar_modelo()


def volume(bloco):
    return float(np.abs(bloco.astype(np.int32)).max())


def decidir_fim(volumes, bloco=BLOCO):
    falou = False
    quietos = 0
    for i, v in enumerate(volumes):
        if v >= LIMIAR:
            falou = True
            quietos = 0
        else:
            quietos += 1
        tempo = (i + 1) * bloco
        if falou and quietos * bloco >= SILENCIO_FIM:
            return True, True
        if not falou and tempo >= ESPERA_MAX:
            return True, False
        if tempo >= FALA_MAX + ESPERA_MAX:
            return True, falou
    return False, falou


def gravar():
    print("Ouvindo...")
    tamanho = int(TAXA * BLOCO)
    blocos = []
    volumes = []
    with sd.InputStream(samplerate=TAXA, channels=1, dtype="int16", blocksize=tamanho) as entrada:
        while True:
            dados, _ = entrada.read(tamanho)
            blocos.append(dados.copy())
            volumes.append(volume(dados))
            parar, falou = decidir_fim(volumes)
            if parar:
                break
    if not falou:
        return None
    return np.concatenate(blocos)


def sem_acento(texto):
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def limpar_texto(texto):
    if not texto:
        return ""
    t = sem_acento(texto).strip().strip(".").strip()
    if t in IGNORAR:
        return ""
    return texto.strip()


def ouvir():
    audio = gravar()
    if audio is None:
        return ""
    amostras = audio.astype(np.float32).flatten() / 32768.0
    inicio = time.time()
    segmentos, _ = modelo.transcribe(
        amostras,
        language="pt",
        beam_size=1,
        vad_filter=True,
        initial_prompt=DICA,
    )
    texto = " ".join(s.text.strip() for s in segmentos)
    print("[tempo] transcricao:", round(time.time() - inicio, 1), "s")
    return limpar_texto(texto)


if __name__ == "__main__":
    print("Voce disse:", ouvir())