import os
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.system.logger import log

async def verificar_modelos_faltantes(config):
    hw = brain_selector.detectar_hardware()
    perfil_nome = brain_selector._escolher_perfil(hw)
    modelos_perfil = brain_selector.PERFIS[perfil_nome]["modelos"]
    
    try:
        lista = ollama.list()
        # Suporta tanto o formato antigo (dict) quanto o novo (ModelsList object)
        models = lista.get('models', []) if isinstance(lista, dict) else getattr(lista, 'models', [])
        modelos_locais = []
        for m in models:
            if isinstance(m, dict):
                modelos_locais.append(m.get('name', ''))
            else:
                # No objeto Model, pode ser .model ou .name
                modelos_locais.append(getattr(m, 'model', getattr(m, 'name', '')))
    except Exception as e:
        log.warning(f"Falha de conexão com o Ollama na integridade: {e}")
        return True 

    for lista_m in modelos_perfil.values():
        for m in lista_m:
            if m.endswith("-air"):
                repo_id = m.replace("-air", "")
                target_dir = os.path.join(config['hd_path'], repo_id.split('/')[-1])
                path_cache = os.path.join(config['hd_path'], "hub", f"models--{repo_id.replace('/', '--')}")
                
                shards_path = r"C:\Users\felip\.cache\huggingface\jarvis_shards_32b"
                
                if not (os.path.exists(path_cache) or (os.path.exists(target_dir) and len(os.listdir(target_dir)) > 5)):
                    log.error(f"[INTEGRIDADE] Modelo base AirLLM faltando no HD: {repo_id}")
                    return True
                
                if "Coder-32B" in repo_id:
                    if not os.path.exists(shards_path) or len(os.listdir(shards_path)) < 5:
                        log.error(f"[INTEGRIDADE] Fatias (shards) do 32B faltando no SSD.")
                        return True
            else:
                if not any(m in loc for loc in modelos_locais):
                    log.error(f"[INTEGRIDADE] Modelo Ollama faltando: {m}")
                    return True
    return False
