import asyncio
import os
import tempfile

import edge_tts

VOZ = "pt-BR-ThalitaMultilingualNeural"


async def _gerar(texto, caminho):
    comunicar = edge_tts.Communicate(texto, VOZ)
    await comunicar.save(caminho)


def falar(texto):
    pasta = tempfile.gettempdir()
    arquivo = os.path.join(pasta, "jarvis_fala.mp3")
    asyncio.run(_gerar(texto, arquivo))
    os.startfile(arquivo)


if __name__ == "__main__":
    falar("Olá, eu sou o Jarvis. Estou pronto para ajudar.")