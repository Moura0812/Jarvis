import os
import re

import httpx

MODELOS = ("gemini-flash-latest", "gemini-3.5-flash-lite")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
INSTRUCAO = (
    "Voce e o Jarvis, um assistente de voz. Pesquise na internet e responda em "
    "portugues do Brasil, em no maximo 2 frases curtas, com menos de 25 palavras "
    "no total, sem markdown, sem listas e sem citar enderecos de sites."
)
ASSUNTOS_ATUAIS = ("cotacao", "dolar", "euro", "bitcoin", "placar", "quem ganhou", "preco d", "ultimas noticias", "ontem")
MOEDAS = {"dola": ("USD-BRL", "dolar"), "euro": ("EUR-BRL", "euro"), "bitcoin": ("BTC-BRL", "bitcoin")}


def extrair_consulta(f):
    pediu = re.search(r"\b(pesquis\w*|procur\w*|busqu\w*|busc\w*)\b", f)
    if not pediu and any(k in f for k in ASSUNTOS_ATUAIS):
        return f
    return _extrair(f)


def _extrair(f):
    m = re.search(r"\b(pesquis\w*|procur\w*|busqu\w*|busc\w*)\b(.*)", f)
    if not m:
        return None
    consulta = m.group(2).strip()
    for _ in range(4):
        consulta = re.sub(
            r"^(na internet|no google|na web|sobre|a respeito de|por|para mim|pra mim|de|que)\b\s*",
            "",
            consulta,
        ).strip()
    return consulta


def _gemini(consulta):
    corpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCAO}]},
        "contents": [{"role": "user", "parts": [{"text": consulta}]}],
        "tools": [{"google_search": {}}],
    }
    cabecalho = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    for modelo in MODELOS:
        try:
            r = httpx.post(URL.format(modelo), json=corpo, headers=cabecalho, timeout=30)
            if r.status_code == 429:
                print("Gemini no limite de pedidos, usando plano B.")
                return None
            r.raise_for_status()
            partes = r.json()["candidates"][0]["content"]["parts"]
            texto = " ".join(p.get("text", "") for p in partes).strip()
            if texto:
                return texto
        except Exception as erro:
            print("Erro na pesquisa com", modelo, ":", erro)
    return None


def _moedas(f):
    pares = [par for chave, par in MOEDAS.items() if chave in f]
    if not pares:
        return None
    lista = ",".join(p[0] for p in pares)
    r = httpx.get("https://economia.awesomeapi.com.br/json/last/" + lista, timeout=10)
    r.raise_for_status()
    dados = r.json()
    frases = []
    for codigo, nome in pares:
        valor = float(dados[codigo.replace("-", "")]["bid"])
        if valor >= 1000:
            texto = format(round(valor), ",").replace(",", ".")
        else:
            texto = format(valor, ".2f").replace(".", ",")
        frases.append("O " + nome + " esta cotado a " + texto + " reais.")
    return " ".join(frases)


def _wikipedia(consulta):
    assunto = re.sub(r"^(quem foi|quem e|o que e|o que sao|qual e|quais sao)\s+(o |a |os |as )?", "", consulta).strip()
    r = httpx.get(
        "https://pt.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": assunto,
            "gsrlimit": 1,
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "format": "json",
        },
        headers={"User-Agent": "JarvisAssistente/0.1 (projeto pessoal; https://github.com/moura0812/jarvis)"},
        timeout=10,
    )
    r.raise_for_status()
    paginas = r.json().get("query", {}).get("pages", {})
    if not paginas:
        return None
    pagina = sorted(paginas.values(), key=lambda p: p.get("index", 0))[0]
    texto = pagina.get("extract", "").strip()
    if not texto:
        return None
    frases = re.split(r"(?<=[.!?])\s+", texto)
    return "Segundo a Wikipedia, " + " ".join(frases[:2])[:400]


def pesquisar(consulta):
    texto = _gemini(consulta)
    if texto:
        return texto
    for plano_b in (_moedas, _wikipedia):
        try:
            texto = plano_b(consulta)
            if texto:
                return texto
        except Exception as erro:
            print("Erro no plano B:", erro)
    return None