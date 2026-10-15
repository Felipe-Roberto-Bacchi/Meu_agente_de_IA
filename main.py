import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import subprocess
import time
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.system.logger import log
from MODULOS.system.config import carregar_configuracao
from MODULOS.system.services import liberar_porta_8000, iniciar_ollama_se_necessario
from MODULOS.system.sync import gerenciar_downloads_iniciais
from MODULOS.system.integrity import verificar_modelos_faltantes
from MODULOS.skills import hardware_module
from MODULOS.memory import memory_long
from MODULOS.voice import voice_manager
from MODULOS.brain.selector import selector as brain_selector
from MODULOS import ear
from MODULOS import brain

CONFIG_FILE = "DADOS/config_paths.json"

_executor = ThreadPoolExecutor(max_workers=1)

async def _capturar_async() -> tuple[bool, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, ear.capturar_comando_dinamico)

async def loop_principal():
    """Loop infinito de escuta e processamento."""
    log.info("Sincronização de sentidos concluída.")
    
    # Inicia o processador de voz em background
    asyncio.create_task(voice_manager.processador_de_fala())
    # Inicia o monitoramento térmico em background
    asyncio.create_task(hardware_module.sentinela_hardware())
    
    # Saudação inicial baseada no horário
    hora = time.localtime().tm_hour
    if hora < 12: saudacao = "Bom dia, senhor."
    elif hora < 18: saudacao = "Boa tarde, senhor."
    else: saudacao = "Boa noite, senhor."
    
    await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
    await voice_manager.falar("Jarvis", saudacao, prioridade=1)
    
    estado_anterior = None
    
    while True:
        # 0. Verifica se chegou solicitação de teste de voz pela interface
        flag_teste_voz = "DADOS/teste_voz.flag"
        if os.path.exists(flag_teste_voz):
            try:
                with open(flag_teste_voz, "r", encoding="utf-8") as f:
                    texto_teste = f.read().strip()
                os.remove(flag_teste_voz)
                if texto_teste:
                    log.info(f"[TESTE DE VOZ]: \"{texto_teste}\"")
                    await atualizar_jarvis(cor_hex="#00ffff", texto=texto_teste, padrao="conversa")
                    await voice_manager.falar("Jarvis", texto_teste, prioridade=0)
            except Exception as e_teste:
                log.error(f"Erro ao processar teste_voz.flag: {e_teste}")

        # 1. Verifica se chegou comando manual de texto pela interface
        flag_manual = "DADOS/comando_manual.txt"
        if os.path.exists(flag_manual):
            try:
                with open(flag_manual, "r", encoding="utf-8") as f:
                    texto_manual = f.read().strip()
                os.remove(flag_manual)
            except Exception:
                texto_manual = ""

            if texto_manual:
                log.info(f"[COMANDO MANUAL]: \"{texto_manual}\"")
                await atualizar_jarvis(cor_hex="#00ffff", texto=f"Comando: {texto_manual}", padrao="conversa")
                memory_long.registrar_conversa_global("user", texto_manual)

                if ear.verificar_despedida(texto_manual):
                    despedida = "Até logo, senhor. Estarei aqui quando precisar."
                    await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
                    await voice_manager.falar("Jarvis", despedida, prioridade=1)
                    memory_long.registrar_conversa_global("assistant", despedida)
                    continue

                await atualizar_jarvis(cor_hex="#3366ff", texto="Pensando...", padrao="conversa")
                cor_fala, padrao, resposta = await brain.processar_comando(texto_manual)
                if resposta:
                    await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
                    log.info(f"[JARVIS]: {resposta}")
                    memory_long.registrar_conversa_global("assistant", resposta)
                    await voice_manager.falar("Jarvis", resposta, prioridade=1)
                else:
                    await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")
                continue

        tem_audio, estado_atual = await _capturar_async()
        
        if estado_atual != estado_anterior:
            if estado_atual == ear.Estado.ATIVO:
                saudacao = "Sim, senhor?"
                await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
                await voice_manager.falar("Jarvis", saudacao, prioridade=1)
                print("\n--- [ATIVO] Pronto para comandos ---")
            elif estado_anterior == ear.Estado.ATIVO and estado_atual == ear.Estado.DORMINDO:
                await atualizar_jarvis(cor_hex="#1a0033", texto="Aguardando...", padrao="dormindo")
                print("\n--- [DORMINDO] Diga 'Jarvis' para ativar ---")

        estado_anterior = estado_atual
        if not tem_audio: continue

        await atualizar_jarvis(cor_hex="#00ffff", texto="Transcrevendo áudio...", padrao="tarefa")
        texto_bruto = ear.transcrever_audio()
        if not texto_bruto:
            log.info("[EAR] Áudio capturado sem palavras reconhecíveis.")
            await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")
            continue

        log.info(f"[ESCUTADO]: \"{texto_bruto}\"")
        memory_long.registrar_conversa_global("user", texto_bruto)

        if ear.verificar_despedida(texto_bruto):
            ear.set_estado(ear.Estado.DORMINDO)
            despedida = "Até logo, senhor. Estarei aqui quando precisar."
            await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
            await voice_manager.falar("Jarvis", despedida, prioridade=1)
            memory_long.registrar_conversa_global("assistant", despedida)
            continue

        await atualizar_jarvis(cor_hex="#3366ff", texto="Pensando...", padrao="conversa")
        cor_fala, padrao, resposta = await brain.processar_comando(texto_bruto)
        if resposta:
            await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
            log.info(f"[JARVIS]: {resposta}")
            memory_long.registrar_conversa_global("assistant", resposta)
            await voice_manager.falar("Jarvis", resposta, prioridade=1)
            # Aguarda a fala iniciar e concluir para não gravar eco ou cliques
            await asyncio.sleep(0.15)
            while voice_manager.STATUS_FALANDO:
                await asyncio.sleep(0.1)
        else:
            await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")

if __name__ == "__main__":
    import webbrowser
    import traceback
    
    # 0. Garante que a porta 8000 esteja livre (libera instâncias antigas travadas)
    liberar_porta_8000()

    try:
        # 1. Garante que o Ollama esteja rodando ANTES de qualquer outra coisa
        if not iniciar_ollama_se_necessario():
            log.critical("Não foi possível iniciar o serviço Ollama.")
            input("Pressione ENTER para fechar...")
            sys.exit(1)

        config = carregar_configuracao()
        
        if not config:
            # Fluxo de Primeiro Acesso (Instalador)
            python_exe = sys.executable
            # Usamos cmd /k para garantir que a janela fique aberta se houver erro de sistema/importação
            subprocess.Popen(["cmd", "/k", python_exe, "-m", "MODULOS.system.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            time.sleep(2)
            webbrowser.open("http://localhost:8000")
            
            while not os.path.exists(CONFIG_FILE):
                time.sleep(1)
            
            config = carregar_configuracao()
            log.info("Configuração recebida! Iniciando transferência dos núcleos...")
            asyncio.run(gerenciar_downloads_iniciais(config))
            log.info("Tudo pronto! Por favor, reinicie o Jarvis.")
            time.sleep(5)
            sys.exit()

        # Fluxo Normal (Já configurado)
        
        # 1. Inicia o servidor de interface (Apenas uma vez)
        subprocess.Popen(["cmd", "/k", sys.executable, "-m", "MODULOS.system.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        webbrowser.open("http://localhost:8000")

        # 2. VERIFICAÇÃO DE INTEGRIDADE: Se faltar modelo leve, recupera apenas os leves
        if asyncio.run(verificar_modelos_faltantes(config)):
            log.warning("Núcleos neurais incompletos. Iniciando recuperação...")
            asyncio.run(gerenciar_downloads_iniciais(config, incluir_pesados=False))
            log.info("Integridade restaurada. Reiniciando fluxo principal...")

        brain_selector.calibrar_e_salvar()
        memory_long.inicializar_banco()
        # Whisper e Kokoro operam em lazy-loading sob demanda para boot quase instantâneo
        ear.calibrar_ruido(duracao=2)

        asyncio.run(loop_principal())
        
    except KeyboardInterrupt:
        log.info("Finalizado pelo usuário.")
    except Exception as e:
        log.critical("ERRO CRÍTICO NO BOOT DO JARVIS")
        log.exception(e)
        input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")
