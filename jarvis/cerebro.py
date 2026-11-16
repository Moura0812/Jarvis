import os
import time

from openai import OpenAI

cliente = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODELO = "gemini-3.5-flash-lite"

INSTRUCAO = (
    "Voce e o Jarvis, um assistente pessoal inteligente e educado. "
    "Responda sempre em portugues do Brasil, de forma curta e direta. "
    "Trate o usuario no masculino. "
    "Voce nao tem acesso a internet nem a localizacao do usuario."
)

historico = [{"role": "system", "content": INSTRUCAO}]


def perguntar(texto):
    historico.append({"role": "user", "content": texto})
    resposta = cliente.chat.completions.create(
        model=MODELO,
        messages=historico,
        reasoning_effort="low",
    )
    conteudo = resposta.choices[0].message.content or ""
    historico.append({"role": "assistant", "content": conteudo})
    return conteudo


def perguntar_em_pedacos(texto):
    historico.append({"role": "user", "content": texto})
    inicio = time.time()
    fluxo = cliente.chat.completions.create(
        model=MODELO,
        messages=historico,
        stream=True,
        reasoning_effort="low",
    )
    completo = ""
    primeiro = True
    for parte in fluxo:
        if not parte.choices:
            continue
        pedaco = parte.choices[0].delta.content or ""
        if pedaco:
            if primeiro:
                print("[tempo] Gemini 1a parte:", round(time.time() - inicio, 1), "s")
                primeiro = False
            completo += pedaco
            yield pedaco
    historico.append({"role": "assistant", "content": completo})