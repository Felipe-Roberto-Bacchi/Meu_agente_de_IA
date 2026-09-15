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
    if os.path.exists("INTERFACE"):
        app.mount("/INTERFACE", StaticFiles(directory="INTERFACE"), name="INTERFACE")

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

    async def broadcast_hardware_status():
        from MODULOS.system import hardware_module
        while True:
            try:
                # Obtém o dict bruto de sensores
                hw_info = {
                    "cpu_usage": psutil.cpu_percent(),
                    "ram_usage": psutil.virtual_memory().percent,
                }
                # Tenta pegar dados da GPU (pode falhar se hardware_module não estiver pronto ou sem GPU)
                try:
                    gpu_data = await hardware_module._ler_gpu_lhm()
                    hw_info.update(gpu_data)
                except: pass
                
                await manager.broadcast({"type": "hardware_update", "hardware": hw_info})
            except Exception:
                pass
            await asyncio.sleep(2)

    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(broadcast_hardware_status())

    @app.get("/")
    async def get():
        with open("C:\\projeto ia\\teste 2\\Meu-agente-IA-main\\INTERFACE\\index.html", "r", encoding="utf-8") as f:
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
            input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")

except Exception:
    import traceback
    print("\n" + "="*60)
    print("ERRO FATAL NO MODULO INTERFACE_SERVER")
    print("="*60)
    traceback.print_exc()
    print("="*60)
    input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")
