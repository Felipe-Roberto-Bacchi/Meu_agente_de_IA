import os
import json
import subprocess
import ollama
try:
    from win32com.client import Dispatch
except ImportError:
    Dispatch = None

try:
    from rapidfuzz import process
except ImportError:
    process = None

CACHE_FILE = "DADOS/apps_cache.json"
PROGRAMAS_INSTALADOS = {}

# --- 1. DEFINIÇÃO DAS FUNÇÕES (O Python guarda na memória) ---

def escanear_e_salvar():
    print("[ACTIONS] Jarvis localizando executaveis no sistema...")
    
    # Pastas que NUNCA devem ser escaneadas
    blacklist_dirs = [
        'git\\usr', 'git\\mingw', 'installer', '.venv', 'site-packages',
        'node_modules', 'target\\release', 'target\\debug', 'cuda', 'sdk',
        'framing', 'resources\\bin', 'common files'
    ]

    # Palavras que indicam que o arquivo NÃO é um programa principal do usuário
    blacklist = [
        'unins', 'setup', 'installer', 'helper', 'crash', 'proxy', 'msal', 
        'driver', 'cmd', 'wmp', 'imagingdevices', 'patch', 'update', 'fix',
        'icon', 'cli', 'build_script', 'python314', 'daemon', 'service',
        'agent', 'crashpad', 'redist'
    ]
    
    pastas = [
        os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Discord'),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        r"C:\Program Files",
        r"C:\Program Files (x86)"
    ]
    
    shell = Dispatch('WScript.Shell') if Dispatch else None
    encontrados = {}

    for pasta in pastas:
        if not pasta or not os.path.exists(pasta): continue
        for root, dirs, files in os.walk(pasta):
            # Filtra subpastas em tempo de percurso para não gastar tempo nem indexar lixo
            dirs[:] = [
                d for d in dirs 
                if not any(b in os.path.join(root, d).lower() for b in blacklist_dirs)
            ]
            root_lower = root.lower()
            if any(b in root_lower for b in blacklist_dirs):
                continue

            for file in files:
                if file.endswith((".lnk", ".exe")):
                    nome_limpo = file.replace(".lnk", "").replace(".exe", "").lower()
                    
                    # --- FILTRO DE INTELIGÊNCIA ---
                    if len(nome_limpo) < 3: continue
                    if any(word in nome_limpo for word in blacklist): continue
                    
                    caminho_completo = os.path.join(root, file)
                    
                    if file.endswith(".lnk"):
                        if shell:
                            try:
                                target = shell.CreateShortCut(caminho_completo).TargetPath
                                if target and os.path.exists(target) and target.lower().endswith(".exe"):
                                    t_lower = target.lower()
                                    if not any(b in t_lower for b in blacklist_dirs) and not any(w in t_lower for w in blacklist):
                                        encontrados[nome_limpo] = target
                            except: continue
                    else:
                        encontrados[nome_limpo] = caminho_completo

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(encontrados, f, indent=4, ensure_ascii=False)
    print(f"[ACTIONS] Cache de aplicativos atualizado com {len(encontrados)} programas limpos.")
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

    match = process.extractOne(alvo, nomes, score_cutoff=90) if process else None

    if match:
        nome_final = match[0]
        print(f"[ACTIONS] Match direto encontrado: {nome_final}")
    else:
        nome_final = next((n for n in nomes if alvo.lower() in n.lower()), None)
        if not nome_final:
            print(f"[ACTIONS] '{alvo}' não é óbvio. Consultando Llama...")
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