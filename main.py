import os
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

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
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
    
    # Saudação inicial baseada no horário
    hora = time.localtime().tm_hour
    if hora < 12: saudacao = "Bom dia, senhor."
    elif hora < 18: saudacao = "Boa tarde, senhor."
    else: saudacao = "Boa noite, senhor."
    
    await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
    await voice_manager.falar("Jarvis", saudacao, prioridade=1)
    
    estado_anterior = None
    
    while True:
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

        await atualizar_jarvis(cor_hex="#00ffff", texto="Ouvindo...", padrao="ouvindo")
        texto_bruto = ear.transcrever_audio()
        if not texto_bruto: continue

        log.info(f"[ESCUTADO]: \"{texto_bruto}\"")
        memory_long.registrar_conversa_global("user", texto_bruto)

        if ear.verificar_despedida(texto_bruto):
            ear.set_estado(ear.Estado.DORMINDO)
            despedida = "Até logo, senhor. Estarei aqui quando precisar."
            await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
            await voice_manager.falar("Jarvis", despedida, prioridade=1)
            memory_long.registrar_conversa_global("assistant", despedida)
            continue

        cor_fala, padrao, resposta = await brain.processar_comando(texto_bruto)
        if resposta:
            await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
            log.info(f"[JARVIS]: {resposta}")
            memory_long.registrar_conversa_global("assistant", resposta)
            await voice_manager.falar("Jarvis", resposta, prioridade=1)

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

        # 2. VERIFICAÇÃO DE INTEGRIDADE: Se deletou modelos ou shards, inicia recuperação
        print("\n[MOCK/TESTE] Verificação de integridade e download de modelos PESADOS pulada.")
        # if asyncio.run(verificar_modelos_faltantes(config)):
        #     log.warning("Núcleos neurais ou shards incompletos. Iniciando recuperação...")
        #     asyncio.run(gerenciar_downloads_iniciais(config))
        #     log.info("Integridade restaurada. Reiniciando fluxo principal...")

        brain_selector.calibrar_e_salvar()
        memory_long.inicializar_banco()
        ear.inicializar_whisper()

        asyncio.run(loop_principal())
        
    except KeyboardInterrupt:
        log.info("Finalizado pelo usuário.")
    except Exception as e:
        log.critical("ERRO CRÍTICO NO BOOT DO JARVIS")
        log.exception(e)
        input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")
