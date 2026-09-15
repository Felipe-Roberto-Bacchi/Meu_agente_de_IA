import ollama
from MODULOS.system.logger import log

def _e_despedida(texto: str) -> bool:
    if not texto or not texto.strip():
        return False
    try:
        prompt = (
            "Você decide se o usuário está EXPLICITAMENTE se despedindo do assistente.\n"
            "Só responda SIM se houver palavras claras de despedida como: tchau, até logo, pode dormir, encerrar, desligar, obrigado pode ir, até mais.\n"
            "Instruções, perguntas, pedidos ou comentários são NAO.\n"
            "Responda APENAS: SIM ou NAO.\n\n"
            f"Frase: \"{texto}\"\n"
            "É uma despedida explícita?"
        )
        resp = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}
        )
        resposta = resp["message"]["content"].strip().upper()
        return resposta.startswith("SIM")
    except Exception as e:
        log.debug(f"Erro LLM despedida: {e}")
        despedidas = ["tchau", "até logo", "pode dormir", "encerrar", "desligar"]
        texto_lower = texto.lower()
        if any(d in texto_lower for d in despedidas):
            return True
        return False

def verificar_despedida(texto: str) -> bool:
    return _e_despedida(texto)
