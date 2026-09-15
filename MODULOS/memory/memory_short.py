# memory_short.py
from collections import deque

# Mantém as últimas 10 interações
MAX_MENSAGENS = 10 
contexto_atual = deque(maxlen=MAX_MENSAGENS)

def adicionar_mensagem(role, content):
    """Adiciona uma mensagem ao histórico."""
    contexto_atual.append({'role': role, 'content': content})

def obter_contexto(system_prompt="Você é o Jarvis. Responda de forma técnica e curta."):
    """Retorna a lista de mensagens para o Ollama."""
    mensagens = [{'role': 'system', 'content': system_prompt}]
    mensagens.extend(list(contexto_atual))
    return mensagens
