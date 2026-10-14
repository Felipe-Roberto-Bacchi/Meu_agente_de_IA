import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_short
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log

SYSTEM_PROMPT_BASE = (
    "Você é o Jarvis, um assistente de inteligência artificial de elite, leal, eficiente, inteligente e elegante.\n"
    "Responda ao senhor com respeito, objetividade, clareza e elegância em português do Brasil.\n"
    "Suas respostas serão sintetizadas por voz, portanto evite formatações markdown excessivas, emojis exagerados ou tabelas complexas, mantendo fluidez natural."
)

async def gerar_resposta_conversa(texto: str, especialidade: str = "CONVERSA") -> str:
    """
    Gera resposta inteligente usando LLM local (Ollama) ou AirLLM,
    enriquecendo o prompt com memória de longo prazo e contexto de curto prazo.
    """
    try:
        # 1. Busca contexto semântico de longo prazo
        contexto_longo = memory_long.montar_contexto_longo(texto)
        system_prompt = SYSTEM_PROMPT_BASE
        if contexto_longo:
            system_prompt += f"\n\nContexto e memórias relevantes sobre o senhor:\n{contexto_longo}"

        if especialidade == "CODIGO":
            system_prompt += "\nVocê está atuando como especialista em programação e engenharia de software. Seja preciso e direto ao ponto."

        # 2. Monta mensagens com histórico curto
        mensagens = memory_short.obter_contexto(system_prompt=system_prompt)
        mensagens.append({"role": "user", "content": texto})

        # 3. Escolhe o melhor modelo para a especialidade
        modelo, tipo = brain_selector.escolher_melhor_modelo(especialidade)
        log.info(f"[CONVERSA] Especialidade: {especialidade} | Modelo: {modelo} ({tipo})")

        # 4. Executa modelo
        if tipo == "airllm":
            resposta = await asyncio.to_thread(airllm_module.gerar_resposta_airllm, modelo, texto, system_prompt)
        else:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(model=modelo, messages=mensagens)
            )
            resposta = response['message']['content'].strip()

        # 5. Atualiza memória de curto prazo
        memory_short.adicionar_mensagem("user", texto)
        memory_short.adicionar_mensagem("assistant", resposta)

        return resposta
    except Exception as e:
        log.error(f"[CONVERSA] Erro ao gerar resposta: {e}")
        return "Perdoe-me, senhor. Ocorreu uma oscilação temporária em meus circuitos neurais ao processar sua solicitação."
