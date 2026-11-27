import json
import math
import os
import queue
import random
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import xml.etree.ElementTree as ET

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
URLS_NOTICIAS = (
    "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
    "https://agenciabrasil.ebc.com.br/feed/ultimasnoticias/feed.xml",
    "http://agenciabrasil.ebc.com.br/feed/ultimasnoticias/feed.xml",
)
NS = {"a": "http://www.w3.org/2005/Atom"}
URL_VIDEOS = "https://www.youtube.com/feeds/videos.xml?channel_id="
CANAIS = (
    ("Filipe Deschamps", "UCU5JicSrEM5A63jkJ2QvGYw"),
    ("Codigo Fonte TV", "@codigofontetv"),
    ("Curso em Video", "@cursoemvideo"),
)
_ids_canais = {}

FUNDO = "#030912"
GRADE = "#061424"
PAINEL = "#050e1a"
BORDA = "#0d3350"
TEXTO = "#d7f1ff"
SUAVE = "#6f9bb8"
TITULO = "#5cc8f0"
CIANO = "#22d3ee"
VERDE = "#34d399"
VERMELHO = "#ef4444"
CORES = {
    "dormindo": "#2f7fb0",
    "ouvindo": "#22d3ee",
    "falando": "#60a5fa",
    "pensando": "#f59e0b",
    "mudo": "#ef4444",
}
FREQ = {"dormindo": 0.3, "ouvindo": 0.8, "falando": 2.2, "pensando": 1.5, "mudo": 0.2}
VELOCIDADE = {"dormindo": 14, "ouvindo": 40, "falando": 80, "pensando": 210, "mudo": 0}
DICAS = {
    "dormindo": "Diga Jarvis para me chamar",
    "ouvindo": "Estou ouvindo",
    "falando": "Estou respondendo",
    "pensando": "Pensando na resposta",
    "mudo": "Microfone desligado",
}
DIAS = ("SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO")
F9 = ("Consolas", 9)
F9B = ("Consolas", 9, "bold")


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
    f = max(0.0, min(1.0, f))
    a = [int(cor_a[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * f):02x}" for x, y in zip(a, b))


def saudacao():
    h = time.localtime().tm_hour
    if h < 12:
        return "BOM DIA, SENHOR. EU SOU O JARVIS."
    if h < 18:
        return "BOA TARDE, SENHOR. EU SOU O JARVIS."
    return "BOA NOITE, SENHOR. EU SOU O JARVIS."


def resposta_local(comando, noticias, emails, clima, agora):
    f = " " + " ".join(limpar(comando).split()) + " "
    palavras = f.split()
    if any(p.startswith("noticia") or p.startswith("manchete") for p in palavras):
        if not noticias:
            return "Ainda não consegui carregar as notícias."
        return "As principais notícias são. " + " ".join(t.rstrip(".") + "." for t in noticias[:3])
    if (any(p in ("email", "emails", "gmail", "correio") for p in palavras)
            or " e mail " in f or " e mails " in f or "caixa de entrada" in f):
        if emails is None:
            return "Não consegui acessar os seus e-mails agora."
        if not emails:
            return "Você não tem e-mails recentes."
        partes = []
        for e in emails[:3]:
            remetente = e.get("de") or "remetente desconhecido"
            partes.append("De " + remetente + ". Assunto: " + e.get("assunto", "").rstrip(".") + ".")
        return "Seus e-mails mais recentes são. " + " ".join(partes)
    if any(p in ("clima", "temperatura", "previsao", "chover", "chuva") for p in palavras):
        if not clima or "indisponivel" in clima or "consultando" in clima:
            return "Ainda não consegui consultar o clima."
        return clima.replace("\n", ". ").replace("\u00b0C", " graus") + "."
    if " que horas " in f or " horas sao " in f or " hora e " in f:
        return "São " + str(agora.tm_hour) + " horas e " + str(agora.tm_min) + " minutos."
    if " que dia " in f or " data de hoje " in f or " qual a data " in f:
        return "Hoje é " + time.strftime("%d/%m/%Y", agora) + "."
    return None


def resposta_videos(comando, videos):
    palavras = limpar(comando).split()
    if not any(p.startswith("video") for p in palavras):
        return None
    if not videos:
        return "Ainda não consegui carregar os vídeos."
    partes = [v["canal"] + ". " + v["titulo"].rstrip(".?!") + "." for v in videos[:3]]
    return "Os vídeos mais recentes são. " + " ".join(partes)


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


def buscar_noticias(quantidade=3):
    for url in URLS_NOTICIAS:
        try:
            pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Jarvis"})
            with urllib.request.urlopen(pedido, timeout=10) as resposta:
                raiz = ET.fromstring(resposta.read())
            titulos = []
            for item in raiz.iter("item"):
                titulo = (item.findtext("title") or "").strip()
                if titulo:
                    titulos.append(titulo[:90])
                if len(titulos) >= quantidade:
                    break
            if titulos:
                return titulos
        except Exception as erro:
            print("Noticias:", erro)
    return None


def _pedir(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Jarvis"})
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        return resposta.read()


def resolver_canal(ref):
    if ref.startswith("UC"):
        return ref
    if ref in _ids_canais:
        return _ids_canais[ref]
    html = _pedir("https://www.youtube.com/" + ref).decode("utf-8", "ignore")
    padroes = (
        r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
        r'"externalId":"(UC[\w-]{22})"',
        r'"channelId":"(UC[\w-]{22})"',
    )
    for padrao in padroes:
        achado = re.search(padrao, html)
        if achado:
            _ids_canais[ref] = achado.group(1)
            return achado.group(1)
    raise ValueError("nao achei o codigo do canal " + ref)


def buscar_videos():
    resultados = []
    for nome, ref in CANAIS:
        try:
            codigo = resolver_canal(ref)
            raiz = ET.fromstring(_pedir(URL_VIDEOS + codigo))
            entrada = raiz.find("a:entry", NS)
            titulo = (entrada.findtext("a:title", "", NS) or "").strip()
            if titulo:
                resultados.append({"canal": nome, "titulo": titulo[:80]})
        except Exception as erro:
            print("Videos:", nome, erro)
    return resultados or None


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
        self.microfone = True
        self.estado = "dormindo"
        self.clima = CLIMA_PADRAO
        self.noticias = None
        self.videos = None
        self.emails = None
        self.emails_prontos = False
        self.ultima_acao = "nenhuma ainda"
        self.mensagens = []
        self.fase = 0.0
        self.giro = 0.0
        self.t = 0.0
        self.ultimo_quadro = time.time()
        self.erro_impresso = False
        self.r = {}
        self.W, self.H = 1280, 760
        self.cx, self.cy, self.R = 640, 300, 140
        self.y_sauda, self.y_estado, self.y_input = 460, 494, 700
        self.chat = (320, 520, 960, 660)
        self.barra = (320, 676, 960, 724)
        self.particulas = [
            [random.random(), random.random(), random.uniform(0.01, 0.05), random.choice((1, 2, 2, 3))]
            for _ in range(32)
        ]

        raiz.title("Jarvis")
        raiz.geometry("1280x760")
        raiz.configure(bg=FUNDO)
        raiz.minsize(1000, 640)

        self.f_hora = tkfont.Font(family="Consolas", size=30, weight="bold")
        self.f_sauda = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.saudacao_total = saudacao()
        self.larg_sauda = self.f_sauda.measure(self.saudacao_total)
        self.saudacao_inicio = time.time()

        self.c = tk.Canvas(raiz, bg=FUNDO, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.entrada = tk.Entry(self.c, font=("Consolas", 11), bg=PAINEL, fg=TEXTO,
                                insertbackground=CIANO, relief="flat", bd=0, highlightthickness=0)
        self.id_entrada = self.c.create_window(0, 0, window=self.entrada, anchor="w")
        self.entrada.bind("<Return>", lambda e: self.enviar_digitado())

        self.c.tag_bind("mic", "<Button-1>", lambda e: self.alternar_microfone())
        self.c.tag_bind("enviar", "<Button-1>", lambda e: self.enviar_digitado())
        for etiqueta in ("mic", "enviar"):
            self.c.tag_bind(etiqueta, "<Enter>", lambda e: self.c.configure(cursor="hand2"))
            self.c.tag_bind(etiqueta, "<Leave>", lambda e: self.c.configure(cursor=""))
        self.c.bind("<Configure>", lambda e: self._layout())

        self._layout()
        self.raiz.after(100, self._processar_fila)
        self.raiz.after(33, self._quadro)
        self.raiz.after(1000, self._atualizar_painel)
        threading.Thread(target=self._loop_emails, daemon=True).start()
        threading.Thread(target=self._loop_clima, daemon=True).start()
        threading.Thread(target=self._loop_noticias, daemon=True).start()
        threading.Thread(target=self._loop_videos, daemon=True).start()
        threading.Thread(target=self._loop_escuta, daemon=True).start()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)

    # ---------- layout e desenho estatico ----------

    def _layout(self):
        c = self.c
        W = max(c.winfo_width(), 900)
        H = max(c.winfo_height(), 560)
        self.W, self.H = W, H
        margem, lat, topo, base = 16, 288, 70, H - 16

        def coluna(x0, pesos, nomes):
            total = base - topo - 10 * (len(pesos) - 1)
            y = topo
            for nome, p in zip(nomes, pesos):
                h = total * p
                self.r[nome] = (x0, y, x0 + lat, y + h)
                y += h + 10

        coluna(margem, (0.20, 0.20, 0.60), ("hora", "clima", "noticias"))
        coluna(W - margem - lat, (0.36, 0.34, 0.30), ("emails", "videos", "status"))
        xc0 = margem + lat + 14
        xc1 = W - margem - lat - 14
        self.cx = (xc0 + xc1) / 2
        hc = H - topo - 16
        self.R = max(60, min(0.23 * hc, (xc1 - xc0) * 0.46))
        self.cy = topo + self.R + 14
        self.y_sauda = self.cy + self.R + 16
        self.y_estado = self.y_sauda + 34
        cw = min(xc1 - xc0, 760)
        self.chat = (self.cx - cw / 2, self.y_estado + 30, self.cx + cw / 2, H - 84)
        self.y_input = H - 44
        self.barra = (self.cx - cw / 2, self.y_input - 24, self.cx + cw / 2, self.y_input + 24)

        c.delete("estatico")
        for x in range(0, W, 44):
            c.create_line(x, 0, x, H, fill=GRADE, tags="estatico")
        for y in range(0, H, 44):
            c.create_line(0, y, W, y, fill=GRADE, tags="estatico")

        c.create_text(24, 32, text="J.A.R.V.I.S", anchor="w", font=("Consolas", 20, "bold"),
                      fill=CIANO, tags="estatico")
        c.create_text(W - 24, 32, text="BRASILIA \u00b7 DF", anchor="e", font=("Consolas", 10, "bold"),
                      fill=SUAVE, tags="estatico")
        c.create_line(16, 58, W - 16, 58, fill=BORDA, tags="estatico")
        self._colchetes(16, 58, W - 16, 60, 18, TITULO, 2)

        nomes = {
            "hora": "HORA LOCAL", "clima": "CLIMA", "noticias": "NOTICIAS",
            "emails": "CAIXA DE ENTRADA", "videos": "VIDEOS RECENTES", "status": "STATUS DO SISTEMA",
        }
        for chave, titulo in nomes.items():
            self._painel(self.r[chave], titulo)
        self._painel(self.chat, "COMUNICACAO")

        x0, y0, x1, y1 = self.barra
        c.create_rectangle(x0, y0, x1, y1, fill=PAINEL, outline=BORDA, tags="estatico")
        self._colchetes(x0, y0, x1, y1, 10, CIANO, 2)
        c.create_rectangle(x1 - 100, self.y_input - 16, x1 - 10, self.y_input + 16, fill="#073b5c",
                           outline=CIANO, tags=("estatico", "enviar"))
        c.create_text(x1 - 55, self.y_input, text="ENVIAR", font=("Consolas", 10, "bold"), fill=TEXTO,
                      tags=("estatico", "enviar"))
        c.coords(self.id_entrada, x0 + 54, self.y_input)
        c.itemconfig(self.id_entrada, width=max(60, int(x1 - x0 - 54 - 112)), height=32)

        self._desenhar_mic()
        self._desenhar_dados()

    def _colchetes(self, x0, y0, x1, y1, n, cor, largura):
        for x, y, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            self.c.create_line(x, y + dy * n, x, y, x + dx * n, y, fill=cor, width=largura, tags="estatico")

    def _painel(self, r, titulo):
        x0, y0, x1, y1 = r
        self.c.create_rectangle(x0, y0, x1, y1, fill=PAINEL, outline=BORDA, tags="estatico")
        self._colchetes(x0, y0, x1, y1, 12, CIANO, 2)
        self.c.create_text(x0 + 16, y0 + 16, text=titulo, anchor="w", font=F9B, fill=TITULO, tags="estatico")
        self.c.create_line(x0 + 12, y0 + 29, x1 - 12, y0 + 29, fill=BORDA, tags="estatico")

    def _desenhar_mic(self):
        c = self.c
        c.delete("mic")
        ligado = self.microfone
        borda = CIANO if ligado else VERMELHO
        fundo = "#08263b" if ligado else "#2a1215"
        cor = TEXTO if ligado else "#fca5a5"
        x0 = self.barra[0] + 6
        y0 = self.y_input - 20
        t = ("mic",)
        c.create_oval(x0, y0, x0 + 40, y0 + 40, fill=fundo, outline=borda, width=2, tags=t)
        c.create_oval(x0 + 15, y0 + 9, x0 + 25, y0 + 19, fill=cor, outline=cor, tags=t)
        c.create_rectangle(x0 + 15, y0 + 14, x0 + 25, y0 + 22, fill=cor, outline=cor, tags=t)
        c.create_oval(x0 + 15, y0 + 17, x0 + 25, y0 + 27, fill=cor, outline=cor, tags=t)
        c.create_arc(x0 + 11, y0 + 13, x0 + 29, y0 + 29, start=200, extent=140, style="arc",
                     outline=cor, width=2, tags=t)
        c.create_line(x0 + 20, y0 + 29, x0 + 20, y0 + 32, fill=cor, width=2, tags=t)
        c.create_line(x0 + 16, y0 + 32, x0 + 24, y0 + 32, fill=cor, width=2, tags=t)
        if not ligado:
            c.create_line(x0 + 9, y0 + 31, x0 + 31, y0 + 9, fill=VERMELHO, width=3, tags=t)

    # ---------- dados (textos dos paineis) ----------

    def _txt(self, x, y, texto, fonte, cor, largura, limite):
        t = self.c.create_text(x, y, text=texto, font=fonte, fill=cor, width=largura,
                               anchor="nw", tags="dados")
        caixa = self.c.bbox(t)
        if caixa and caixa[3] > limite:
            self.c.delete(t)
            return None
        return caixa[3] if caixa else y

    def _dados_lista(self, r, itens, cor_titulo, cor_detalhe, vazio):
        x0, y0, x1, y1 = r
        x = x0 + 16
        larg = x1 - x0 - 32
        limite = y1 - 8
        y = y0 + 38
        if not itens:
            self._txt(x, y, vazio, F9, SUAVE, larg, limite)
            return
        for i, (titulo, detalhe) in enumerate(itens):
            if i:
                self.c.create_line(x, y - 5, x + larg, y - 5, fill=BORDA, tags="dados")
            if titulo:
                y = self._txt(x, y, titulo, F9B, cor_titulo, larg, limite)
                if y is None:
                    return
                y += 1
            y = self._txt(x, y, detalhe, F9, cor_detalhe, larg, limite)
            if y is None:
                return
            y += 11

    def _desenhar_dados(self):
        c = self.c
        c.delete("dados")
        agora = time.localtime()

        x0, y0, x1, y1 = self.r["hora"]
        c.create_text(x0 + 16, y0 + 36, text=time.strftime("%H:%M", agora), anchor="nw",
                      font=self.f_hora, fill=TEXTO, tags="dados")
        c.create_text(x0 + 16 + self.f_hora.measure("00:00") + 6, y0 + 56, text=time.strftime("%S", agora),
                      anchor="nw", font=("Consolas", 14, "bold"), fill=CIANO, tags="dados")
        c.create_text(x0 + 16, y0 + 36 + 50, text=DIAS[agora.tm_wday] + "  " + time.strftime("%d/%m/%Y", agora),
                      anchor="nw", font=F9, fill=SUAVE, tags="dados")

        x0, y0, x1, y1 = self.r["clima"]
        achado = re.search(r"(-?\d+)\u00b0C", self.clima)
        grande = achado.group(1) + "\u00b0C" if achado else "--"
        c.create_text(x0 + 16, y0 + 34, text=grande, anchor="nw", font=("Consolas", 24, "bold"),
                      fill=CIANO, tags="dados")
        linhas = self.clima.split("\n")
        descricao = re.sub(r"\s*-?\d+\u00b0C,?\s*", " ", linhas[0]).replace(":  ", ": ").strip()
        texto = "\n".join([descricao] + linhas[1:])
        self._txt(x0 + 16, y0 + 34 + 38, texto, F9, TEXTO, x1 - x0 - 32, y1 - 6)

        itens = [(None, "%02d  %s" % (i, t)) for i, t in enumerate(self.noticias or [], 1)]
        vazio = "Carregando..." if self.noticias is None else "Noticias indisponiveis."
        self._dados_lista(self.r["noticias"], itens, CIANO, TEXTO, vazio)
        if self.noticias:
            x0, y0, x1, y1 = self.r["noticias"]
            c.create_text(x0 + 16, y1 - 8, text="Fonte: Agencia Brasil", anchor="sw", font=("Consolas", 8),
                          fill=SUAVE, tags="dados")

        if not self.emails_prontos:
            itens, vazio = None, "Carregando e-mails..."
        elif self.emails is None:
            itens, vazio = None, "Gmail nao conectado.\nVeja a linha Gmail: no CMD."
        elif not self.emails:
            itens, vazio = None, "Nenhum e-mail recente."
        else:
            itens = [(e["de"] or "Remetente desconhecido", e["assunto"]) for e in self.emails[:4]]
            vazio = ""
        self._dados_lista(self.r["emails"], itens, CIANO, TEXTO, vazio)

        if self.videos:
            itens = [(v["canal"], v["titulo"]) for v in self.videos]
            vazio = ""
        else:
            itens = None
            vazio = "Carregando videos..." if self.videos is None else "Videos indisponiveis."
        self._dados_lista(self.r["videos"], itens, CIANO, TEXTO, vazio)

        x0, y0, x1, y1 = self.r["status"]
        y = y0 + 40
        c.create_text(x0 + 16, y, text="MICROFONE", anchor="nw", font=F9, fill=SUAVE, tags="dados")
        c.create_text(x1 - 16, y, text="LIGADO" if self.microfone else "DESLIGADO", anchor="ne", font=F9B,
                      fill=VERDE if self.microfone else VERMELHO, tags="dados")
        c.create_text(x0 + 16, y + 22, text="MODO", anchor="nw", font=F9, fill=SUAVE, tags="dados")
        c.create_text(x1 - 16, y + 22, text="ATIVO" if self.acordado else "EM ESPERA", anchor="ne", font=F9B,
                      fill=CIANO if self.acordado else SUAVE, tags="dados")
        c.create_text(x0 + 16, y + 44, text="ULTIMA ACAO", anchor="nw", font=F9, fill=SUAVE, tags="dados")
        self._txt(x0 + 16, y + 62, self.ultima_acao, F9, TEXTO, x1 - x0 - 32, y1 - 6)

        x0, y0, x1, y1 = self.chat
        topo_chat = y0 + 36
        y = y1 - 10
        larg = x1 - x0 - 32
        for quem, texto in reversed(self.mensagens[-12:]):
            voce = quem == "Voce"
            rotulo = "VOCE \u25b8 " if voce else "JARVIS \u25b8 "
            t = c.create_text(x0 + 16, y, text=rotulo + texto, anchor="sw", font=F9,
                              fill="#8fb3cc" if voce else "#7fe0ff", width=larg, tags="dados")
            caixa = c.bbox(t)
            if not caixa or caixa[1] < topo_chat:
                c.delete(t)
                break
            y = caixa[1] - 8

    # ---------- animacao ----------

    def _quadro(self):
        try:
            self._animar()
        except Exception as erro:
            if not self.erro_impresso:
                print("Animacao:", erro)
                self.erro_impresso = True
        if self.rodando:
            self.raiz.after(33, self._quadro)

    def _animar(self):
        c = self.c
        agora = time.time()
        dt = min(agora - self.ultimo_quadro, 0.2)
        self.ultimo_quadro = agora
        est = self.estado
        self.fase += dt * FREQ[est] * 2 * math.pi
        self.giro = (self.giro + dt * VELOCIDADE[est]) % 360
        self.t += dt
        f = 0.65 + 0.35 * math.sin(self.fase)
        cor = CORES[est]
        dim = misturar(FUNDO, cor, 0.30)
        med = misturar(FUNDO, cor, 0.55)
        W, H = self.W, self.H
        cx, cy, R = self.cx, self.cy, self.R
        g = math.radians(self.giro)
        cos, sin = math.cos, math.sin
        c.delete("anim")

        y = (self.t * 70) % H
        c.create_line(0, y, W, y, fill="#0a2740", tags="anim")
        for p in self.particulas:
            p[1] -= p[2] * dt
            if p[1] < 0:
                p[1] = 1.0
                p[0] = random.random()
            px, py = p[0] * W, p[1] * H
            c.create_oval(px, py, px + p[3], py + p[3], fill="#12476b", outline="", tags="anim")

        for raio, k in ((1.00, 0.30), (0.64, 0.45), (0.50, 0.25)):
            r = R * raio
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=misturar(FUNDO, cor, k), width=1, tags="anim")

        for i in range(60):
            a = g + i * 2 * math.pi / 60
            longo = i % 5 == 0
            r0 = R * 0.90
            r1 = R * (0.99 if longo else 0.95)
            c.create_line(cx + r0 * cos(a), cy + r0 * sin(a), cx + r1 * cos(a), cy + r1 * sin(a),
                          fill=cor if longo else dim, width=2 if longo else 1, tags="anim")
        for i in range(40):
            a = -g * 1.6 + i * 2 * math.pi / 40
            r0, r1 = R * 0.70, R * 0.74
            c.create_line(cx + r0 * cos(a), cy + r0 * sin(a), cx + r1 * cos(a), cy + r1 * sin(a),
                          fill=med, width=1, tags="anim")

        def arco(raio, inicio, extensao, largura, cor_arco):
            r = R * raio
            caixa = (cx - r, cy - r, cx + r, cy + r)
            c.create_arc(*caixa, start=inicio % 360, extent=extensao, style="arc",
                         outline=misturar(FUNDO, cor, 0.22), width=largura + 6, tags="anim")
            c.create_arc(*caixa, start=inicio % 360, extent=extensao, style="arc",
                         outline=cor_arco, width=largura, tags="anim")

        for k in range(3):
            arco(0.82, self.giro + k * 120, 70, 4, cor)
        for k in range(2):
            arco(0.64, -self.giro * 1.8 + k * 180, 40, 3, med)

        amp = {"falando": 1.0, "ouvindo": 0.22, "pensando": 0.10}.get(est, 0.0)
        if amp > 0:
            n = 64
            for i in range(n):
                a = i * 2 * math.pi / n + g * 0.3
                v = (0.5 + 0.5 * sin(self.fase * 3.0 + i * 0.9)) * (0.5 + 0.5 * sin(self.fase * 1.7 + i * 2.3))
                r0 = R * 0.52
                r1 = r0 + R * 0.11 * (0.15 + v * amp)
                c.create_line(cx + r0 * cos(a), cy + r0 * sin(a), cx + r1 * cos(a), cy + r1 * sin(a),
                              fill=cor, width=2, tags="anim")

        for raio, inten in ((0.44, 0.10), (0.38, 0.18), (0.32, 0.30), (0.26, 0.48), (0.20, 0.70), (0.14, 0.90)):
            r = R * raio * (0.92 + 0.10 * f)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=misturar(FUNDO, cor, inten), outline="", tags="anim")

        pontos = []
        for k in range(6):
            a = -g * 0.7 + k * math.pi / 3
            pontos += [cx + R * 0.30 * cos(a), cy + R * 0.30 * sin(a)]
        c.create_polygon(pontos, fill="", outline=cor, width=2, tags="anim")
        r = R * 0.08 * (0.9 + 0.2 * f)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=misturar(cor, "#ffffff", 0.75), outline="", tags="anim")

        digitado = self.saudacao_total[: int((agora - self.saudacao_inicio) * 24)]
        if len(digitado) < len(self.saudacao_total):
            digitado += "_"
        c.create_text(self.cx - self.larg_sauda / 2, self.y_sauda, text=digitado, anchor="nw",
                      font=self.f_sauda, fill="#bfeaff", tags="anim")
        c.create_text(self.cx, self.y_estado, text="\u25cf " + est.upper() + "  \u00b7  " + DICAS[est],
                      anchor="n", font=("Consolas", 10, "bold"), fill=cor, tags="anim")

        pisca = misturar("#0a3a28", VERDE, 0.5 + 0.5 * sin(self.t * 3))
        c.create_text(W / 2, 32, text="\u25cf SISTEMA ONLINE", font=("Consolas", 10, "bold"),
                      fill=pisca, tags="anim")

        c.tag_raise("anim", "estatico")

    # ---------- controle ----------

    def alternar_microfone(self):
        self.microfone = not self.microfone
        self._desenhar_mic()
        if self.microfone:
            self._definir_estado("ouvindo" if self.acordado else "dormindo")
            self.ultima_acao = "Microfone ligado"
        else:
            self._definir_estado("mudo")
            self.ultima_acao = "Microfone desligado"
        self._desenhar_dados()

    def escrever(self, quem, texto):
        self.mensagens.append((quem, texto))
        self._desenhar_dados()

    def _definir_estado(self, estado):
        self.estado = estado

    def _atualizar_painel(self):
        self._desenhar_dados()
        if self.rodando:
            self.raiz.after(1000, self._atualizar_painel)

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

    def _loop_noticias(self):
        while self.rodando:
            titulos = buscar_noticias()
            self.fila.put(("noticias", titulos or []))
            espera = 120 if not titulos else 1800
            for _ in range(espera):
                if not self.rodando:
                    return
                time.sleep(1)

    def _loop_videos(self):
        while self.rodando:
            videos = buscar_videos()
            self.fila.put(("videos", videos or []))
            espera = 120 if not videos else 1800
            for _ in range(espera):
                if not self.rodando:
                    return
                time.sleep(1)

    def _processar_fila(self):
        mudou = False
        try:
            while True:
                tipo, dados = self.fila.get_nowait()
                if tipo == "escrever":
                    self.mensagens.append(dados)
                    mudou = True
                elif tipo == "estado":
                    self._definir_estado(dados)
                elif tipo == "acao":
                    self.ultima_acao = dados
                    mudou = True
                elif tipo == "clima":
                    self.clima = dados
                    mudou = True
                elif tipo == "noticias":
                    self.noticias = dados
                    mudou = True
                elif tipo == "videos":
                    self.videos = dados
                    mudou = True
                elif tipo == "emails":
                    self.emails = dados
                    self.emails_prontos = True
                    mudou = True
        except queue.Empty:
            pass
        if mudou:
            self._desenhar_dados()
        if self.rodando:
            self.raiz.after(100, self._processar_fila)

    def _loop_escuta(self):
        self.fila.put(("estado", "dormindo"))
        while self.rodando:
            if self.falando.is_set():
                threading.Event().wait(0.05)
                continue
            if not self.microfone:
                self.fila.put(("estado", "mudo"))
                threading.Event().wait(0.3)
                continue
            self.fila.put(("estado", "ouvindo" if self.acordado else "dormindo"))
            try:
                frase = ouvidos.ouvir()
            except Exception:
                threading.Event().wait(1)
                continue
            if frase and self.microfone and not self.falando.is_set():
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

    def _falar_longo(self, texto):
        self.fila.put(("escrever", ("Jarvis", texto)))
        self.fila.put(("estado", "falando"))
        self.falando.set()
        try:
            voz.falar_em_pedacos(iter([texto]))
        finally:
            self.falando.clear()

    def _executar(self, comando):
        self.fila.put(("estado", "pensando"))
        if any(p in limpar(comando).split() for p in PALAVRAS_SAIR):
            self._falar("Encerrando. Ate logo.")
            self.raiz.after(0, self.fechar)
            return
        local = resposta_local(comando, self.noticias, self.emails, self.clima, time.localtime())
        if local is None:
            local = resposta_videos(comando, self.videos)
        if local is not None:
            self.fila.put(("acao", "Li os dados do painel"))
            self._falar_longo(local)
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
