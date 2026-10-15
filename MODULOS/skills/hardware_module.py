import psutil
import aiohttp
import asyncio
import subprocess
import re

from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice import voice_manager

try:
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    import pynvml
    pynvml.nvmlInit()
    gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _NVIDIA_OK = True
except Exception:
    pynvml = None
    gpu_handle = None
    _NVIDIA_OK = False

def garantir_monitor_aberto():
    try:
        check = subprocess.check_output('tasklist', shell=True).decode('latin-1')
        if "LibreHardwareMonitor.exe" not in check:
            print("[SISTEMA] Iniciando Monitor de Hardware silenciosamente (Via Tarefa)...")
            subprocess.Popen('schtasks /run /tn "LibreHardwareMonitorTask"', shell=True)
        else:
            print("[HARDWARE_MODULE] Monitor já está em execução.")
    except Exception as e:
        print(f"[ERRO AO ABRIR MONITOR]: {e}")

async def _buscar_lhm() -> dict:
    """Busca o JSON completo do LibreHardwareMonitor. Retorna {} se indisponível."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8085/data.json", timeout=2) as r:
                if r.status == 200:
                    return await r.json()
    except Exception:
        pass
    return {}

async def ler_temperatura_cpu_lhm():
    palavras_cpu = ['Ryzen', 'Core', 'Intel', 'AMD', 'CPU']
    dados = await _buscar_lhm()
    try:
        for hardware in dados['Children'][0]['Children']:
            if any(p in hardware['Text'] for p in palavras_cpu):
                for sensor_group in hardware['Children']:
                    if sensor_group['Text'] == 'Temperatures':
                        for sensor in sensor_group['Children']:
                            if 'Core' in sensor['Text'] or 'Tctl' in sensor['Text'] or 'Package' in sensor['Text']:
                                val = sensor['Value'].replace(',', '.').replace(' °C', '')
                                return float(val)
    except Exception:
        pass
    return "N/A"

async def _ler_gpu_lhm() -> dict:
    """Lê dados da GPU via LHM — funciona com AMD e NVIDIA."""
    resultado = {"gpu_load": 0, "gpu_temp": "N/A", "vram_used_gb": "N/A", "gpu_power": "N/A"}
    if _NVIDIA_OK and gpu_handle:
        try:
            rates = pynvml.nvmlDeviceGetUtilizationRates(gpu_handle)
            resultado['gpu_load'] = round(float(rates.gpu), 1)
            resultado['gpu_temp'] = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            resultado['gpu_power'] = round(pynvml.nvmlDeviceGetPowerUsage(gpu_handle) / 1000.0, 1)
            meminfo = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
            resultado['vram_used_gb'] = round(meminfo.used / (1024 ** 3), 2)
            return resultado
        except Exception:
            pass

    dados = await _buscar_lhm()
    palavras_gpu = ['GPU', 'Radeon', 'GeForce', 'RX ', 'RTX', 'GTX']
    try:
        for hardware in dados.get('Children', [{}])[0].get('Children', []):
            if any(p in hardware['Text'] for p in palavras_gpu):
                for sensor_group in hardware.get('Children', []):
                    if sensor_group['Text'] == 'Temperatures':
                        for s in sensor_group.get('Children', []):
                            if 'GPU' in s['Text'] or 'Core' in s['Text']:
                                resultado['gpu_temp'] = float(s['Value'].replace(',', '.').replace(' °C', ''))
                    elif sensor_group['Text'] == 'Load':
                        for s in sensor_group.get('Children', []):
                            if 'GPU Core' in s['Text'] or s['Text'] == 'GPU Core':
                                val = s['Value'].replace(',', '.').replace(' %', '')
                                try:
                                    resultado['gpu_load'] = round(float(val), 1)
                                except Exception:
                                    pass
                    elif sensor_group['Text'] == 'Data':
                        for s in sensor_group.get('Children', []):
                            if 'Memory Used' in s['Text']:
                                val = s['Value'].replace(',', '.').replace(' MB', '').replace(' GB', '')
                                try:
                                    resultado['vram_used_gb'] = round(float(val) / 1024, 2) if 'MB' in s['Value'] else round(float(val), 2)
                                except Exception:
                                    pass
                    elif sensor_group['Text'] == 'Powers':
                        for s in sensor_group.get('Children', []):
                            if 'GPU' in s['Text']:
                                resultado['gpu_power'] = round(float(s['Value'].replace(',', '.').replace(' W', '')), 1)
    except Exception:
        pass
    return resultado

def listar_processos_vram() -> str:
    """Lista processos usando VRAM. NVIDIA via pynvml, AMD via psutil (aproximado)."""
    if _NVIDIA_OK:
        try:
            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(gpu_handle)
            procs += pynvml.nvmlDeviceGetGraphicsRunningProcesses(gpu_handle)
            if not procs:
                return "Nenhum processo usando VRAM no momento."
            linhas = []
            vistos = set()
            for p in procs:
                if p.pid in vistos:
                    continue
                vistos.add(p.pid)
                try:
                    nome = psutil.Process(p.pid).name()
                except Exception:
                    nome = f"PID {p.pid}"
                mb = round(p.usedGpuMemory / (1024 ** 2), 1) if p.usedGpuMemory else 0
                linhas.append(f"{nome}: {mb}MB")
            return ", ".join(linhas)
        except Exception as e:
            return f"Erro ao listar processos: {e}"
    else:
        try:
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if p.info['memory_info'].rss > 50 * 1024 * 1024:
                        procs.append((p.info['name'], round(p.info['memory_info'].rss / (1024**2), 1)))
                except Exception:
                    pass
            procs.sort(key=lambda x: x[1], reverse=True)
            top = procs[:5]
            return "(estimativa RAM) " + ", ".join(f"{n}: {m}MB" for n, m in top)
        except Exception:
            return "Não foi possível listar processos."

async def obter_status_hardware(foco=None):
    status = {}

    if _NVIDIA_OK and gpu_handle:
        try:
            status["gpu_temp"]     = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            status["gpu_power"]    = round(pynvml.nvmlDeviceGetPowerUsage(gpu_handle) / 1000.0, 1)
            meminfo                = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
            status["vram_used_gb"] = round(meminfo.used / (1024 ** 3), 2)
        except Exception:
            status["gpu_temp"] = status["gpu_power"] = status["vram_used_gb"] = "N/A"
    else:
        gpu_lhm = await _ler_gpu_lhm()
        status["gpu_temp"]     = gpu_lhm["gpu_temp"]
        status["gpu_power"]    = gpu_lhm["gpu_power"]
        status["vram_used_gb"] = gpu_lhm["vram_used_gb"]

    status["ram_used_percent"]  = psutil.virtual_memory().percent
    status["cpu_usage_percent"] = psutil.cpu_percent(interval=None)
    status["cpu_temp"]          = await ler_temperatura_cpu_lhm()

    if foco == "GPU":
        return f"A GPU está em {status['gpu_temp']} graus, consumindo {status['gpu_power']}W."
    elif foco == "CPU":
        return f"A CPU está com {status['cpu_usage_percent']}% de uso e {status['cpu_temp']} graus."
    elif foco == "VRAM":
        processos = listar_processos_vram()
        return f"VRAM em uso: {status['vram_used_gb']}GB. Processos: {processos}"
    elif foco == "RAM":
        return f"A RAM está com {status['ram_used_percent']}% de uso."

    return (
        f"Sensores: CPU {status['cpu_temp']}°C ({status['cpu_usage_percent']}%). "
        f"RAM {status['ram_used_percent']}%. "
        f"GPU {status['gpu_temp']}°C (VRAM: {status['vram_used_gb']}GB, Energia: {status['gpu_power']}W)."
    )

async def sentinela_hardware():
    while True:
        try:
            temps_alerta = []
            if _NVIDIA_OK and gpu_handle:
                try:
                    gpu_t = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                    if isinstance(gpu_t, (int, float)) and gpu_t > 85.0:
                        temps_alerta.append(("GPU", gpu_t))
                except Exception:
                    pass
            
            cpu_t = await ler_temperatura_cpu_lhm()
            if isinstance(cpu_t, (int, float)) and cpu_t > 85.0:
                temps_alerta.append(("CPU", cpu_t))

            if temps_alerta:
                comp, val = max(temps_alerta, key=lambda x: x[1])
                msg_alerta = f"ALERTA TÉRMICO: {comp} atingiu {val:.0f}°C!"
                await atualizar_jarvis(cor_hex="#ff0000", texto=msg_alerta, padrao="alerta")
                await voice_manager.falar("Sentinela", msg_alerta, prioridade=0)
                await asyncio.sleep(6)
                await atualizar_jarvis(cor_hex="#00ffff", texto="Sistemas normalizados", padrao="conversa")
        except asyncio.CancelledError:
            break
        except Exception as e:
            pass
        await asyncio.sleep(30)
