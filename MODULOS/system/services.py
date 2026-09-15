import psutil
import subprocess
import time
import ollama
import httpx
from MODULOS.system.logger import log

def liberar_porta_8000():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.net_connections(kind='inet'):
                if conn.laddr.port == 8000:
                    log.info(f"Liberando porta 8000 (Encerrando processo antigo {proc.pid})...")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue

def iniciar_ollama_se_necessario() -> bool:
    try:
        ollama.ps()
        log.info("Ollama já está em execução.")
        return True
    except Exception:
        log.info("Ollama não detectado. Iniciando servidor...")
        try:
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            for i in range(10):
                time.sleep(1)
                try:
                    ollama.ps()
                    log.info(f"Servidor Ollama conectado e pronto.")
                    return True
                except:
                    continue
        except Exception as e:
            log.error(f"Falha ao iniciar Ollama: {e}")
            return False
    return False

async def reportar_progresso(progresso, mensagem, model_id=None, progresso_total=0, lista_modelos=None, ativo=True):
    try:
        payload = {
            "progresso": progresso,
            "mensagem": mensagem,
            "ativo": ativo,
            "progresso_total": progresso_total
        }
        if model_id: payload["model_id"] = model_id
        if lista_modelos: payload["lista_modelos"] = lista_modelos
        
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/system/download_progress", json=payload)
    except Exception as e:
        log.debug(f"Falha ao reportar progresso GUI: {e}")

async def reportar_sharding(progresso, mensagem, ativo=True):
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/system/sharding_progress", json={
                "progresso": progresso,
                "mensagem": mensagem,
                "ativo": ativo
            })
    except Exception as e:
        log.debug(f"Falha ao reportar sharding GUI: {e}")
