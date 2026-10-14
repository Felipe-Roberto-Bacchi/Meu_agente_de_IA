import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice import voice_manager

async def _executar_em_background(tarefa: str):
    log.info(f"[BACKGROUND] Iniciando tarefa: {tarefa}")
    try:
        modelo, tipo = brain_selector.escolher_melhor_modelo("TAREFA_LONGA")
        prompt = (
            "Você é um especialista em planejamento. "
            f"Crie um plano detalhado, passo a passo, para a seguinte tarefa: '{tarefa}'.\n"
            "Seja criativo e minucioso."
        )
        
        if tipo == "airllm":
            resultado = await asyncio.to_thread(airllm_module.gerar_resposta_airllm, modelo, prompt, "")
        else:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(model=modelo, messages=[{'role': 'user', 'content': prompt}])
            )
            resultado = response['message']['content'].strip()
            
        log.info(f"[BACKGROUND] Tarefa '{tarefa}' concluída.")
        
        memory_long.salvar_memoria(f"resultado da tarefa {tarefa}", resultado)
        
        await atualizar_jarvis(cor_hex="#00ff00", texto="Tarefa Concluída!", padrao="tarefa")
        await voice_manager.falar("Jarvis", f"Senhor, finalizei a tarefa sobre '{tarefa}'. O resultado foi salvo na memória.", prioridade=1)

    except Exception as e:
        log.error(f"[BACKGROUND] Erro ao executar tarefa '{tarefa}': {e}")
        await voice_manager.falar("Jarvis", "Tive um problema ao processar a tarefa em segundo plano.", prioridade=1)
