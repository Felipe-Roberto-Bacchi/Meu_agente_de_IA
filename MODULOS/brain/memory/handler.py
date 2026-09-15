import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_long
from MODULOS.brain.core.router import _extrair_json
from MODULOS.system.logger import log

async def _processar_memoria(texto: str) -> str:
    t = texto.lower().strip()

    prompt_sistema = (
        "Você é o assistente de memória do Jarvis.\n"
        "O usuário enviou uma frase. Você deve classificar a intenção dele em uma das três ações:\n"
        "1) BUSCAR: quando o usuário pergunta por uma informação.\n"
        "2) SALVAR: quando o usuário quer que você guarde uma nova informação.\n"
        "3) APAGAR: quando o usuário quer que você esqueça algo.\n\n"
        "Sua resposta deve ser estritamente em formato JSON com chaves 'acao', 'chave', e 'valor'.\n"
        "Responda apenas com o JSON."
    )

    try:
        modelo_memoria, tipo = brain_selector.escolher_melhor_modelo("MEMORIA")
        
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo_memoria,
                messages=[
                    {'role': 'system', 'content': prompt_sistema},
                    {'role': 'user', 'content': f"Usuário: '{texto}'"}
                ],
                options={"temperature": 0}
            )
        )
        conteudo = response['message']['content']
        resultado = _extrair_json(conteudo)
    except Exception as e:
        log.error(f"LLM MEMORIA: {e}")
        resultado = None

    if not resultado or "acao" not in resultado:
        memory_long.salvar_memoria("nota", texto)
        return f"Anotei: '{texto}', senhor."
    
    acao = resultado.get("acao", "").upper()
    chave = resultado.get("chave", "")
    valor = resultado.get("valor", "")

    if acao == "APAGAR":
        return memory_long.apagar_memoria(chave)
    elif acao == "BUSCAR":
        resultado_busca = memory_long.buscar_memoria(chave)
        return resultado_busca if resultado_busca else f"Não tenho nenhuma memória sobre '{chave}', senhor."
    elif acao == "SALVAR":
        return memory_long.salvar_memoria(chave, valor)
    else:
        memory_long.salvar_memoria("nota", texto)
        return f"Anotei: '{texto}', senhor."
