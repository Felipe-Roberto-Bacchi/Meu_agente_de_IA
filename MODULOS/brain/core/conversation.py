import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_short
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log

async def gerar_resposta_conversa(texto: str, especialidade: str = "CONVERSA") -> str:
    print(f"\n[MOCK/TESTE] Modelo de inteligência para '{especialidade}' DESATIVADO temporariamente.")
    return f"Recebi seu comando: '{texto}'. O cérebro foi desativado temporariamente para testes do sistema de voz."
