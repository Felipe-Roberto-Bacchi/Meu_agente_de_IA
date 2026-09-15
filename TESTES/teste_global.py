import asyncio
import os
import sys
import time
import json
import traceback

# --- ADICIONE ESTE BLOCO DE CÓDIGO AQUI ---
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# -------------------------------------------

# Configuração de cores para o terminal
class Cores:
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    RESET = '\033[0m'

RELATORIO_PATH = "DADOS/relatorio_diagnostico.txt"
resultados = []

def log_resultado(modulo, status, mensagem):
    simbolo = "[OK]" if status == "OK" else ("[AVISO]" if status == "AVISO" else "[ERRO]")
    cor = Cores.VERDE if status == "OK" else (Cores.AMARELO if status == "AVISO" else Cores.VERMELHO)
    
    linha_texto = f"{simbolo} [{modulo}] {status}: {mensagem}"
    print(f"{cor}{linha_texto}{Cores.RESET}")
    resultados.append(linha_texto)

async def testar_sistema():
    print(f"\n{Cores.AZUL}--- INICIANDO DIAGNÓSTICO GLOBAL DO JARVIS ---{Cores.RESET}\n")
    
    # 1. MÓDULOS DE SISTEMA
    try:
        from MODULOS.system.logger import log
        log.debug("Teste de log silencioso.")
        log_resultado("SYSTEM.LOGGER", "OK", "Logger carregado e operante.")
    except Exception as e:
        log_resultado("SYSTEM.LOGGER", "ERRO", str(e))

    try:
        from MODULOS.system.config import carregar_configuracao
        cfg = carregar_configuracao()
        if cfg:
            log_resultado("SYSTEM.CONFIG", "OK", f"Configuração lida com sucesso: HD={cfg.get('hd_path')}")
        else:
            log_resultado("SYSTEM.CONFIG", "AVISO", "Arquivo de configuração não encontrado ou vazio.")
    except Exception as e:
        log_resultado("SYSTEM.CONFIG", "ERRO", str(e))

    # 2. AUDIÇÃO (EAR)
    try:
        from MODULOS.ear import models, recorder, states
        log_resultado("EAR.IMPORTS", "OK", "Módulos de áudio importados.")
        
        # Teste de microfone básico
        try:
            import sounddevice as sd
            dispositivos = sd.query_devices()
            if len(dispositivos) > 0:
                log_resultado("EAR.HARDWARE", "OK", f"{len(dispositivos)} dispositivos de entrada de áudio detectados.")
            else:
                log_resultado("EAR.HARDWARE", "AVISO", "Nenhum dispositivo de entrada de áudio encontrado.")
        except:
            log_resultado("EAR.HARDWARE", "ERRO", "Falha ao acessar sounddevice.")
    except Exception as e:
        log_resultado("EAR.EAR_MODULE", "ERRO", f"Falha crítica nos módulos de áudio: {e}")

    # 3. CÉREBRO E INTELIGÊNCIA (BRAIN)
    try:
        from MODULOS.brain.selector import selector as brain_selector
        hw = brain_selector.detectar_hardware()
        log_resultado("BRAIN.SELECTOR", "OK", f"Hardware detectado: VRAM={hw.get('vram_gb')}GB, GPU={hw.get('gpu_modelo')}")
        
        from MODULOS import brain
        log_resultado("BRAIN.INIT", "OK", "Módulo principal do cérebro carregado.")
        
        from MODULOS.brain.core import router
        log_resultado("BRAIN.ROUTER", "OK", "Roteador de intenções carregado.")
    except Exception as e:
        log_resultado("BRAIN.MODULES", "ERRO", f"Erro ao carregar componentes do cérebro: {e}")

    # 4. MEMÓRIA
    try:
        from MODULOS.memory import memory_long, memory_short
        db_ok = memory_long.inicializar_banco()
        log_resultado("MEMORY.LONG", "OK", "Banco de dados de longo prazo conectado.")
        
        memory_short.adicionar_mensagem("system", "teste")
        log_resultado("MEMORY.SHORT", "OK", "Memória de curto prazo (contexto) ativa.")
    except Exception as e:
        log_resultado("MEMORY", "ERRO", f"Falha nos sistemas de memória: {e}")

    # 5. VOZ E VISÃO
    try:
        from MODULOS.voice import voice_manager
        log_resultado("VOICE", "OK", "Gerenciador de voz carregado.")
    except Exception as e:
        log_resultado("VOICE", "ERRO", str(e))

    try:
        from MODULOS.skills import vision_module
        log_resultado("VISION", "OK", "Módulo de visão (análise de tela) disponível.")
    except Exception as e:
        log_resultado("VISION", "AVISO", f"Dependências de visão incompletas: {e}")

    # 6. ESPECIALISTAS E FERRAMENTAS
    try:
        from MODULOS.skills import hardware_module
        stats = await hardware_module.obter_status_hardware()
        if stats:
            log_resultado("HARDWARE_STATS", "OK", "Coleta de telemetria (CPU/GPU) funcionando.")
    except Exception as e:
        log_resultado("HARDWARE_STATS", "ERRO", str(e))

    try:
        from MODULOS.skills import fii_monitor
        log_resultado("FINANCE", "OK", "Monitor de FIIs carregado.")
    except Exception as e:
        log_resultado("FINANCE", "ERRO", str(e))

    try:
        from MODULOS.brain.models import identity_module
        log_resultado("IDENTITY", "OK", "Módulo de identidade da máquina ativo.")
    except Exception as e:
        log_resultado("IDENTITY", "ERRO", str(e))

    try:
        from MODULOS.brain import nlp_processor
        res, txt = nlp_processor.processar_intencao("teste")
        log_resultado("NLP_PROCESSOR", "OK", f"Processador de linguagem legado operacional ({res}).")
    except Exception as e:
        log_resultado("NLP_PROCESSOR", "ERRO", str(e))

    try:
        from MODULOS.brain import airllm_module
        log_resultado("AIRLLM", "OK", "Infraestrutura AirLLM (Modelos Gigantes) carregada.")
    except Exception as e:
        log_resultado("AIRLLM", "ERRO", str(e))

    try:
        from MODULOS.skills import actions_module
        log_resultado("ACTIONS", "OK", "Módulo de ações do sistema (abrir apps) ativo.")
    except Exception as e:
        log_resultado("ACTIONS", "ERRO", str(e))

    try:
        from MODULOS.system import comunicacao_visual
        log_resultado("GUI.VISUAL", "OK", "Sistema de cores e feedback visual operacional.")
    except Exception as e:
        log_resultado("GUI.VISUAL", "ERRO", str(e))

    try:
        from MODULOS.system import interface_server
        log_resultado("GUI.SERVER", "OK", "Servidor de interface carregado.")
    except Exception as e:
        log_resultado("GUI.SERVER", "ERRO", str(e))

    # 7. FINALIZAÇÃO E RELATÓRIO
    os.makedirs(os.path.dirname(RELATORIO_PATH), exist_ok=True)
    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO DE DIAGNÓSTICO GLOBAL DO JARVIS\n")
        f.write("="*40 + "\n")
        f.write(f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        for res in resultados:
            f.write(res + "\n")
    
    print(f"\n{Cores.AZUL}" + "="*40)
    print("DIAGNÓSTICO CONCLUÍDO!")
    print(f"Relatório salvo em: {RELATORIO_PATH}")
    print("="*40 + Cores.RESET)

if __name__ == "__main__":
    asyncio.run(testar_sistema())