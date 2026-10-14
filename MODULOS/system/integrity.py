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
                continue  # Modelos pesados AirLLM são opcionais e não bloqueiam o boot
            else:
                if not any(m in loc for loc in modelos_locais):
                    log.error(f"[INTEGRIDADE] Modelo Ollama faltando: {m}")
                    return True
    return False
