import os
import json
import subprocess
import ollama
from win32com.client import Dispatch
from rapidfuzz import process

CACHE_FILE = "DADOS/apps_cache.json"
PROGRAMAS_INSTALADOS = {}

# --- 1. DEFINIÇÃO DAS FUNÇÕES (O Python guarda na memória) ---

def escanear_e_salvar():
    print("🔍 Jarvis limpando e localizando executáveis reais...")
    
    # Palavras que indicam que o arquivo NÃO é um programa principal
    blacklist = [
        'unins', 'setup', 'installer', 'helper', 'crash', 'proxy', 'msal', 
        'driver', 'cmd', 'wmp', 'imagingdevices', 'patch', 'update', 'fix'
    ]
    
    pastas = [
        os.path.join(os.environ['PROGRAMDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ['LOCALAPPDATA'], 'Discord'),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        r"C:\Program Files",
        r"C:\Program Files (x86)"
    ]
    
    shell = Dispatch('WScript.Shell')
    encontrados = {}

    for pasta in pastas:
        if not os.path.exists(pasta): continue
        for root, _, files in os.walk(pasta):
            for file in files:
                if file.endswith((".lnk", ".exe")):
                    nome_limpo = file.replace(".lnk", "").replace(".exe", "").lower()
                    
                    # --- FILTRO DE INTELIGÊNCIA ---
                    if len(nome_limpo) < 3: continue
                    if any(word in nome_limpo for word in blacklist): continue
                    
                    caminho_completo = os.path.join(root, file)
                    
                    if file.endswith(".lnk"):
                        try:
                            target = shell.CreateShortCut(caminho_completo).TargetPath
                            if target and os.path.exists(target) and target.lower().endswith(".exe"):
                                encontrados[nome_limpo] = target
                        except: continue
                    else:
                        encontrados[nome_limpo] = caminho_completo

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(encontrados, f, indent=4)
    return encontrados

def perguntar_ao_llama_sobre_programa(alvo, lista_programas):
    try:
        nomes_mostra = ", ".join(lista_programas[:100])
        prompt = (
            f"SISTEMA: Você é um seletor de arquivos. O usuário quer: '{alvo}'.\n"
            f"ARQUIVOS: [{nomes_mostra}]\n"
            "RESPOSTA: Responda APENAS o nome do arquivo da lista. Sem explicações."
        )
        res = ollama.chat(model="llama3.2:3b", messages=[{'role': 'user', 'content': prompt}])
        resposta = res['message']['content'].strip().lower().split('\n')[0].replace("'", "").replace('"', "")
        return resposta if resposta in lista_programas else None
    except:
        return None

def executar_comando(alvo):
    global PROGRAMAS_INSTALADOS
    if not alvo or len(alvo) < 2: return None
    
    nomes = list(PROGRAMAS_INSTALADOS.keys())
    
    if "não existe" in alvo.lower() or "não encontrado" in alvo.lower():
        return "Não consegui identificar o programa, senhor."

    match = process.extractOne(alvo, nomes, score_cutoff=90) 

    if match:
        nome_final = match[0]
        print(f"🎯 Match direto encontrado: {nome_final}")
    else:
        nome_final = next((n for n in nomes if alvo.lower() in n.lower()), None)
        if not nome_final:
            print(f"🤔 '{alvo}' não é óbvio. Consultando Llama...")
            nome_final = perguntar_ao_llama_sobre_programa(alvo, nomes)

    if nome_final and nome_final in PROGRAMAS_INSTALADOS:
        caminho = PROGRAMAS_INSTALADOS[nome_final]
        try:
            subprocess.Popen([caminho], shell=True, creationflags=subprocess.DETACHED_PROCESS)
            return f"Iniciando {nome_final}, senhor."
        except Exception as e:
            return f"Erro técnico ao abrir {nome_final}: {e}"

    return f"Não localizei o '{alvo}' no sistema."

# --- 2. INICIALIZAÇÃO DO MÓDULO (Sempre depois das funções) ---

def inicializar_modulo():
    global PROGRAMAS_INSTALADOS
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                PROGRAMAS_INSTALADOS = json.load(f)
            # Se o arquivo existir mas estiver vazio, escaneia de novo
            if not PROGRAMAS_INSTALADOS:
                PROGRAMAS_INSTALADOS = escanear_e_salvar()
        except:
            PROGRAMAS_INSTALADOS = escanear_e_salvar()
    else:
        PROGRAMAS_INSTALADOS = escanear_e_salvar()

# EXECUTA A INICIALIZAÇÃO AO IMPORTAR O MÓDULO
inicializar_modulo()