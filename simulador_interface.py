import time
import httpx
import webbrowser
import subprocess
import sys
import os
import json

# Tenta importar psutil para liberar a porta, se falhar ignora
try:
    import psutil
    def liberar_porta_8000():
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.net_connections(kind='inet'):
                    if conn.laddr.port == 8000:
                        print(f"[SIMULADOR] Liberando porta 8000 (Encerrando processo antigo {proc.pid})...")
                        proc.terminate()
            except: continue
except ImportError:
    def liberar_porta_8000(): pass

def simular():
    print("\n" + "="*50)
    print("   JARVIS - SIMULADOR DE INTERFACE NEON")
    print("="*50 + "\n")

    liberar_porta_8000()
    time.sleep(1)

    # 1. Inicia o servidor
    print("[1/4] Iniciando servidor de interface...")
    proc = subprocess.Popen([sys.executable, "-m", "MODULOS.system.interface_server"], 
                            creationflags=subprocess.CREATE_NEW_CONSOLE)
    time.sleep(3) # Espera o servidor subir
    
    # 2. Abre o navegador
    print("[2/4] Abrindo painel visual...")
    webbrowser.open("http://localhost:8000")
    time.sleep(2)
    
    # 3. Modelos de exemplo vibrantes
    modelos = [
        "Núcleo_Llama_3B",
        "Cérebro_72B_Master",
        "Visão_Moondream",
        "Código_Python_32B",
        "Roteador_Qwen_1.5B"
    ]
    
    print("[3/4] Inicializando rosquinhas neons...")
    try:
        httpx.post("http://localhost:8000/system/download_progress", json={
            "lista_modelos": modelos,
            "mensagem": "Sincronizando núcleos neurais...",
            "progresso_total": 0,
            "ativo": True
        })
    except:
        print("[ERRO] Não foi possível conectar ao servidor. Verifique a porta 8000.")
        return

    print("[4/4] Executando coreografia de cores...")
    
    # Simula progresso individual e global
    for p in range(0, 101, 2):
        for i, m in enumerate(modelos):
            # Cada modelo sobe em uma velocidade levemente diferente para efeito visual
            offset = i * 15
            prog_individual = min(100, p + offset if p > 5 else 0)
            
            try:
                httpx.post("http://localhost:8000/system/download_progress", json={
                    "model_id": m,
                    "progresso": prog_individual,
                    "progresso_total": p,
                    "mensagem": f"Alinhando Sincrotron: {m} ({prog_individual}%)"
                })
            except: break
        time.sleep(0.15)
        
    print("\n[OK] Simulação completa!")
    print("O painel de roscas deve estar brilhando agora no navegador.")
    print("Mantenha esta janela aberta para ver o design. Pressione ENTER para sair.")
    
    try:
        input()
        proc.terminate()
    except:
        proc.terminate()

if __name__ == "__main__":
    simular()
