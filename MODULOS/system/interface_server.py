try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import json
    import asyncio
    import os
    import sys
    import traceback
    import psutil
    
    # Adicionado para suportar caso cliquem/abram diretamente o arquivo invés do módulo
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    # Importa o seletor para pegar os modelos propostos
    from MODULOS.brain.selector import selector as brain_selector

    app = FastAPI()

    # Serve arquivos estáticos da pasta INTERFACE
    interface_dir = os.path.join(ROOT_DIR, "INTERFACE")
    if os.path.exists(interface_dir):
        app.mount("/INTERFACE", StaticFiles(directory=interface_dir), name="INTERFACE")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ConnectionManager:
        def __init__(self):
            self.active_connections: list[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        async def broadcast(self, message: dict):
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass

    manager = ConnectionManager()
    download_status = {"ativo": False, "progresso": 0, "mensagem": "", "modelos": {}, "progresso_total": 0}
    sharding_status = {"ativo": False, "progresso": 0, "mensagem": ""}
    hardware_status = {}
    
    FLAG_MIC_MUTED = os.path.join(ROOT_DIR, "DADOS", "mic_muted.flag")
    mic_muted = False

    async def broadcast_hardware_status():
        from MODULOS.skills import hardware_module
        while True:
            try:
                # Obtém o dict bruto de sensores
                hw_info = {
                    "cpu_usage": psutil.cpu_percent(),
                    "ram_usage": psutil.virtual_memory().percent,
                    "cpu_temp": await hardware_module.ler_temperatura_cpu_lhm(),
                    "gpu_load": 0,
                    "gpu_temp": "N/A",
                    "vram_used_gb": "N/A",
                    "gpu_power": "N/A",
                }
                # Tenta pegar dados da GPU (pode falhar se hardware_module não estiver pronto ou sem GPU)
                try:
                    gpu_data = await hardware_module._ler_gpu_lhm()
                    hw_info.update(gpu_data)
                except Exception:
                    pass
                
                await manager.broadcast({"type": "hardware_update", "hardware": hw_info})
            except Exception:
                pass
            await asyncio.sleep(2)

    @app.on_event("startup")
    async def startup_event():
        global mic_muted
        if os.path.exists(FLAG_MIC_MUTED):
            try:
                os.remove(FLAG_MIC_MUTED)
            except Exception:
                pass
        mic_muted = False
        asyncio.create_task(broadcast_hardware_status())

    @app.get("/")
    async def get():
        index_path = os.path.join(ROOT_DIR, "INTERFACE", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/html")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.get("/system/pick_folder")
    async def pick_folder():
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory()
        root.destroy()
        
        # Sincroniza com o que o index.html espera (data.path)
        print(f"[DEBUG] Pasta selecionada: {folder}")
        return {"path": folder}

    @app.get("/system/proposed_models")
    async def proposed_models():
        hw = brain_selector.detectar_hardware()
        perfil_id = brain_selector._escolher_perfil(hw)
        perfil = brain_selector.PERFIS[perfil_id]
        return {
            "perfil": perfil_id,
            "descricao": perfil["descricao"],
            "modelos": perfil["modelos"]
        }

    @app.post("/system/setup")
    async def setup(data: dict):
        print(f"[DEBUG] Recebendo configuração: {data}")
        # data deve conter ssd_path e hd_path
        with open("DADOS/config_paths.json", "w") as f:
            json.dump(data, f)
        return {"status": "success"}

    @app.get("/system/status")
    async def get_status():
        configurado = os.path.exists("DADOS/config_paths.json")
        return {
            "download": download_status,
            "sharding": sharding_status,
            "configurado": configurado
        }

    @app.post("/system/download_heavy")
    async def download_heavy():
        from MODULOS.system.config import carregar_configuracao
        from MODULOS.system.sync import baixar_modelos_pesados_airllm
        config = carregar_configuracao()
        if not config:
            return {"status": "erro", "mensagem": "Sistema ainda não configurado (caminhos ausentes)."}
        if download_status.get("ativo", False) or sharding_status.get("ativo", False):
            return {"status": "ocupado", "mensagem": "Download ou sharding já em andamento."}
        asyncio.create_task(baixar_modelos_pesados_airllm(config))
        return {"status": "iniciado", "mensagem": "Download dos modelos pesados (AirLLM) iniciado em segundo plano."}

    @app.post("/system/download_progress")
    async def update_download(data: dict):
        global download_status
        download_status["ativo"] = data.get("ativo", True)
        
        if "lista_modelos" in data:
            download_status["modelos"] = {m: 0 for m in data["lista_modelos"]}
        
        if "model_id" in data:
            mid = data["model_id"]
            if mid not in download_status["modelos"]:
                download_status["modelos"][mid] = 0
            download_status["modelos"][mid] = data.get("progresso", 0)
            
        download_status["progresso_total"] = data.get("progresso_total", 0)
        download_status["mensagem"] = data.get("mensagem", "")
        
        await manager.broadcast({"type": "download_update", "download": download_status})
        return {"status": "ok"}

    @app.post("/system/sharding_progress")
    async def update_sharding(data: dict):
        global sharding_status
        sharding_status["ativo"] = data.get("ativo", True)
        sharding_status["progresso"] = data.get("progresso", 0)
        sharding_status["mensagem"] = data.get("mensagem", "")
        
        await manager.broadcast({"type": "sharding_update", "sharding": sharding_status})
        return {"status": "ok"}

    @app.post("/update")
    async def update_interface(data: dict):
        # Transmite os dados recebidos (cor, texto, intensidade, padrao) para todos os clientes via WebSocket
        await manager.broadcast(data)
        return {"status": "ok"}

    @app.post("/api/mic/toggle_mute")
    async def toggle_mute():
        global mic_muted
        os.makedirs(os.path.join(ROOT_DIR, "DADOS"), exist_ok=True)
        ja_mutado = os.path.exists(FLAG_MIC_MUTED) or os.path.exists("DADOS/mic_muted.flag")
        mic_muted = not ja_mutado
        
        if mic_muted:
            with open(FLAG_MIC_MUTED, "w", encoding="utf-8") as f:
                f.write("muted")
            msg = {
                "type": "mic_mute_update",
                "muted": True,
                "cor": "#ff0055",
                "texto": "Microfone Mutado",
                "padrao": "dormindo"
            }
            print("[INTERFACE] Microfone MUTADO.")
        else:
            for p in (FLAG_MIC_MUTED, "DADOS/mic_muted.flag"):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            msg = {
                "type": "mic_mute_update",
                "muted": False,
                "cor": "#00ffff",
                "texto": "Microfone Ativo - Ouvindo...",
                "padrao": "conversa"
            }
            print("[INTERFACE] Microfone DESMUTADO (Ativo).")

        await manager.broadcast(msg)
        return {"status": "ok", "muted": mic_muted}

    @app.get("/api/mic/status")
    async def get_mic_status():
        return {"muted": os.path.exists("DADOS/mic_muted.flag") or os.path.exists(FLAG_MIC_MUTED)}

    @app.post("/api/mic/stop")
    async def stop_mic():
        os.makedirs(os.path.join(ROOT_DIR, "DADOS"), exist_ok=True)
        flag_path = os.path.join(ROOT_DIR, "DADOS", "mic_stop.flag")
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write("stop")
        print("[INTERFACE] Sinal de parada de gravação enviado.")
        return {"status": "ok", "mensagem": "Parada de gravação solicitada."}

    @app.get("/api/voice/config")
    async def get_voice_config():
        from MODULOS.voice.voice_manager import carregar_config_voz, VOZES_DISPONIVEIS
        cfg = carregar_config_voz()
        return {
            "config": cfg,
            "opcoes": VOZES_DISPONIVEIS
        }

    @app.post("/api/voice/config")
    async def set_voice_config(data: dict):
        from MODULOS.voice.voice_manager import salvar_config_voz
        motor = data.get("motor", "kokoro")
        voz = data.get("voz", "blend_jarvis")
        nome = data.get("nome", "")
        efeito_jarvis = data.get("efeito_jarvis") if "efeito_jarvis" in data else None
        novo_cfg = salvar_config_voz(motor=motor, voz=voz, nome=nome, efeito_jarvis=efeito_jarvis)
        print(f"[INTERFACE] Voz do Jarvis alterada para: {novo_cfg}")
        
        # Sinaliza para o processo principal (main.py) executar a frase de teste
        try:
            flag_teste = os.path.join(ROOT_DIR, "DADOS", "teste_voz.flag")
            os.makedirs(os.path.dirname(flag_teste), exist_ok=True)
            with open(flag_teste, "w", encoding="utf-8") as f:
                f.write("Calibragem acústica concluída. Sistemas de voz operantes, senhor.")
            print("[INTERFACE] Sinal teste_voz.flag gravado para reprodução no processo principal.")
        except Exception as e:
            print(f"[INTERFACE] Erro ao gravar teste_voz.flag: {e}")
            
        return {"status": "ok", "config": novo_cfg}

    @app.get("/api/news/config")
    async def get_news_config():
        from MODULOS.skills.mcp_client import carregar_config_noticias
        return carregar_config_noticias()

    @app.post("/api/news/config")
    async def set_news_config(data: dict):
        from MODULOS.skills.mcp_client import carregar_config_noticias, salvar_config_noticias
        cfg = carregar_config_noticias()
        if "categorias" in data:
            cfg["categorias"] = list(data["categorias"])
        if "incluir_cotacoes" in data:
            cfg["incluir_cotacoes"] = bool(data["incluir_cotacoes"])
        if "detalhamento" in data:
            cfg["detalhamento"] = str(data["detalhamento"])
        salvo = salvar_config_noticias(cfg)
        print(f"[INTERFACE] Configuração do Briefing de Notícias atualizada: {salvo}")
        return {"status": "ok", "config": salvo}

    # ── ROTAS DE LEMBRETES / AGENDA ──
    @app.get("/api/reminders")
    async def get_reminders():
        from MODULOS.skills import reminders_module
        return {"reminders": reminders_module.listar_todos_lembretes()}

    @app.post("/api/reminders")
    async def create_reminder(data: dict):
        from MODULOS.skills import reminders_module
        texto = data.get("texto", "").strip()
        horario = data.get("horario", "").strip()
        if not texto:
            return {"status": "erro", "mensagem": "Texto do lembrete não informado."}
        novo = reminders_module.adicionar_lembrete(texto=texto, horario=horario)
        return {"status": "ok", "reminder": novo}

    @app.delete("/api/reminders/{rem_id}")
    async def delete_reminder(rem_id: str):
        from MODULOS.skills import reminders_module
        sucesso = reminders_module.remover_lembrete(rem_id)
        return {"status": "ok" if sucesso else "nao_encontrado"}

    @app.put("/api/reminders/{rem_id}/toggle")
    @app.post("/api/reminders/{rem_id}/toggle")
    async def toggle_reminder(rem_id: str):
        from MODULOS.skills import reminders_module
        sucesso = reminders_module.alternar_lembrete(rem_id)
        return {"status": "ok" if sucesso else "nao_encontrado"}

    # ── ROTAS DE BRIEFING COREOGRAFADO ──
    @app.post("/api/briefing/start")
    async def start_briefing():
        from MODULOS.skills import briefing_module
        if briefing_module.BRIEFING_EM_ANDAMENTO:
            return {"status": "em_andamento", "mensagem": "Briefing já está em execução."}
        asyncio.create_task(briefing_module.executar_briefing_coreografado())
        return {"status": "iniciado", "mensagem": "Briefing matinal coreografado iniciado."}

    @app.get("/api/briefing/status")
    async def get_briefing_status():
        from MODULOS.skills import briefing_module
        return {"ativo": briefing_module.BRIEFING_EM_ANDAMENTO}

    @app.post("/api/comando_manual")
    async def comando_manual(data: dict):
        texto = data.get("texto", "").strip()
        if texto:
            os.makedirs(os.path.join(ROOT_DIR, "DADOS"), exist_ok=True)
            cmd_path = os.path.join(ROOT_DIR, "DADOS", "comando_manual.txt")
            with open(cmd_path, "w", encoding="utf-8") as f:
                f.write(texto)
            print(f"[INTERFACE] Comando manual recebido: '{texto}'")
            return {"status": "ok", "texto": texto}
        return {"status": "vazio"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(content="", media_type="image/x-icon")

    if __name__ == "__main__":
        try:
            print("[INTERFACE] Iniciando servidor na porta 8000...")
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        except Exception:
            print("\n" + "="*60)
            print("ERRO CRÍTICO NA INICIALIZAÇÃO DO SERVIDOR")
            print("="*60)
            traceback.print_exc()
            print("="*60)
            if sys.stdin and sys.stdin.isatty():
                input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")

except Exception:
    import traceback
    print("\n" + "="*60)
    print("ERRO FATAL NO MODULO INTERFACE_SERVER")
    print("="*60)
    traceback.print_exc()
    print("="*60)
    if sys.stdin and sys.stdin.isatty():
        input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")
