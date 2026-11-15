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


if __name__ == "__main__":
    print(abrir_programa("calculadora"))
    print(abrir_programa("regedit"))
    print(abrir_site("youtube"))
    print(abrir_pasta("documentos"))
