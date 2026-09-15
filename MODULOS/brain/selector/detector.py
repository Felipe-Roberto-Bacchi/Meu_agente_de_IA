import json
import os

def _ler_identidade() -> dict:
    path = "DADOS/jarvis_identity.json"
    if not os.path.exists(path):
        path = os.path.join("teste", "jarvis_identity.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _detectar_vram_psutil() -> float:
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(info.total / (1024 ** 3), 2)
    except Exception:
        return 0.0

def detectar_hardware() -> dict:
    identidade = _ler_identidade()

    vram_gb = identidade.get("vram_total_gb", 0.0)
    if vram_gb == 0.0:
        vram_gb = _detectar_vram_psutil()

    ram_gb = identidade.get("ram_total_gb", 0.0)
    if ram_gb == 0.0:
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            ram_gb = 8.0 

    cores_str = identidade.get("cpu_cores", "")
    try:
        cpu_cores = int(cores_str.split("cores")[0].strip())
    except Exception:
        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=False) or 4
        except Exception:
            cpu_cores = 4

    return {
        "vram_gb":    vram_gb,
        "ram_gb":     ram_gb,
        "cpu_cores":  cpu_cores,
        "cpu_modelo": identidade.get("cpu_modelo", "Desconhecido"),
        "gpu_modelo": identidade.get("gpu_modelo", "Desconhecido"),
    }
