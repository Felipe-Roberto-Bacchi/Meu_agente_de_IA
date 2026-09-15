import json
from MODULOS.system.logger import log
from MODULOS.brain.models.profiles import PERFIS, _DESCRICOES
from MODULOS.brain.selector.detector import detectar_hardware

REGISTRY_FILE = "DADOS/model_registry.json"

def _escolher_perfil(hw: dict) -> str:
    vram = hw["vram_gb"]
    if vram >= 24: return "MONSTER"
    if vram >= 12: return "ULTRA"
    if vram >= 8:  return "HIGH"
    if vram >= 6:  return "MEDIUM"
    if vram >= 4:  return "LOW"
    return "CPU_ONLY"

def atualizar_registry(hw: dict, perfil: str) -> dict:
    modelos = PERFIS[perfil]["modelos"]
    especialistas = {
        "HARDWARE": {
            "tipo": "funcao_local",
            "modulo": "hardware_module",
            "descricao": _DESCRICOES["HARDWARE"],
        },
        "ABRIR_APP": {
            "tipo": "funcao_local",
            "modulo": "actions_module",
            "descricao": _DESCRICOES["ABRIR_APP"],
        },
    }

    for especialidade, desc in _DESCRICOES.items():
        if especialidade in ("HARDWARE", "ABRIR_APP"):
            continue
            
        lista_modelos = modelos.get(especialidade, modelos["CONVERSA"])
        modelo = lista_modelos[0]
        
        if modelo.endswith("-air"):
            repo_id = modelo.replace("-air", "")
            especialistas[especialidade] = {
                "tipo": "airllm",
                "repo_id": repo_id,
                "descricao": desc,
            }
        else:
            especialistas[especialidade] = {
                "tipo": "llm",
                "modelo_ollama": modelo,
                "descricao": desc,
            }

    registry = {
        "_perfil_detectado": perfil,
        "_hardware_detectado": hw,
        "_descricao_perfil": PERFIS[perfil]["descricao"],
        "modelo_roteador": modelos["ROTEADOR"][0],
        "especialistas": specialists if 'specialists' in locals() else especialistas,
    }

    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    return registry

def calibrar_e_salvar() -> dict:
    hw     = detectar_hardware()
    perfil = _escolher_perfil(hw)
    log.info(f"Seletor: VRAM={hw['vram_gb']}GB | Perfil={perfil}")
    registry = atualizar_registry(hw, perfil)
    return registry

def escolher_melhor_modelo(especialidade: str) -> tuple[str, str]:
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            registry = json.load(f)
        esp = registry.get("especialistas", {}).get(especialidade, {})
        tipo = esp.get("tipo", "llm")
        if tipo == "airllm":
            return esp.get("repo_id", "Qwen/Qwen2.5-72B-Instruct"), "airllm"
        else:
            return esp.get("modelo_ollama", "llama3.2:3b"), "llm"
    except Exception:
        return "llama3.2:3b", "llm"
