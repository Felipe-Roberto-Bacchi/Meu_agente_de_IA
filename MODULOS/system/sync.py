import os
import asyncio
from MODULOS.system.logger import log
from MODULOS.system.services import reportar_progresso, reportar_sharding
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.brain import airllm_module

async def gerenciar_downloads_iniciais(config, incluir_pesados: bool = False):
    from huggingface_hub import snapshot_download
    import ollama
    
    hw = brain_selector.detectar_hardware()
    perfil_nome = brain_selector._escolher_perfil(hw)
    modelos_perfil = brain_selector.PERFIS[perfil_nome]["modelos"]
    
    nomes_ollama = set()
    nomes_airllm = []
    for lista in modelos_perfil.values():
        for m in lista:
            if m.endswith("-air"):
                rid = m.replace("-air", "")
                if rid not in [x['id'] for x in nomes_airllm]:
                    nomes_airllm.append({"id": rid, "nome": rid.split('/')[-1]})
            else:
                nomes_ollama.add(m)
    
    if not incluir_pesados:
        nomes_airllm = []
        
    todos_ids = list(nomes_ollama) + [x['id'] for x in nomes_airllm]
    if not todos_ids:
        await reportar_progresso(100, "Nenhum modelo para baixar.", ativo=False)
        return True

    await reportar_progresso(0, "Iniciando Sincronização...", lista_modelos=todos_ids)

    total_etapas = len(todos_ids)
    etapa_atual = 0

    modelos_locais = []
    try:
        lista = ollama.list()
        models = lista.get('models', []) if isinstance(lista, dict) else getattr(lista, 'models', [])
        for m in models:
            if isinstance(m, dict):
                modelos_locais.append(m.get('name', ''))
            else:
                modelos_locais.append(getattr(m, 'model', getattr(m, 'name', '')))
    except Exception as e: 
        log.warning(f"Erro ao listar Ollama locais: {e}")

    for model_id in nomes_ollama:
        etapa_atual += 1
        prog_total = int((etapa_atual / total_etapas) * 100)
        
        if any(model_id in m for m in modelos_locais):
            await reportar_progresso(100, f"Já instalado: {model_id}", model_id=model_id, progresso_total=prog_total)
            continue

        await reportar_progresso(10, f"Puxando {model_id}...", model_id=model_id, progresso_total=prog_total)
        try:
            ollama.pull(model_id)
            await reportar_progresso(100, f"Concluído: {model_id}", model_id=model_id, progresso_total=prog_total)
        except Exception as e: 
            log.error(f"Erro no pull do {model_id}: {e}")

    if incluir_pesados and nomes_airllm:
        hd_path = config.get("hd_path", "D:\\ModelosIA")
        ssd_path = config.get("ssd_path", os.path.expanduser("~/.cache/huggingface"))

        for model in nomes_airllm:
            etapa_atual += 1
            prog_total = int((etapa_atual / total_etapas) * 100)
            repo_id = model['id']
            
            target_dir = os.path.join(hd_path, repo_id.split('/')[-1])
            path_cache = os.path.join(hd_path, "hub", f"models--{repo_id.replace('/', '--')}")
            
            modelo_base_existe = os.path.exists(path_cache) or (os.path.exists(target_dir) and len(os.listdir(target_dir)) > 5)
            
            if not modelo_base_existe:
                await reportar_progresso(20, f"Baixando {repo_id}...", model_id=repo_id, progresso_total=prog_total)
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    await asyncio.to_thread(snapshot_download, repo_id=repo_id, local_dir=target_dir, local_dir_use_symlinks=False)
                except Exception as e:
                    log.error(f"DOWNLOAD ERROR {repo_id}: {e}")
                    await reportar_progresso(0, f"Erro no download: {model['nome']}", model_id=repo_id, progresso_total=prog_total)
                    continue 

            shards_path = os.path.join(ssd_path, "jarvis_shards_32b")
            precisa_sharding = False
            if "Coder-32B" in repo_id:
                if not os.path.exists(shards_path) or len(os.listdir(shards_path)) < 5:
                    precisa_sharding = True
            
            if precisa_sharding:
                await reportar_progresso(50, f"Fatiando camadas (sharding): {model['nome']}...", model_id=repo_id, progresso_total=prog_total)
                await reportar_sharding(10, f"Lendo shards: {model['nome']}")
                await asyncio.to_thread(airllm_module._inicializar_airllm, repo_id)
                await reportar_sharding(100, f"Fatiamento concluído: {model['nome']}", ativo=False)
            
            await reportar_progresso(100, f"Concluído: {model['nome']}", model_id=repo_id, progresso_total=prog_total)
                
    await reportar_progresso(100, "Sincronização Finalizada!", ativo=False)
    return True


async def baixar_modelos_pesados_airllm(config):
    """Baixa e faz sharding exclusivamente dos modelos AirLLM (-air)."""
    from huggingface_hub import snapshot_download
    
    hw = brain_selector.detectar_hardware()
    perfil_nome = brain_selector._escolher_perfil(hw)
    modelos_perfil = brain_selector.PERFIS[perfil_nome]["modelos"]
    
    nomes_airllm = []
    for lista in modelos_perfil.values():
        for m in lista:
            if m.endswith("-air"):
                rid = m.replace("-air", "")
                if rid not in [x['id'] for x in nomes_airllm]:
                    nomes_airllm.append({"id": rid, "nome": rid.split('/')[-1]})
    
    if not nomes_airllm:
        await reportar_progresso(100, "Nenhum modelo pesado configurado no perfil atual.", ativo=False)
        return True

    todos_ids = [x['id'] for x in nomes_airllm]
    await reportar_progresso(0, "Iniciando Download dos Modelos Pesados...", lista_modelos=todos_ids)

    total_etapas = len(nomes_airllm)
    etapa_atual = 0

    hd_path = config.get("hd_path", "D:\\ModelosIA")
    ssd_path = config.get("ssd_path", os.path.expanduser("~/.cache/huggingface"))

    for model in nomes_airllm:
        etapa_atual += 1
        prog_total = int((etapa_atual / total_etapas) * 100)
        repo_id = model['id']
        
        target_dir = os.path.join(hd_path, repo_id.split('/')[-1])
        path_cache = os.path.join(hd_path, "hub", f"models--{repo_id.replace('/', '--')}")
        
        modelo_base_existe = os.path.exists(path_cache) or (os.path.exists(target_dir) and len(os.listdir(target_dir)) > 5)
        
        if not modelo_base_existe:
            await reportar_progresso(20, f"Baixando {repo_id} no HD...", model_id=repo_id, progresso_total=prog_total)
            try:
                os.makedirs(target_dir, exist_ok=True)
                await asyncio.to_thread(snapshot_download, repo_id=repo_id, local_dir=target_dir, local_dir_use_symlinks=False)
            except Exception as e:
                log.error(f"DOWNLOAD ERROR {repo_id}: {e}")
                await reportar_progresso(0, f"Erro no download: {model['nome']}", model_id=repo_id, progresso_total=prog_total)
                continue 

        shards_path = os.path.join(ssd_path, "jarvis_shards_32b")
        precisa_sharding = False
        if "Coder-32B" in repo_id:
            if not os.path.exists(shards_path) or len(os.listdir(shards_path)) < 5:
                precisa_sharding = True
        
        if precisa_sharding:
            await reportar_progresso(50, f"Fatiando camadas (sharding): {model['nome']}...", model_id=repo_id, progresso_total=prog_total)
            await reportar_sharding(10, f"Lendo shards: {model['nome']}")
            await asyncio.to_thread(airllm_module._inicializar_airllm, repo_id)
            await reportar_sharding(100, f"Fatiamento concluído: {model['nome']}", ativo=False)
        
        await reportar_progresso(100, f"Concluído: {model['nome']}", model_id=repo_id, progresso_total=prog_total)
            
    await reportar_progresso(100, "Download e Sharding de Modelos Pesados Concluídos!", ativo=False)
    return True
