"""
diagnostics_module.py
─────────────────────
Módulo de Diagnóstico Completo em Tempo Real dos Subsistemas Neurais do Jarvis.
Executa checkups profundos em cada subsistema e emite telemetria WebSocket
para renderização de HUD holográfico Glassmorphism estilo Mark VII.
"""

import os
import time
import socket
import asyncio
import psutil

from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import enviar_evento_interface, atualizar_jarvis
from MODULOS.voice import voice_manager

DIAGNOSTICO_EM_ANDAMENTO = False
ULTIMO_DIAGNOSTICO = {}

SUBSISTEMAS_METADATA = [
    {"id": "ollama", "nome": "1. Núcleo Neural & Roteador (Ollama)", "icone": "🧠"},
    {"id": "vision", "nome": "2. Módulo de Visão (Moondream)", "icone": "👁️"},
    {"id": "memory", "nome": "3. Memória Semântica (ChromaDB)", "icone": "📚"},
    {"id": "voice", "nome": "4. Sintetizador & Audição (Edge-TTS / Whisper)", "icone": "🎙️"},
    {"id": "calendar", "nome": "5. Google Calendar API (OAuth2)", "icone": "📅"},
    {"id": "drive", "nome": "6. Google Drive API (Workspace)", "icone": "📁"},
    {"id": "media", "nome": "7. Rede & Media Hub (YouTube / Locais)", "icone": "🎵"},
    {"id": "hardware", "nome": "8. Sentinela de Hardware (GTX 1650 / CPU)", "icone": "🛡️"}
]

async def _testar_ollama() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        import ollama
        loop = asyncio.get_running_loop()
        models_data = await loop.run_in_executor(None, ollama.list)
        ms = max(1, int((time.time() - t0) * 1000))
        names = []
        if hasattr(models_data, 'models'):
            names = [m.model for m in models_data.models]
        elif isinstance(models_data, dict) and 'models' in models_data:
            names = [m.get('name', '') for m in models_data['models']]
        
        tem_llama = any("llama3.2" in n for n in names)
        tem_qwen = any("qwen" in n for n in names)
        
        if tem_llama and tem_qwen:
            return "ok", f"Ollama Online • Llama 3.2 e Qwen ativos ({len(names)} modelos)", ms
        return "ok", f"Ollama Online • {len(names)} modelos carregados", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "error", f"Servidor Ollama inativo ou porta 11434 ocupada: {str(e)[:40]}", ms

async def _testar_visao() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        import ollama
        loop = asyncio.get_running_loop()
        models_data = await loop.run_in_executor(None, ollama.list)
        names = [m.model for m in models_data.models] if hasattr(models_data, 'models') else []
        tem_moondream = any("moondream" in n for n in names)
        
        # Teste de captura de tela
        captura_ok = False
        try:
            from PIL import ImageGrab
            test_img = ImageGrab.grab(bbox=(0, 0, 10, 10))
            if test_img:
                captura_ok = True
        except Exception:
            try:
                import pyautogui
                if pyautogui.size():
                    captura_ok = True
            except Exception:
                pass

        ms = max(1, int((time.time() - t0) * 1000))
        if tem_moondream and captura_ok:
            return "ok", "Moondream pronto • Captura de tela ativa", ms
        elif captura_ok:
            return "warn", "Captura ativa • Modelo moondream pendente de download", ms
        elif tem_moondream:
            return "warn", "Moondream disponível • Permissão de captura restrita", ms
        return "warn", "Módulo de visão em modo simulado", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Visão em standby: {str(e)[:40]}", ms

async def _testar_memoria() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        from MODULOS.memory import memory_long
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, memory_long.inicializar_banco)
        ms = max(1, int((time.time() - t0) * 1000))
        
        total_fatos = 0
        total_historico = 0
        try:
            if memory_long._col_fatos:
                total_fatos = memory_long._col_fatos.count()
            if memory_long._col_historico:
                total_historico = memory_long._col_historico.count()
        except Exception:
            pass

        return "ok", f"ChromaDB Conectado • {total_fatos} fatos / {total_historico} memórias", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"ChromaDB em modo arquivo local: {str(e)[:40]}", ms

async def _testar_voz() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        cfg = voice_manager.carregar_config_voz()
        voz_nome = cfg.get("nome", "Neural: Antonio")
        # Checa microfone
        mic_status = "Microfone Ativo"
        try:
            from MODULOS import ear
            if hasattr(ear, "MIC_MUTADO") and ear.MIC_MUTADO:
                mic_status = "Microfone Mutado"
        except Exception:
            pass

        ms = max(1, int((time.time() - t0) * 1000))
        return "ok", f"{mic_status} • {voz_nome}", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Sintetizador com fallback local: {str(e)[:40]}", ms

async def _testar_google_calendar() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        from MODULOS.skills import google_mcp_module
        st = google_mcp_module.obter_status_google_auth()
        ms = max(1, int((time.time() - t0) * 1000))
        if st.get("autenticado"):
            loop = asyncio.get_running_loop()
            evs = await loop.run_in_executor(None, lambda: google_mcp_module.listar_eventos_google_calendar(max_results=1))
            return "ok", f"Google Calendar Conectado • {len(evs)} compromisso(s) próximo(s)", ms
        elif st.get("configurado"):
            return "warn", "Credenciais encontradas • Aguardando autorização no navegador", ms
        return "warn", "Google Calendar não conectado (Configure no Menu Sistema)", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Google Calendar Offline: {str(e)[:40]}", ms

async def _testar_google_drive() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        from MODULOS.skills import google_mcp_module
        st = google_mcp_module.obter_status_google_auth()
        ms = max(1, int((time.time() - t0) * 1000))
        if st.get("autenticado"):
            loop = asyncio.get_running_loop()
            arqs = await loop.run_in_executor(None, lambda: google_mcp_module.buscar_arquivos_google_drive(termo="", max_results=3))
            return "ok", f"Google Drive Conectado • Acesso a {len(arqs)}+ arquivos recentes", ms
        elif st.get("configurado"):
            return "warn", "Credenciais encontradas • Aguardando autorização no navegador", ms
        return "warn", "Google Drive não conectado (Configure no Menu Sistema)", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Google Drive Offline: {str(e)[:40]}", ms

async def _testar_media_hub() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        loop = asyncio.get_running_loop()
        def _check_net():
            sock = socket.create_connection(('1.1.1.1', 53), timeout=2)
            sock.close()
        await loop.run_in_executor(None, _check_net)
        
        from MODULOS.skills import music_module
        locais = await loop.run_in_executor(None, music_module.escanear_arquivos_locais)
        ms = max(1, int((time.time() - t0) * 1000))
        return "ok", f"Conexão de Rede Estável • {len(locais)} Músicas Locais (.opus/.flac/.mp3)", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Rede limitada: {str(e)[:40]}", ms

async def _testar_hardware() -> tuple[str, str, int]:
    t0 = time.time()
    try:
        gpu_info = "GPU N/A"
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            nome_gpu = pynvml.nvmlDeviceGetName(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            gpu_info = f"{nome_gpu} {temp}°C ({mem.used // (1024**2)}MB VRAM)"
        except Exception:
            pass

        cpu_p = psutil.cpu_percent(interval=0.1)
        ram_p = psutil.virtual_memory().percent
        ms = max(1, int((time.time() - t0) * 1000))
        return "ok", f"CPU {cpu_p}% | RAM {ram_p}% | {gpu_info}", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return "warn", f"Telemetria básica: {str(e)[:40]}", ms

TEST_RUNNERS = {
    "ollama": _testar_ollama,
    "vision": _testar_visao,
    "memory": _testar_memoria,
    "voice": _testar_voz,
    "calendar": _testar_google_calendar,
    "drive": _testar_google_drive,
    "media": _testar_media_hub,
    "hardware": _testar_hardware
}

async def executar_diagnostico_coreografado():
    """
    Executa o diagnóstico completo dos 8 subsistemas com sincronização em tempo real
    para o HUD holográfico Glassmorphism e síntese de voz executiva do Jarvis.
    """
    global DIAGNOSTICO_EM_ANDAMENTO, ULTIMO_DIAGNOSTICO
    if DIAGNOSTICO_EM_ANDAMENTO:
        log.info("[DIAGNOSTICO] Diagnóstico já em andamento.")
        return

    DIAGNOSTICO_EM_ANDAMENTO = True
    log.info("[DIAGNOSTICO] Iniciando checkup geral dos 8 subsistemas neurais...")

    try:
        # 1. Abre a interface holográfica no centro e minimiza o Core para o canto
        await enviar_evento_interface({
            "type": "diag_start",
            "total": len(SUBSISTEMAS_METADATA),
            "subsistemas": SUBSISTEMAS_METADATA
        })

        fala_intro = "Iniciando diagnóstico completo dos subsistemas neurais. Por favor, acompanhe o status na interface holográfica, senhor."
        await atualizar_jarvis(cor_hex="#00ffff", texto=fala_intro, padrao="tarefa")
        asyncio.create_task(voice_manager.falar("Jarvis", fala_intro, prioridade=1))

        resultados = []
        ok_count = 0
        warn_count = 0
        error_count = 0

        # 2. Executa cada teste sequencialmente com feedback ao vivo
        for sub in SUBSISTEMAS_METADATA:
            if voice_manager.ABORTAR_FALA:
                log.info("[DIAGNOSTICO] Abortado pelo usuário.")
                break

            sub_id = sub["id"]
            nome = sub["nome"]

            # Emite estado "testing" (scanner animado)
            await enviar_evento_interface({
                "type": "diag_step",
                "id": sub_id,
                "nome": nome,
                "status": "testing",
                "detalhe": "Executando varredura e checagem de latência...",
                "latencia_ms": 0
            })

            # Executa o teste real
            runner = TEST_RUNNERS.get(sub_id)
            if runner:
                status, detalhe, latencia = await runner()
            else:
                status, detalhe, latencia = "warn", "Teste não implementado", 0

            if status == "ok":
                ok_count += 1
            elif status == "warn":
                warn_count += 1
            else:
                error_count += 1

            resultados.append({
                "id": sub_id,
                "nome": nome,
                "status": status,
                "detalhe": detalhe,
                "latencia_ms": latencia
            })

            # Atualiza a linha com o resultado final do subsistema
            await enviar_evento_interface({
                "type": "diag_step",
                "id": sub_id,
                "nome": nome,
                "status": status,
                "detalhe": detalhe,
                "latencia_ms": latencia
            })

            # Pausa rítmica estética de 350ms para desfile Sci-Fi
            await asyncio.sleep(0.35)

        total = len(SUBSISTEMAS_METADATA)
        pct = int((ok_count / total) * 100) if total else 0
        resumo_str = f"{ok_count}/{total} SISTEMAS OPERACIONAIS - {pct}% ONLINE"

        ULTIMO_DIAGNOSTICO = {
            "timestamp": time.strftime("%d/%m/%Y %H:%M:%S"),
            "total": total,
            "ok": ok_count,
            "warn": warn_count,
            "error": error_count,
            "pct": pct,
            "resultados": resultados
        }

        # 3. Notifica a conclusão para a HUD
        await enviar_evento_interface({
            "type": "diag_end",
            "total": total,
            "ok": ok_count,
            "warn": warn_count,
            "error": error_count,
            "pct": pct,
            "resumo": resumo_str
        })

        # 4. Síntese de voz executiva do Jarvis
        if error_count == 0 and warn_count == 0:
            fala_final = "Diagnóstico concluído com sucesso, senhor. Todos os oito subsistemas estão 100% online e operando em capacidade nominal."
            cor_final = "#00ff88"
        elif error_count > 0:
            fala_final = f"Diagnóstico finalizado, senhor. Identifiquei {ok_count} sistemas operacionais, porém detectei {error_count} falha crítica que requer atenção imediata."
            cor_final = "#ff0055"
        else:
            fala_final = f"Diagnóstico concluído, senhor. {ok_count} sistemas estão plenamente operacionais e {warn_count} módulos requerem pequenos ajustes ou login."
            cor_final = "#ffaa00"

        await atualizar_jarvis(cor_hex=cor_final, texto=fala_final, padrao="conversa")
        await voice_manager.falar("Jarvis", fala_final, prioridade=1)

    except Exception as e:
        log.error(f"[DIAGNOSTICO] Falha durante execução: {e}")
        await enviar_evento_interface({
            "type": "diag_end",
            "total": 8,
            "ok": 0,
            "error": 8,
            "resumo": "FALHA NO DIAGNÓSTICO GERAL"
        })
    finally:
        DIAGNOSTICO_EM_ANDAMENTO = False
