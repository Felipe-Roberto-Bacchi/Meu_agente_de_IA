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

    if categoria == "PARAR_AÇÃO":
        from MODULOS.voice import voice_manager
        voice_manager.interromper_fala_imediata()
        from MODULOS.skills import briefing_module
        try:
            briefing_module.ULTIMO_BRIEFING_ATIVO = False
        except Exception:
            pass
        await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="Ação interrompida, senhor.", padrao="conversa")
        log.info("[BRAIN] Comando de interrupção de fala/ação executado com sucesso.")
        return "#00ffff", "conversa", None

    elif categoria == "DUVIDA":
        cor      = "#ffaa00"
        padrao   = "conversa"
        pergunta = alvo if (alvo and len(alvo) > 8 and "?" in alvo) else "Senhor, o áudio cortou levemente e não compreendi com clareza. Poderia repetir o comando?"
        await atualizar_jarvis(cor_hex=cor, texto=pergunta, padrao=padrao)
        resposta = pergunta

    elif categoria == "HARDWARE":
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

    elif categoria == "DIAGNOSTICO":
        cor      = "#00ffff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Iniciando diagnóstico de sistemas...", padrao=padrao)
        from MODULOS.skills import diagnostics_module
        asyncio.create_task(diagnostics_module.executar_diagnostico_coreografado())
        resposta = None

    elif categoria == "BRIEFING":
        cor      = "#00e5ff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Iniciando Briefing Matinal...", padrao=padrao)
        from MODULOS.skills import briefing_module
        asyncio.create_task(briefing_module.executar_briefing_coreografado())
        resposta = None

    elif categoria == "BRIEFING_FOLLOWUP":
        cor      = "#00ffff"
        padrao   = "conversa"
        await atualizar_jarvis(cor_hex=cor, texto="Aprofundando detalhes...", padrao="tarefa")
        from MODULOS.skills import briefing_module
        resposta = await briefing_module.responder_followup_briefing(texto_bruto)

    elif categoria == "LEMBRETES":
        cor      = "#ffaa00"
        padrao   = "conversa"
        from MODULOS.skills import reminders_module
        resposta = reminders_module.processar_comando_voz(texto_bruto)

    elif categoria == "MUSICA":
        cor      = "#00e5ff"
        padrao   = "conversa"
        await atualizar_jarvis(cor_hex=cor, texto="Sintonizando áudio...", padrao=padrao)
        from MODULOS.skills import music_module
        resposta = await music_module.processar_comando_musica(texto_bruto)

    elif categoria == "CONTROLE_PC":
        cor      = "#00ffff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Acessando controles do sistema...", padrao=padrao)
        from MODULOS.skills import pc_control_module
        resposta = await pc_control_module.processar_comando_pc(texto_bruto)

    elif categoria == "GOOGLE_WORKSPACE":
        cor      = "#4285f4"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Conectando ao Google Workspace...", padrao=padrao)
        from MODULOS.skills import google_mcp_module
        import re
        cmd_lower = texto_bruto.lower()
        if any(k in cmd_lower for k in ["drive", "arquivo", "documento"]):
            arquivos = google_mcp_module.buscar_arquivos_google_drive(texto_bruto, max_results=5)
            if arquivos:
                titulos = [f"'{a['nome']}'" for a in arquivos[:3]]
                resposta = f"Localizei {len(arquivos)} arquivo(s) no seu Google Drive: " + ", ".join(titulos) + "."
            else:
                resposta = "Não localizei arquivos no seu Google Drive com esses critérios, senhor."
        else:
            eventos = google_mcp_module.listar_eventos_google_calendar(max_results=3)
            if eventos:
                descricoes = [f"'{e['titulo']}' às {e['horario']}" for e in eventos]
                resposta = f"Seus próximos compromissos no Google Calendar são: " + "; ".join(descricoes) + "."
            else:
                resposta = "Sua agenda do Google não possui próximos eventos agendados no momento, senhor."

    elif categoria == "WEB_MCP":
        cor      = "#0088ff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Conectando à rede / MCP...", padrao=padrao)
        from MODULOS.skills import mcp_client
        resposta = await mcp_client.executar_comandos_mcp_ou_web(texto_bruto)

    else:
        cor      = "#00ffff"
        padrao   = "conversa"
        resposta = await gerar_resposta_conversa(texto_bruto, especialidade="CONVERSA")

    return cor, padrao, resposta
