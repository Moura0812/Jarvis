import json
import math
import os
import queue
import re
import threading
import time
import tkinter as tk
import urllib.request

import cerebro
import maos
import ouvidos
import voz
from jarvis import PALAVRAS_SAIR, limpar, tentar_acao

ATIVACAO = ("jarvis", "jarves", "jarvi", "charvis", "garvis")
SILENCIO = ("silencio", "fica quieto", "fique quieto", "cala a boca", "para de falar")
CLIMA_PADRAO = "Brasilia: consultando a previsao"
URL_CLIMA = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=-15.7939&longitude=-47.8828"
    "&current=temperature_2m,relative_humidity_2m,weather_code"
)

FUNDO = "#0b0f16"
PAINEL = "#111827"
BOLHA_VOCE = "#1f2937"
BOLHA_JARVIS = "#0c3a52"
TEXTO = "#e5f1ff"
SUAVE = "#7b93ad"
AZUL = "#38bdf8"
CORES = {
    "dormindo": "#4b5563",
    "ouvindo": "#22c55e",
    "falando": "#38bdf8",
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


def descrever_clima(codigo):
    if codigo == 0:
        return "ceu limpo"
    if codigo in (1, 2):
        return "poucas nuvens"
    if codigo == 3:
        return "nublado"
    if codigo in (45, 48):
        return "neblina"
    if 51 <= codigo <= 57:
        return "garoa"
    if 61 <= codigo <= 67 or 80 <= codigo <= 82:
        return "chuva"
    if 71 <= codigo <= 77 or codigo in (85, 86):
        return "neve"
    if codigo >= 95:
        return "trovoada"
    return "tempo variavel"


def buscar_clima():
    try:
        with urllib.request.urlopen(URL_CLIMA, timeout=10) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        atual = dados["current"]
        temperatura = round(atual["temperature_2m"])
        umidade = round(atual["relative_humidity_2m"])
        descricao = descrever_clima(int(atual["weather_code"]))
        return "Brasilia: " + str(temperatura) + "\u00b0C, " + descricao + "\nUmidade " + str(umidade) + "%"
    except Exception as erro:
        print("Clima:", erro)
        return "Brasilia: clima indisponivel"


def ler_emails_recentes(quantidade=5):
    """Le os e-mails recentes da caixa de entrada, somente para leitura.
    Devolve uma lista de dicionarios, ou None se o Gmail nao estiver conectado."""
    if not os.path.exists("credenciais.json") and not os.path.exists("token.json"):
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        escopos = ["https://www.googleapis.com/auth/gmail.readonly"]
        credencial = None
        if os.path.exists("token.json"):
            credencial = Credentials.from_authorized_user_file("token.json", escopos)
        if not credencial or not credencial.valid:
            if credencial and credencial.expired and credencial.refresh_token:
                credencial.refresh(Request())
            else:
                fluxo = InstalledAppFlow.from_client_secrets_file("credenciais.json", escopos)
                credencial = fluxo.run_local_server(port=0)
            with open("token.json", "w", encoding="utf-8") as f:
                f.write(credencial.to_json())
        servico = build("gmail", "v1", credentials=credencial, cache_discovery=False)
        lista = servico.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=quantidade
        ).execute()
        emails = []
        for item in lista.get("messages", []):
            msg = servico.users().messages().get(
                userId="me", id=item["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            cabecalhos = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            emails.append({
                "de": re.sub(r"<.*?>", "", cabecalhos.get("From", "")).strip().strip('"')[:34],
                "assunto": cabecalhos.get("Subject", "(sem assunto)")[:60],
            })
        return emails
    except Exception as erro:
        print("Gmail:", erro)
        return None


class Interface:
    def __init__(self, raiz):
        self.raiz = raiz
        self.fila = queue.Queue()
        self.falando = threading.Event()
        self.acordado = False
        self.rodando = True
        self.estado = "dormindo"
        self.clima = CLIMA_PADRAO
        self.emails = None
        self.emails_prontos = False
        self.ultima_acao = "nenhuma ainda"
        self.inicio = time.time()

        raiz.title("Jarvis")
        raiz.geometry("1000x640")
        raiz.configure(bg=FUNDO)
        raiz.minsize(820, 520)

        self._montar_esquerda()
        self._montar_direita()
        self._montar_centro()

        self.raiz.after(100, self._processar_fila)
        self.raiz.after(60, self._pulsar)
        self.raiz.after(1000, self._atualizar_painel)
        threading.Thread(target=self._loop_emails, daemon=True).start()
        threading.Thread(target=self._loop_clima, daemon=True).start()
        threading.Thread(target=self._loop_escuta, daemon=True).start()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)

    def _montar_esquerda(self):
        painel = tk.Frame(self.raiz, bg=PAINEL, width=220)
        painel.pack(side="left", fill="y", padx=(12, 6), pady=12)
        painel.pack_propagate(False)
        tk.Label(painel, text="HORA", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        self.label_hora = tk.Label(painel, text="", bg=PAINEL, fg=TEXTO, font=("Segoe UI", 26, "bold"))
        self.label_hora.pack(anchor="w", padx=16)
        self.label_data = tk.Label(painel, text="", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 10))
        self.label_data.pack(anchor="w", padx=16, pady=(0, 18))

        tk.Label(painel, text="CLIMA", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        self.label_clima = tk.Label(painel, text=self.clima, bg=PAINEL, fg=TEXTO,
                                    font=("Segoe UI", 10), wraplength=190, justify="left")
        self.label_clima.pack(anchor="w", padx=16, pady=(0, 18))

        tk.Label(painel, text="ULTIMA ACAO", bg=PAINEL, fg=SUAVE, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        self.label_acao = tk.Label(painel, text=self.ultima_acao, bg=PAINEL, fg=TEXTO,
                                   font=("Segoe UI", 10), wraplength=190, justify="left")
        self.label_acao.pack(anchor="w", padx=16)

    def _montar_direita(self):
        painel = tk.Frame(self.raiz, bg=PAINEL, width=260)
        painel.pack(side="right", fill="y", padx=(6, 12), pady=12)
        painel.pack_propagate(False)
        tk.Label(painel, text="E-MAILS RECENTES (SO LEITURA)", bg=PAINEL, fg=SUAVE,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.label_emails = tk.Label(painel, text="Carregando e-mails...", bg=PAINEL, fg=TEXTO,
                                     font=("Segoe UI", 9), wraplength=230, justify="left")
        self.label_emails.pack(anchor="w", padx=16, fill="x")

    def _montar_centro(self):
        meio = tk.Frame(self.raiz, bg=FUNDO)
        meio.pack(side="left", fill="both", expand=True, padx=6, pady=12)

        self.canvas_nucleo = tk.Canvas(meio, height=170, bg=FUNDO, highlightthickness=0)
        self.canvas_nucleo.pack(fill="x")
        self.anel_externo = self.canvas_nucleo.create_oval(0, 0, 0, 0, outline=AZUL, width=2)
        self.anel_medio = self.canvas_nucleo.create_oval(0, 0, 0, 0, outline=AZUL, width=1)
        self.nucleo = self.canvas_nucleo.create_oval(0, 0, 0, 0, fill=CORES["dormindo"], outline="")
        self.label_estado = tk.Label(meio, text="DORMINDO", bg=FUNDO, fg=TEXTO, font=("Segoe UI", 12, "bold"))
        self.label_estado.pack()
        self.label_dica = tk.Label(meio, text="Diga Jarvis para me chamar", bg=FUNDO, fg=SUAVE, font=("Segoe UI", 9))
        self.label_dica.pack(pady=(0, 8))

        self.area = tk.Canvas(meio, bg=FUNDO, highlightthickness=0)
        self.area.pack(fill="both", expand=True)
        self.area.bind("<Configure>", lambda e: self._redesenhar())
        self.mensagens = []

        barra = tk.Frame(meio, bg=FUNDO)
        barra.pack(fill="x", pady=(8, 0))
        self.entrada = tk.Entry(barra, font=("Segoe UI", 11), bg="#1a2333", fg=TEXTO,
                                insertbackground=TEXTO, relief="flat")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8)
        self.entrada.bind("<Return>", lambda e: self.enviar_digitado())
        tk.Button(barra, text="Enviar", command=self.enviar_digitado,
                  bg="#0369a1", fg="white", relief="flat", padx=16, pady=6).pack(side="left", padx=(8, 0))

    def _redesenhar(self):
        self.area.delete("all")
        largura = self.area.winfo_width()
        y = 8
        for quem, texto in self.mensagens[-40:]:
            direita = quem == "Voce"
            cor = BOLHA_VOCE if direita else BOLHA_JARVIS
            maximo = int(largura * 0.72)
            t = self.area.create_text(0, 0, text=quem + "\n" + texto, fill=TEXTO,
                                      font=("Segoe UI", 11), width=maximo, anchor="nw")
            x0, y0, x1, y1 = self.area.bbox(t)
            self.area.delete(t)
            altura = y1 - y0 + 18
            if direita:
                x_fim = largura - 8
                x_ini = x_fim - (x1 - x0) - 24
            else:
                x_ini = 8
                x_fim = x_ini + (x1 - x0) + 24
            self._bolha(x_ini, y, x_fim, y + altura, 14, cor)
            self.area.create_text(x_ini + 12, y + 9, text=quem + "\n" + texto, fill=TEXTO,
                                  font=("Segoe UI", 11), width=maximo, anchor="nw")
            y += altura + 10
        self.area.configure(scrollregion=(0, 0, largura, y))
        self.area.yview_moveto(1.0)

    def _bolha(self, x0, y0, x1, y1, r, cor):
        passos = 8
        cantos = [(x1 - r, y0 + r, -90, 0), (x1 - r, y1 - r, 0, 90),
                  (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270)]
        pontos = []
        for cx, cy, a0, a1 in cantos:
            for i in range(passos + 1):
                a = math.radians(a0 + (a1 - a0) * i / passos)
                pontos += [cx + r * math.cos(a), cy + r * math.sin(a)]
        self.area.create_polygon(pontos, fill=cor)

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
        cor = misturar("#0b0f16", CORES[self.estado], f)
        self.canvas_nucleo.update_idletasks()
        largura = self.canvas_nucleo.winfo_width()
        altura = self.canvas_nucleo.winfo_height()
        cx, cy = largura / 2, altura / 2
        raio = min(cx, cy) - 12
        self.canvas_nucleo.coords(self.anel_externo, cx - raio, cy - raio, cx + raio, cy + raio)
        r2 = raio * 0.72
        self.canvas_nucleo.coords(self.anel_medio, cx - r2, cy - r2, cx + r2, cy + r2)
        r3 = raio * 0.42 * f + 6
        self.canvas_nucleo.coords(self.nucleo, cx - r3, cy - r3, cx + r3, cy + r3)
        self.canvas_nucleo.itemconfig(self.nucleo, fill=cor)
        if self.rodando:
            self.raiz.after(60, self._pulsar)

    def _atualizar_painel(self):
        agora = time.localtime()
        self.label_hora.configure(text=time.strftime("%H:%M", agora))
        self.label_data.configure(text=time.strftime("%d/%m/%Y", agora))
        self.label_acao.configure(text=self.ultima_acao)
        if self.rodando:
            self.raiz.after(30000, self._atualizar_painel)

    def _mostrar_emails(self):
        if not self.emails_prontos:
            texto = "Carregando e-mails..."
        elif self.emails is None:
            texto = "Gmail nao conectado.\nVeja a linha Gmail: no CMD."
        elif not self.emails:
            texto = "Nenhum e-mail recente."
        else:
            texto = "\n\n".join(f"{e['de']}\n{e['assunto']}" for e in self.emails)
        self.label_emails.configure(text=texto)

    def _loop_emails(self):
        while self.rodando:
            resultado = ler_emails_recentes()
            self.fila.put(("emails", resultado))
            espera = 60 if resultado is None else 300
            for _ in range(espera):
                if not self.rodando:
                    return
                time.sleep(1)

    def _loop_clima(self):
        while self.rodando:
            self.fila.put(("clima", buscar_clima()))
            for _ in range(900):
                if not self.rodando:
                    return
                time.sleep(1)

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
                    self.label_acao.configure(text=dados)
                elif tipo == "clima":
                    self.clima = dados
                    self.label_clima.configure(text=dados)
                elif tipo == "emails":
                    self.emails = dados
                    self.emails_prontos = True
                    self._mostrar_emails()
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