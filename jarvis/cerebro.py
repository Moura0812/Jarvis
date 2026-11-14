import os
from openai import OpenAI

cliente = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
MODELO = "gemini-3.5-flash-lite"
INSTRUCAO = "Voce e o Jarvis, um assistente pessoal inteligente e educado. Responda sempre em portugues do Brasil, de forma curta e direta. Trate o usuario no masculino."
historico = [{"role": "system", "content": INSTRUCAO}]


def perguntar(texto):
    historico.append({"role": "user", "content": texto})
    resposta = cliente.chat.completions.create(model=MODELO, messages=historico)
    conteudo = resposta.choices[0].message.content
    historico.append({"role": "assistant", "content": conteudo})
    return conteudo


if __name__ == "__main__":
    print("Jarvis no ar. Digite sair para encerrar.")
    while True:
        entrada = input("Voce: ")
        if entrada.strip().lower() == "sair":
            break
        print("Jarvis:", perguntar(entrada))
