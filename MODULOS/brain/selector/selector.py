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

import os
from MODULOS.system.config import carregar_configuracao

def _modelo_airllm_existe(repo_id: str) -> bool:
    try:
        config = carregar_configuracao()
        hd_path = config.get("hd_path") if config else None
        ssd_path = config.get("ssd_path") if config else None
        
        caminhos_a_testar = []
        if hd_path:
            caminhos_a_testar.append(os.path.join(hd_path, repo_id.split('/')[-1]))
            caminhos_a_testar.append(os.path.join(hd_path, "hub", f"models--{repo_id.replace('/', '--')}"))
        
        hf_home = os.environ.get("HF_HOME")
        if hf_home:
            caminhos_a_testar.append(os.path.join(hf_home, "hub", f"models--{repo_id.replace('/', '--')}"))
            
        caminhos_a_testar.append(os.path.expanduser(f"~/.cache/huggingface/hub/models--{repo_id.replace('/', '--')}"))
        
        existe_base = any(os.path.exists(p) and (not os.path.isdir(p) or len(os.listdir(p)) > 0) for p in caminhos_a_testar)
        if not existe_base:
            return False
            
        if "Coder-32B" in repo_id:
            shards_path = os.path.join(ssd_path, "jarvis_shards_32b") if ssd_path else os.path.expanduser("~/.cache/huggingface/jarvis_shards_32b")
            if not os.path.exists(shards_path) or len(os.listdir(shards_path)) < 5:
                return False
                
        return True
    except Exception:
        return False

def escolher_melhor_modelo(especialidade: str) -> tuple[str, str]:
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            registry = json.load(f)
        esp = registry.get("especialistas", {}).get(especialidade, {})
        tipo = esp.get("tipo", "llm")
        if tipo == "airllm":
            repo_id = esp.get("repo_id", "Qwen/Qwen2.5-72B-Instruct")
            if _modelo_airllm_existe(repo_id):
                return repo_id, "airllm"
            
            # Fallback automático e transparente para modelo leve local
            log.warning("[SELETOR] Modelo pesado ausente. Usando modelo leve local como fallback.")
            perfil = registry.get("_perfil_detectado", "CPU_ONLY")
            modelos_perfil = PERFIS.get(perfil, {}).get("modelos", {})
            
            if especialidade == "CODIGO":
                return "qwen2.5-coder:1.5b", "llm"
            else:
                modelo_conversa = modelos_perfil.get("CONVERSA", ["llama3.2:3b"])[0]
                return modelo_conversa, "llm"
        else:
            return esp.get("modelo_ollama", "llama3.2:3b"), "llm"
    except Exception as e:
        log.warning(f"[SELETOR] Erro ao selecionar modelo: {e}. Usando fallback.")
        if especialidade == "CODIGO":
            return "qwen2.5-coder:1.5b", "llm"
        return "llama3.2:3b", "llm"
