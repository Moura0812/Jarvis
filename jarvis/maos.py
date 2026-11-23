import ctypes
import os
import subprocess
import webbrowser

PROGRAMAS = {
    "bloco de notas": "notepad.exe",
    "calculadora": "calc.exe",
    "paint": "mspaint.exe",
    "explorador": "explorer.exe",
}

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
}

PASTAS = {
    "documentos": os.path.join(os.path.expanduser("~"), "Documents"),
    "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    "area de trabalho": os.path.join(os.path.expanduser("~"), "Desktop"),
}

FECHAVEIS = {
    "calculadora": ("CalculatorApp.exe", "Calculator.exe", "calc.exe", "Calculadora.exe"),
    "bloco de notas": ("Notepad.exe",),
    "paint": ("mspaint.exe",),
}

TECLA_MUDO = 0xAD
TECLA_BAIXAR = 0xAE
TECLA_SUBIR = 0xAF
PASSOS_VOLUME = 5
PASSOS_MAXIMO = 50


def abrir_programa(nome):
    nome = nome.strip().lower()
    if nome not in PROGRAMAS:
        return "Nao tenho permissao para abrir " + nome + "."
    subprocess.Popen(PROGRAMAS[nome])
    return "Abrindo " + nome + "."


def abrir_site(nome):
    nome = nome.strip().lower()
    if nome not in SITES:
        return "O site " + nome + " nao esta na minha lista."
    webbrowser.open(SITES[nome])
    return "Abrindo " + nome + "."


def abrir_pasta(nome):
    nome = nome.strip().lower()
    if nome not in PASTAS:
        return "A pasta " + nome + " nao esta na minha lista."
    os.startfile(PASTAS[nome])
    return "Abrindo a pasta " + nome + "."


def _rodar(argumentos):
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    resultado = subprocess.run(argumentos, capture_output=True, creationflags=sem_janela)
    return resultado.returncode


def _apertar_tecla(codigo, vezes=1):
    if os.name != "nt":
        return False
    for _ in range(vezes):
        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)
    return True


def fechar_programa(nome):
    if nome not in FECHAVEIS:
        return "Nao posso fechar " + nome + "."
    for exe in FECHAVEIS[nome]:
        if nome != "calculadora" and _rodar(["taskkill", "/IM", exe]) == 0:
            return "Fechando " + nome + "."
    if nome == "calculadora":
        for exe in FECHAVEIS[nome]:
            if _rodar(["taskkill", "/F", "/T", "/IM", exe]) == 0:
                return "Fechando " + nome + "."
    return "Nao encontrei o programa " + nome + " aberto."


def mudar_volume(acao):
    if acao == "maximo":
        ok = _apertar_tecla(TECLA_SUBIR, PASSOS_MAXIMO)
        return "Volume no maximo." if ok else "Nao consegui mudar o volume."
    if acao == "minimo":
        ok = _apertar_tecla(TECLA_BAIXAR, PASSOS_MAXIMO)
        return "Volume no minimo." if ok else "Nao consegui mudar o volume."
    if acao == "subir":
        ok = _apertar_tecla(TECLA_SUBIR, PASSOS_VOLUME)
        return "Aumentando o volume." if ok else "Nao consegui mudar o volume."
    if acao == "baixar":
        ok = _apertar_tecla(TECLA_BAIXAR, PASSOS_VOLUME)
        return "Diminuindo o volume." if ok else "Nao consegui mudar o volume."
    ok = _apertar_tecla(TECLA_MUDO, 1)
    return "Alternando o mudo." if ok else "Nao consegui mudar o volume."


def controlar_sistema(f):
    """Recebe a frase ja sem acentos e em minusculas. Devolve texto ou None."""
    palavras = f.split()
    if any(p.startswith("fech") for p in palavras):
        for nome in FECHAVEIS:
            if nome in f:
                return fechar_programa(nome)
        if "calcul" in f:
            return fechar_programa("calculadora")
        if "explorador" in f:
            return "Nao posso fechar o explorador, porque ele e a barra de tarefas do Windows."
        return "Isso nao esta na minha lista de programas que posso fechar."
    if "volume" in palavras:
        if any(p in ("maximo", "maxima", "cem", "100") for p in palavras):
            return mudar_volume("maximo")
        if any(p in ("minimo", "minima", "zero") for p in palavras):
            return mudar_volume("minimo")
        if any(p in ("aumente", "aumentar", "aumenta", "suba", "subir", "sobe", "mais") for p in palavras):
            return mudar_volume("subir")
        if any(p in ("diminua", "diminuir", "diminui", "abaixe", "abaixar", "baixe", "baixar", "reduza", "menos") for p in palavras):
            return mudar_volume("baixar")
        return None
    if "mudo" in palavras:
        return mudar_volume("mudo")
    return None