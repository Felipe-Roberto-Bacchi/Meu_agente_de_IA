import asyncio
from MODULOS.skills import actions_module
from MODULOS.skills import hardware_module
from MODULOS.skills import vision_module
from MODULOS.skills import fii_monitor
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.system.logger import log

from MODULOS.brain.core.router import rotear_intencao
from MODULOS.brain.memory.handler import _processar_memoria
from MODULOS.brain.core.conversation import gerar_resposta_conversa
from MODULOS.brain.core.executor import _executar_em_background

async def processar_comando(texto_bruto: str):
    if not texto_bruto or not texto_bruto.strip():
        return "#00ffff", "conversa", None

    decisao   = await rotear_intencao(texto_bruto)
    categoria = decisao.get("categoria", "CONVERSA")
    alvo      = decisao.get("alvo")

    log.info(f"Roteador - Categoria: {categoria} | Alvo: {alvo}")

    if categoria == "HARDWARE":
        cor      = "#ffff00"
        padrao   = "hardware"
        resposta = await hardware_module.obter_status_hardware(foco=alvo)

    elif categoria == "ABRIR_APP":
        cor      = "#00ff00"
        padrao   = "app"
        resposta = actions_module.executar_comando(alvo)

    elif categoria == "MEMORIA":
        cor      = "#ff8800"
        padrao   = "memoria"
        resposta = await _processar_memoria(texto_bruto)
        
    elif categoria == "VISAO":
        cor      = "#9400D3"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Analisando tela...", padrao=padrao)
        loop = asyncio.get_running_loop()
        resposta = await loop.run_in_executor(
            None,
            vision_module.analisar_tela,
            texto_bruto
        )

    elif categoria == "TAREFA_LONGA":
        cor      = "#ff00ff"
        padrao   = "tarefa"
        resposta = f"Entendido, senhor. Iniciando tarefa complexa em segundo plano: '{alvo}'."
        asyncio.create_task(_executar_em_background(alvo))

    elif categoria == "CODIGO":
        cor      = "#3366ff"
        padrao   = "codigo"
        resposta = await gerar_resposta_conversa(texto_bruto, especialidade="CODIGO")

    elif categoria == "FINANCE":
        cor      = "#00ffcc"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Consultando mercado...", padrao=padrao)
        loop = asyncio.get_running_loop()
        resposta = await loop.run_in_executor(None, fii_monitor.obter_resumo_fiis)

    else:
        cor      = "#00ffff"
        padrao   = "conversa"
        resposta = await gerar_resposta_conversa(texto_bruto, especialidade="CONVERSA")

    return cor, padrao, resposta
