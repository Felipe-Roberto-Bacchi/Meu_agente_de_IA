import platform
import psutil
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pynvml
except ImportError:
    pynvml = None
import json
import os
import subprocess

IDENTITY_FILE = "DADOS/jarvis_identity.json"

def capturar_cpu_autonomo():
    """Tenta 3 métodos diferentes para pegar o nome real da CPU sem intervenção humana."""
    # Método 1: Registro do Windows (Geralmente o mais preciso)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Hardware\Description\System\CentralProcessor\0")
        nome, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        winreg.CloseKey(key)
        return nome.strip()
    except:
        pass

    # Método 2: WMI (Fallback para o sistema)
    try:
        comando = "wmic cpu get name"
        saida = subprocess.check_output(comando, shell=True).decode().strip().split('\n')
        if len(saida) > 1:
            return saida[1].strip()
    except:
        pass

    # Método 3: Platform (O que estava vindo genérico)
    return platform.processor()

def mapear_sistema_completo():
    print("[AUTO-DETECÇÃO] Analisando hardware desconhecido...")
    
    # Detecção dinâmica de OS
    versao_os = f"{platform.system()} {platform.release()}"
    if platform.system() == "Windows" and platform.release() == "10":
        # Ajuste para detectar Windows 11 que se reporta como 10
        import sys
        if sys.getwindowsversion().build >= 22000:
            versao_os = "Windows 11"

    # Detecção dinâmica de CPU
    cpu_real = capturar_cpu_autonomo()
    
    # Detecção dinâmica de GPU
    gpu_nome = "GPU Genérica / Integrada"
    vram_total = 0.0
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_nome = pynvml.nvmlDeviceGetName(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total = round(mem_info.total / (1024**3), 2)
    except:
        # Se não houver NVIDIA, tentamos listar via WMIC
        try:
            cmd_gpu = "wmic path win32_VideoController get name"
            gpu_nome = subprocess.check_output(cmd_gpu, shell=True).decode().strip().split('\n')[1].strip()
        except:
            pass

    identidade = {
        "cpu_modelo": cpu_real,
        "cpu_cores": f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count(logical=True)} threads",
        "gpu_modelo": gpu_nome,
        "vram_total_gb": vram_total,
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "os_versao": versao_os,
        "mapeado_em": platform.node()
    }

    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identidade, f, indent=4, ensure_ascii=False)
    
    print(f"[SISTEMA] Identidade Gerada: {identidade['cpu_modelo']} no {identidade['os_versao']}")
    return identidade

def carregar_identidade():
    if os.path.exists(IDENTITY_FILE):
        with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return mapear_sistema_completo()
