import re
import unicodedata

import cerebro
import maos
import ouvidos
import voz

PALAVRAS_SAIR = ("sair", "encerrar", "tchau", "desligar")


def limpar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", texto).strip()


def tentar_acao(frase):
    f = limpar(frase)
    if not re.search(r"\b(abr[ae]|abrir|abra|inicie|iniciar)\b", f):
        return None
    for nome in maos.PROGRAMAS:
        if nome in f:
            return maos.abrir_programa(nome)
    for nome in maos.SITES:
        if nome in f:
            return maos.abrir_site(nome)
    for nome in maos.PASTAS:
        if nome in f:
            return maos.abrir_pasta(nome)
    return "Isso nao esta na minha lista de permissoes."


def responder(frase):
    acao = tentar_acao(frase)
    if acao is not None:
        return acao
    return cerebro.perguntar(frase)


def principal():
    voz.falar("Jarvis online. Pode falar.")
    while True:
        try:
            frase = ouvidos.ouvir(6)
        except Exception as erro:
            print("Erro ao ouvir:", erro)
            continue
        if not frase:
            continue
        print("Voce:", frase)
        if any(p in limpar(frase).split() for p in PALAVRAS_SAIR):
            voz.falar("Encerrando. Ate logo.")
            break
        try:
            resposta = responder(frase)
        except Exception as erro:
            resposta = "Tive um problema para responder."
            print("Erro:", erro)
        print("Jarvis:", resposta)
        voz.falar(resposta)


if __name__ == "__main__":
    principal()
