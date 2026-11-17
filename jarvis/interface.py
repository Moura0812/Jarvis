import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

import cerebro
import maos
import ouvidos
import voz
from jarvis import PALAVRAS_SAIR, limpar, tentar_acao

ATIVACAO = ("jarvis", "jarves", "jarvi", "charvis", "garvis")
SILENCIO = ("silencio", "fica quieto", "fique quieto", "cala a boca", "para de falar")

COR_FUNDO = "#1e1e1e"
COR_TEXTO = "#e6e6e6"
COR_JARVIS = "#4fc3f7"
COR_VOCE = "#ffd54f"


def tem_nome(frase):
    return any(p in ATIVACAO for p in limpar(frase).split())


def comando_do_nome(frase):
    palavras = limpar(frase).split()
    for i, p in enumerate(palavras):
        if p in ATIVACAO:
            return " ".join(palavras[i + 1 :]).strip()
    return None


def eh_silencio(comando):
    t = " ".join(limpar(comando).split())
    return any(s in t for s in SILENCIO)


class Interface:
    def __init__(self, raiz):
        self.raiz = raiz
        self.fila = queue.Queue()
        self.falando = threading.Event()
        self.acordado = False
        self.rodando = True

        raiz.title("Jarvis")
        raiz.geometry("640x560")
        raiz.configure(bg=COR_FUNDO)

        self.conversa = scrolledtext.ScrolledText(
            raiz, wrap=tk.WORD, bg=COR_FUNDO, fg=COR_TEXTO,
            font=("Segoe UI", 11), state="disabled", relief="flat",
        )
        self.conversa.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.conversa.tag_config("voce", foreground=COR_VOCE)
        self.conversa.tag_config("jarvis", foreground=COR_JARVIS)

        barra = tk.Frame(raiz, bg=COR_FUNDO)
        barra.pack(fill="x", padx=12, pady=(0, 12))

        self.entrada = tk.Entry(
            barra, font=("Segoe UI", 11), bg="#2b2b2b", fg=COR_TEXTO,
            insertbackground=COR_TEXTO, relief="flat",
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=6)
        self.entrada.bind("<Return>", lambda e: self.enviar_digitado())

        tk.Button(
            barra, text="Enviar", command=self.enviar_digitado,
            bg="#333333", fg=COR_TEXTO, relief="flat", padx=12,
        ).pack(side="left", padx=(6, 0))

        self.status = tk.Label(
            raiz, text="Carregando a voz local...",
            bg=COR_FUNDO, fg="#9e9e9e", anchor="w", font=("Segoe UI", 9),
        )
        self.status.pack(fill="x", padx=12, pady=(0, 8))

        self.raiz.after(100, self._processar_fila)
        threading.Thread(target=self._loop_escuta, daemon=True).start()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)

    def escrever(self, quem, texto):
        self.conversa.configure(state="normal")
        tag = "voce" if quem == "Voce" else "jarvis"
        self.conversa.insert("end", quem + ": ", tag)
        self.conversa.insert("end", texto + "\n")
        self.conversa.see("end")
        self.conversa.configure(state="disabled")

    def _processar_fila(self):
        try:
            while True:
                tipo, dados = self.fila.get_nowait()
                if tipo == "status":
                    self.status.configure(text=dados)
                elif tipo == "escrever":
                    self.escrever(*dados)
        except queue.Empty:
            pass
        if self.rodando:
            self.raiz.after(100, self._processar_fila)

    def _loop_escuta(self):
        self.fila.put(("status", "Ouvindo. Diga Jarvis para me chamar, ou digite."))
        while self.rodando:
            if self.falando.is_set():
                threading.Event().wait(0.05)
                continue
            try:
                frase = ouvidos.ouvir()
            except Exception as erro:
                self.fila.put(("status", "Erro ao ouvir: " + str(erro)))
                threading.Event().wait(1)
                continue
            if frase and not self.falando.is_set():
                self.fila.put(("escrever", ("Voce", frase)))
                self._processar(frase)

    def enviar_digitado(self):
        texto = self.entrada.get().strip()
        if not texto:
            return
        self.entrada.delete(0, "end")
        self.escrever("Voce", texto)
        threading.Thread(target=self._processar, args=(texto,), daemon=True).start()

    def _processar(self, frase):
        if not frase or not frase.strip():
            return
        if not self.acordado:
            if not tem_nome(frase):
                return
            cmd = comando_do_nome(frase)
            self.acordado = True
            if cmd and eh_silencio(cmd):
                self.acordado = False
                self._falar("Certo. Estou em silencio. Diga Jarvis para me chamar.")
                return
            if not cmd:
                self._falar("Sim, senhor?")
                return
            self._executar(cmd)
            return
        if eh_silencio(frase):
            self.acordado = False
            self._falar("Certo. Estou em silencio. Diga Jarvis para me chamar.")
            return
        cmd = comando_do_nome(frase)
        self._executar(cmd if cmd else frase.strip())

    def _falar(self, texto):
        self.fila.put(("escrever", ("Jarvis", texto)))
        self.falando.set()
        try:
            voz.falar(texto)
        finally:
            self.falando.clear()

    def _executar(self, comando):
        if any(p in limpar(comando).split() for p in PALAVRAS_SAIR):
            self._falar("Encerrando. Ate logo.")
            self.raiz.after(0, self.fechar)
            return
        acao = tentar_acao(comando)
        if acao is not None:
            self._falar(acao)
            return
        self.falando.set()
        try:
            pedacos = cerebro.perguntar_em_pedacos(comando)
            acumulado = []

            def mostrar():
                for p in pedacos:
                    acumulado.append(p)
                    yield p

            voz.falar_em_pedacos(mostrar())
            self.fila.put(("escrever", ("Jarvis", "".join(acumulado))))
        except Exception as erro:
            self.fila.put(("escrever", ("Jarvis", "Tive um problema para responder.")))
            print("Erro:", erro)
        finally:
            self.falando.clear()

    def fechar(self):
        self.rodando = False
        self.raiz.destroy()


if __name__ == "__main__":
    raiz = tk.Tk()
    Interface(raiz)
    raiz.mainloop()