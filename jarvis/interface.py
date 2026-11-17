import math
import queue
import threading
import time
import tkinter as tk

import cerebro
import maos
import ouvidos
import voz
from jarvis import PALAVRAS_SAIR, limpar, tentar_acao

ATIVACAO = ("jarvis", "jarves", "jarvi", "charvis", "garvis")
SILENCIO = ("silencio", "fica quieto", "fique quieto", "cala a boca", "para de falar")

FUNDO = "#16181d"
PAINEL = "#1f2229"
BOLHA_VOCE = "#2a2e38"
BOLHA_JARVIS = "#16344a"
TEXTO = "#e6e6e6"
SUAVE = "#8a8f9c"
CORES = {
    "dormindo": "#6b7280",
    "ouvindo": "#22c55e",
    "falando": "#4fc3f7",
    "pensando": "#f59e0b",
}


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


def misturar(cor_a, cor_b, f):
    a = [int(cor_a[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * f):02x}" for x, y in zip(a, b))


def retangulo_arredondado(canvas, x0, y0, x1, y1, r, cor):
    passos = 8
    cantos = [
        (x1 - r, y0 + r, -90, 0),
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
    ]
    pontos = []
    for cx, cy, a0, a1 in cantos:
        for i in range(passos + 1):
            a = math.radians(a0 + (a1 - a0) * i / passos)
            pontos += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return canvas.create_polygon(pontos, fill=cor, smooth=False)


class Interface:
    def __init__(self, raiz):
        self.raiz = raiz
        self.fila = queue.Queue()
        self.falando = threading.Event()
        self.acordado = False
        self.rodando = True
        self.estado = "dormindo"
        self.ultima_acao = "nenhuma ainda"
        self.inicio = time.time()

        raiz.title("Jarvis")
        raiz.geometry("820x600")
        raiz.configure(bg=FUNDO)
        raiz.minsize(700, 480)

        self._montar_painel_lateral()
        self._montar_conversa()

        self.raiz.after(100, self._processar_fila)
        self.raiz.after(60, self._pulsar)
        self._atualizar_relogio()
        threading.Thread(target=self._loop_escuta, daemon=True).start()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)

    def _montar_painel_lateral(self):
        lateral = tk.Frame(self.raiz, bg=PAINEL, width=220)
        lateral.pack(side="left", fill="y", padx=(12, 0), pady=12)
        lateral.pack_propagate(False)

        self.canvas_estado = tk.Canvas(lateral, width=180, height=180, bg=PAINEL, highlightthickness=0)
        self.canvas_estado.pack(pady=(18, 6))
        self.circulo = self.canvas_estado.create_oval(30, 30, 150, 150, fill=CORES["dormindo"], outline="")

        self.label_estado = tk.Label(lateral, text="DORMINDO", bg=PAINEL, fg=TEXTO,
                                     font=("Segoe UI", 13, "bold"))
        self.label_estado.pack()
        self.label_dica = tk.Label(lateral, text="Diga Jarvis para me chamar", bg=PAINEL, fg=SUAVE,
                                   font=("Segoe UI", 9), wraplength=190)
        self.label_dica.pack(pady=(2, 18))

        tk.Label(lateral, text="HORA", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18)
        self.label_hora = tk.Label(lateral, text="", bg=PAINEL, fg=TEXTO, font=("Segoe UI", 18))
        self.label_hora.pack(anchor="w", padx=18, pady=(0, 14))

        tk.Label(lateral, text="ULTIMA ACAO", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18)
        self.label_acao = tk.Label(lateral, text=self.ultima_acao, bg=PAINEL, fg=TEXTO,
                                   font=("Segoe UI", 10), wraplength=190, justify="left")
        self.label_acao.pack(anchor="w", padx=18)

    def _montar_conversa(self):
        meio = tk.Frame(self.raiz, bg=FUNDO)
        meio.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        self.area = tk.Canvas(meio, bg=FUNDO, highlightthickness=0)
        self.area.pack(fill="both", expand=True)
        self.area.bind("<Configure>", lambda e: self._redesenhar())
        self.mensagens = []

        barra = tk.Frame(meio, bg=FUNDO)
        barra.pack(fill="x", pady=(8, 0))

        self.entrada = tk.Entry(barra, font=("Segoe UI", 11), bg="#2b2f3a", fg=TEXTO,
                                insertbackground=TEXTO, relief="flat")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8)
        self.entrada.bind("<Return>", lambda e: self.enviar_digitado())

        self.botao = tk.Button(barra, text="Enviar", command=self.enviar_digitado,
                               bg="#0277bd", fg="white", relief="flat", padx=16, pady=6)
        self.botao.pack(side="left", padx=(8, 0))

    def _redesenhar(self):
        self.area.delete("all")
        largura = self.area.winfo_width()
        y = 8
        for quem, texto in self.mensagens[-40:]:
            lado_direito = quem == "Voce"
            cor = BOLHA_VOCE if lado_direito else BOLHA_JARVIS
            maximo = int(largura * 0.72)
            t = self.area.create_text(0, 0, text=quem + "\n" + texto, fill=TEXTO,
                                      font=("Segoe UI", 11), width=maximo, anchor="nw")
            x0, y0, x1, y1 = self.area.bbox(t)
            self.area.delete(t)
            altura = y1 - y0 + 18
            if lado_direito:
                x_fim = largura - 8
                x_ini = x_fim - (x1 - x0) - 24
            else:
                x_ini = 8
                x_fim = x_ini + (x1 - x0) + 24
            retangulo_arredondado(self.area, x_ini, y, x_fim, y + altura, 14, cor)
            self.area.create_text(x_ini + 12, y + 9, text=quem + "\n" + texto, fill=TEXTO,
                                  font=("Segoe UI", 11), width=maximo, anchor="nw")
            y += altura + 10
        self.area.configure(scrollregion=(0, 0, largura, y))
        self.area.yview_moveto(1.0)

    def escrever(self, quem, texto):
        self.mensagens.append((quem, texto))
        self._redesenhar()

    def _definir_estado(self, estado):
        self.estado = estado
        self.label_estado.configure(text=estado.upper())
        dicas = {
            "dormindo": "Diga Jarvis para me chamar",
            "ouvindo": "Estou ouvindo",
            "falando": "Estou respondendo",
            "pensando": "Pensando na resposta",
        }
        self.label_dica.configure(text=dicas[estado])

    def _pulsar(self):
        t = time.time() - self.inicio
        f = 0.65 + 0.35 * math.sin(2 * math.pi * t / 1.2)
        cor = misturar("#1f2229", CORES[self.estado], f)
        self.canvas_estado.itemconfig(self.circulo, fill=cor)
        if self.rodando:
            self.raiz.after(60, self._pulsar)

    def _atualizar_relogio(self):
        self.label_hora.configure(text=time.strftime("%H:%M"))
        self.label_acao.configure(text=self.ultima_acao)
        if self.rodando:
            self.raiz.after(1000, self._atualizar_relogio)

    def _processar_fila(self):
        try:
            while True:
                tipo, dados = self.fila.get_nowait()
                if tipo == "escrever":
                    self.escrever(*dados)
                elif tipo == "estado":
                    self._definir_estado(dados)
                elif tipo == "acao":
                    self.ultima_acao = dados
        except queue.Empty:
            pass
        if self.rodando:
            self.raiz.after(100, self._processar_fila)

    def _loop_escuta(self):
        self.fila.put(("estado", "dormindo"))
        while self.rodando:
            if self.falando.is_set():
                threading.Event().wait(0.05)
                continue
            self.fila.put(("estado", "ouvindo" if self.acordado else "dormindo"))
            try:
                frase = ouvidos.ouvir()
            except Exception:
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
        self.fila.put(("estado", "falando"))
        self.falando.set()
        try:
            voz.falar(texto)
        finally:
            self.falando.clear()

    def _executar(self, comando):
        self.fila.put(("estado", "pensando"))
        if any(p in limpar(comando).split() for p in PALAVRAS_SAIR):
            self._falar("Encerrando. Ate logo.")
            self.raiz.after(0, self.fechar)
            return
        acao = tentar_acao(comando)
        if acao is not None:
            self.fila.put(("acao", acao))
            self._falar(acao)
            return
        self.falando.set()
        try:
            pedacos = cerebro.perguntar_em_pedacos(comando)
            acumulado = []

            def mostrar():
                for p in pedacos:
                    acumulado.append(p)
                    self.fila.put(("estado", "falando"))
                    yield p

            voz.falar_em_pedacos(mostrar())
            self.fila.put(("escrever", ("Jarvis", "".join(acumulado))))
            self.fila.put(("acao", "Respondi: " + comando[:40]))
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