# CONTEXTO COMPLETO DO PROJETO JARVIS



==================================================
 ARQUIVO: .\empacotar.py
==================================================

```python
import os

# Configurações
ARQUIVO_SAIDA = "CONTEXTO_JARVIS.md"
PASTAS_IGNORAR = {'.git', '__pycache__', 'monitor', 'TEMP_AUDIO'} # Pastas pesadas/binárias
EXTENSOES_PERMITIDAS = {'.py', '.json', '.yaml', '.html', '.css', '.js'} # Só o que é código/texto

def empacotar_projeto():
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f_out:
        f_out.write("# CONTEXTO COMPLETO DO PROJETO JARVIS\n\n")
        
        for raiz, diretorios, arquivos in os.walk('.'):
            # Filtra pastas ignoradas
            diretorios[:] = [d for d in diretorios if d not in PASTAS_IGNORAR]
            
            for arquivo in arquivos:
                extensao = os.path.splitext(arquivo)[1]
                if extensao in EXTENSOES_PERMITIDAS:
                    caminho_completo = os.path.join(raiz, arquivo)
                    
                    f_out.write(f"\n\n{'='*50}\n")
                    f_out.write(f" ARQUIVO: {caminho_completo}\n")
                    f_out.write(f"{'='*50}\n\n")
                    f_out.write("```python\n" if extensao == '.py' else "```text\n")
                    
                    try:
                        with open(caminho_completo, 'r', encoding='utf-8') as f_in:
                            f_out.write(f_in.read())
                    except Exception as e:
                        f_out.write(f"ERRO AO LER ARQUIVO: {e}")
                        
                    f_out.write("\n```\n")

    print(f"Pronto! Tudo foi empacotado em: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    empacotar_projeto()

```


==================================================
 ARQUIVO: .\main.py
==================================================

```python
import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import subprocess
import time
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.system.logger import log
from MODULOS.system.config import carregar_configuracao
from MODULOS.system.services import liberar_porta_8000, iniciar_ollama_se_necessario
from MODULOS.system.sync import gerenciar_downloads_iniciais
from MODULOS.system.integrity import verificar_modelos_faltantes
from MODULOS.skills import hardware_module
from MODULOS.memory import memory_long
from MODULOS.voice import voice_manager
from MODULOS.brain.selector import selector as brain_selector
from MODULOS import ear
from MODULOS import brain

CONFIG_FILE = "DADOS/config_paths.json"

_executor = ThreadPoolExecutor(max_workers=1)

async def _capturar_async() -> tuple[bool, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, ear.capturar_comando_dinamico)

async def loop_principal():
    """Loop infinito de escuta e processamento."""
    log.info("Sincronização de sentidos concluída.")
    
    # Inicia o processador de voz em background
    asyncio.create_task(voice_manager.processador_de_fala())
    # Inicia o monitoramento térmico em background
    asyncio.create_task(hardware_module.sentinela_hardware())
    
    # Saudação inicial baseada no horário
    hora = time.localtime().tm_hour
    if hora < 12: saudacao = "Bom dia, senhor."
    elif hora < 18: saudacao = "Boa tarde, senhor."
    else: saudacao = "Boa noite, senhor."
    
    await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
    await voice_manager.falar("Jarvis", saudacao, prioridade=1)
    
    estado_anterior = None
    
    while True:
        # 0. Verifica se chegou solicitação de teste de voz pela interface
        flag_teste_voz = "DADOS/teste_voz.flag"
        if os.path.exists(flag_teste_voz):
            try:
                with open(flag_teste_voz, "r", encoding="utf-8") as f:
                    texto_teste = f.read().strip()
                os.remove(flag_teste_voz)
                if texto_teste:
                    log.info(f"[TESTE DE VOZ]: \"{texto_teste}\"")
                    await atualizar_jarvis(cor_hex="#00ffff", texto=texto_teste, padrao="conversa")
                    await voice_manager.falar("Jarvis", texto_teste, prioridade=0)
            except Exception as e_teste:
                log.error(f"Erro ao processar teste_voz.flag: {e_teste}")

        # 1. Verifica se chegou comando manual de texto pela interface
        flag_manual = "DADOS/comando_manual.txt"
        if os.path.exists(flag_manual):
            try:
                with open(flag_manual, "r", encoding="utf-8") as f:
                    texto_manual = f.read().strip()
                os.remove(flag_manual)
            except Exception:
                texto_manual = ""

            if texto_manual:
                log.info(f"[COMANDO MANUAL]: \"{texto_manual}\"")
                await atualizar_jarvis(cor_hex="#00ffff", texto=f"Comando: {texto_manual}", padrao="conversa")
                memory_long.registrar_conversa_global("user", texto_manual)

                if ear.verificar_despedida(texto_manual):
                    despedida = "Até logo, senhor. Estarei aqui quando precisar."
                    await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
                    await voice_manager.falar("Jarvis", despedida, prioridade=1)
                    memory_long.registrar_conversa_global("assistant", despedida)
                    continue

                await atualizar_jarvis(cor_hex="#3366ff", texto="Pensando...", padrao="conversa")
                cor_fala, padrao, resposta = await brain.processar_comando(texto_manual)
                if resposta:
                    await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
                    log.info(f"[JARVIS]: {resposta}")
                    memory_long.registrar_conversa_global("assistant", resposta)
                    await voice_manager.falar("Jarvis", resposta, prioridade=1)
                else:
                    await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")
                continue

        tem_audio, estado_atual = await _capturar_async()
        
        if estado_atual != estado_anterior:
            if estado_atual == ear.Estado.ATIVO:
                saudacao = "Sim, senhor?"
                await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
                await voice_manager.falar("Jarvis", saudacao, prioridade=1)
                print("\n--- [ATIVO] Pronto para comandos ---")
            elif estado_anterior == ear.Estado.ATIVO and estado_atual == ear.Estado.DORMINDO:
                await atualizar_jarvis(cor_hex="#1a0033", texto="Aguardando...", padrao="dormindo")
                print("\n--- [DORMINDO] Diga 'Jarvis' para ativar ---")

        estado_anterior = estado_atual
        if not tem_audio: continue

        await atualizar_jarvis(cor_hex="#00ffff", texto="Transcrevendo áudio...", padrao="tarefa")
        texto_bruto = ear.transcrever_audio()
        if not texto_bruto:
            log.info("[EAR] Áudio capturado sem palavras reconhecíveis.")
            await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")
            continue

        log.info(f"[ESCUTADO]: \"{texto_bruto}\"")
        memory_long.registrar_conversa_global("user", texto_bruto)

        if ear.verificar_despedida(texto_bruto):
            ear.set_estado(ear.Estado.DORMINDO)
            despedida = "Até logo, senhor. Estarei aqui quando precisar."
            await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
            await voice_manager.falar("Jarvis", despedida, prioridade=1)
            memory_long.registrar_conversa_global("assistant", despedida)
            continue

        await atualizar_jarvis(cor_hex="#3366ff", texto="Pensando...", padrao="conversa")
        cor_fala, padrao, resposta = await brain.processar_comando(texto_bruto)
        if resposta:
            await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
            log.info(f"[JARVIS]: {resposta}")
            memory_long.registrar_conversa_global("assistant", resposta)
            await voice_manager.falar("Jarvis", resposta, prioridade=1)
            # Aguarda a fala iniciar e concluir para não gravar eco ou cliques
            await asyncio.sleep(0.15)
            while voice_manager.STATUS_FALANDO:
                await asyncio.sleep(0.1)
        else:
            await atualizar_jarvis(cor_hex="#00ffff", texto="Pronto para comandos", padrao="conversa")

if __name__ == "__main__":
    import webbrowser
    import traceback
    
    # 0. Garante que a porta 8000 esteja livre (libera instâncias antigas travadas)
    liberar_porta_8000()

    try:
        # 1. Garante que o Ollama esteja rodando ANTES de qualquer outra coisa
        if not iniciar_ollama_se_necessario():
            log.critical("Não foi possível iniciar o serviço Ollama.")
            input("Pressione ENTER para fechar...")
            sys.exit(1)

        config = carregar_configuracao()
        
        if not config:
            # Fluxo de Primeiro Acesso (Instalador)
            python_exe = sys.executable
            # Usamos cmd /k para garantir que a janela fique aberta se houver erro de sistema/importação
            subprocess.Popen(["cmd", "/k", python_exe, "-m", "MODULOS.system.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            time.sleep(2)
            webbrowser.open("http://localhost:8000")
            
            while not os.path.exists(CONFIG_FILE):
                time.sleep(1)
            
            config = carregar_configuracao()
            log.info("Configuração recebida! Iniciando transferência dos núcleos...")
            asyncio.run(gerenciar_downloads_iniciais(config))
            log.info("Tudo pronto! Por favor, reinicie o Jarvis.")
            time.sleep(5)
            sys.exit()

        # Fluxo Normal (Já configurado)
        
        # 1. Inicia o servidor de interface (Apenas uma vez)
        subprocess.Popen(["cmd", "/k", sys.executable, "-m", "MODULOS.system.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        webbrowser.open("http://localhost:8000")

        # 2. VERIFICAÇÃO DE INTEGRIDADE: Se faltar modelo leve, recupera apenas os leves
        if asyncio.run(verificar_modelos_faltantes(config)):
            log.warning("Núcleos neurais incompletos. Iniciando recuperação...")
            asyncio.run(gerenciar_downloads_iniciais(config, incluir_pesados=False))
            log.info("Integridade restaurada. Reiniciando fluxo principal...")

        brain_selector.calibrar_e_salvar()
        memory_long.inicializar_banco()
        # Whisper e Kokoro operam em lazy-loading sob demanda para boot quase instantâneo
        ear.calibrar_ruido(duracao=2)

        asyncio.run(loop_principal())
        
    except KeyboardInterrupt:
        log.info("Finalizado pelo usuário.")
    except Exception as e:
        log.critical("ERRO CRÍTICO NO BOOT DO JARVIS")
        log.exception(e)
        input("\nJanela travada para diagnóstico. Pressione ENTER para fechar...")

```


==================================================
 ARQUIVO: .\obsidian_sync.py
==================================================

```python
"""
obsidian_sync.py — Sincronizador automático Projeto → Obsidian
Uso:
    python obsidian_sync.py                  # gera vault e sai
    python obsidian_sync.py --watch          # gera e fica monitorando mudanças
    python obsidian_sync.py --vault C:/MeuVault  # define pasta do vault
"""

import os
import ast
import json
import time
import hashlib
import argparse
import textwrap
from pathlib import Path
from datetime import datetime

# ─── Dependência opcional para modo --watch ───────────────────────────────────
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_OK = True
except ImportError:
    WATCHDOG_OK = False

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

# Raiz do seu projeto (a pasta onde este script está)
PROJECT_ROOT = Path(__file__).parent

# Onde ficará o vault do Obsidian
DEFAULT_VAULT = PROJECT_ROOT / "OBSIDIAN_VAULT"

# Pastas/arquivos a ignorar ao varrer o projeto
IGNORE_DIRS  = {"__pycache__", ".git", "node_modules", "runtimes", "monitor",
                "OBSIDIAN_VAULT", "TEMP_AUDIO", "TESTE_FALA"}
IGNORE_FILES = {".gitkeep", ".gitignore", "*.pyc", "*.rar", "*.zip",
                "*.bin", "*.wav", "*.dll", "*.exe", "*.pdb", "*.so",
                "*.dylib", "*.db", "*.sqlite3"}

# Extensões que terão nota individual com análise de código
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html"}

# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def should_ignore(path: Path) -> bool:
    if path.is_dir() and path.name in IGNORE_DIRS:
        return True
    if path.is_file():
        for pat in IGNORE_FILES:
            if pat.startswith("*"):
                if path.suffix == pat[1:]:
                    return True
            elif path.name == pat:
                return True
    return False


def file_hash(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def slugify(text: str) -> str:
    """Remove caracteres inválidos para nome de arquivo."""
    return "".join(c if c.isalnum() or c in " _-." else "_" for c in text).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))

# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISE DE CÓDIGO PYTHON
# ══════════════════════════════════════════════════════════════════════════════

def parse_python(path: Path) -> dict:
    """Extrai classes, funções e docstrings de um arquivo .py."""
    info = {"classes": [], "functions": [], "imports": [], "docstring": ""}
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        info["docstring"] = (ast.get_docstring(tree) or "").strip()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    info["imports"].append(node.module)
                else:
                    for alias in node.names:
                        info["imports"].append(alias.name)
            elif isinstance(node, ast.ClassDef):
                doc = (ast.get_docstring(node) or "").strip()
                methods = [n.name for n in ast.walk(node)
                           if isinstance(n, ast.FunctionDef) and n.col_offset > node.col_offset]
                info["classes"].append({"name": node.name, "doc": doc, "methods": methods})
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                doc = (ast.get_docstring(node) or "").strip()
                args = [a.arg for a in node.args.args]
                info["functions"].append({"name": node.name, "doc": doc, "args": args})
    except Exception as e:
        info["error"] = str(e)
    return info


def parse_js(path: Path) -> dict:
    """Extrai funções/comentários básicos de .js."""
    info = {"functions": [], "exports": []}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            s = line.strip()
            if s.startswith("function ") or "const " in s and "=>" in s:
                info["functions"].append(s[:100])
            if s.startswith("export "):
                info["exports"].append(s[:100])
    except Exception:
        pass
    return info

# ══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE NOTAS MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def frontmatter(tags: list, extra: dict = None) -> str:
    lines = ["---", f'updated: "{ts()}"', f'tags: [{", ".join(tags)}]']
    if extra:
        for k, v in extra.items():
            lines.append(f'{k}: "{v}"')
    lines.append("---\n")
    return "\n".join(lines)


def note_for_python(path: Path) -> str:
    info   = parse_python(path)
    relp   = rel(path)
    parent = path.parent.name
    lines  = [
        frontmatter(["python", "módulo", parent], {"arquivo": relp}),
        f"# 🐍 `{path.name}`\n",
        f"> `{relp}`\n",
    ]
    if info.get("docstring"):
        lines += [f"## Descrição\n{info['docstring']}\n"]
    if info.get("error"):
        lines += [f"> [!WARNING] Erro ao parsear: {info['error']}\n"]

    # Imports relevantes → links internos
    local_imports = [i for i in info["imports"] if not i.startswith(("os","sys","re","json","time","datetime","typing","abc","collections","pathlib","threading","asyncio","logging"))]
    if local_imports:
        lines.append("## Dependências\n")
        for imp in sorted(set(local_imports)):
            lines.append(f"- [[{imp}]]")
        lines.append("")

    if info["classes"]:
        lines.append("## Classes\n")
        for cls in info["classes"]:
            lines.append(f"### `{cls['name']}`")
            if cls["doc"]:
                lines.append(f"{cls['doc']}\n")
            if cls["methods"]:
                lines.append("**Métodos:** " + ", ".join(f"`{m}`" for m in cls["methods"]))
            lines.append("")

    if info["functions"]:
        lines.append("## Funções\n")
        for fn in info["functions"]:
            args_str = ", ".join(fn["args"]) if fn["args"] else ""
            lines.append(f"### `{fn['name']}({args_str})`")
            if fn["doc"]:
                lines.append(fn["doc"])
            lines.append("")

    lines += [
        "## Notas pessoais\n",
        "> Espaço livre para suas anotações sobre este módulo.\n"
    ]
    return "\n".join(lines)


def note_for_js(path: Path) -> str:
    info  = parse_js(path)
    relp  = rel(path)
    lines = [
        frontmatter(["javascript", "frontend"], {"arquivo": relp}),
        f"# 📜 `{path.name}`\n",
        f"> `{relp}`\n",
    ]
    if info["functions"]:
        lines.append("## Funções / Callbacks\n")
        for fn in info["functions"][:30]:
            lines.append(f"- `{fn}`")
        lines.append("")
    if info["exports"]:
        lines.append("## Exports\n")
        for ex in info["exports"][:20]:
            lines.append(f"- `{ex}`")
        lines.append("")
    lines += ["## Notas pessoais\n", "> …\n"]
    return "\n".join(lines)


def note_for_generic(path: Path) -> str:
    relp  = rel(path)
    ext   = path.suffix.lstrip(".") or "arquivo"
    lines = [
        frontmatter([ext, "recurso"], {"arquivo": relp}),
        f"# 📄 `{path.name}`\n",
        f"> `{relp}`\n",
        "## Descrição\n",
        "> Adicione aqui uma descrição deste arquivo.\n",
    ]
    return "\n".join(lines)


def note_for_folder(folder: Path, children_files: list, children_dirs: list) -> str:
    relp  = rel(folder)
    name  = folder.name
    lines = [
        frontmatter(["pasta", name]),
        f"# 📁 {name}\n",
        f"> `{relp}`\n",
    ]
    if children_dirs:
        lines.append("## Sub-pastas\n")
        for d in sorted(children_dirs):
            lines.append(f"- [[{d.name}/_{d.name}|{d.name}/]]")
        lines.append("")
    if children_files:
        lines.append("## Arquivos\n")
        for f in sorted(children_files):
            note_name = slugify(f.stem)
            lines.append(f"- [[{name}/{note_name}|{f.name}]]")
        lines.append("")
    lines += ["## Notas\n", "> …\n"]
    return "\n".join(lines)


def note_overview(structure: dict) -> str:
    """Nota raiz do projeto."""
    now  = ts()
    root = PROJECT_ROOT.name
    lines = [
        frontmatter(["projeto", "visão-geral", "JARVIS"]),
        f"# 🤖 {root}\n",
        f"*Sincronizado em: {now}*\n",
        "## Estrutura do projeto\n",
    ]
    for folder, files in sorted(structure.items()):
        if folder == ".":
            lines.append("### Raiz\n")
        else:
            lines.append(f"### [[{Path(folder).name}/_{Path(folder).name}|📁 {folder}]]\n")
        for f in sorted(files):
            slug = slugify(f.stem)
            parent = Path(folder).name if folder != "." else ""
            link = f"{parent}/{slug}" if parent else slug
            lines.append(f"- [[{link}|{f.name}]]")
        lines.append("")

    lines += [
        "## Módulos principais\n",
        "| Módulo | Papel |\n|---|---|\n",
        "| [[brain/core/router|router.py]] | Roteamento de intenções |\n",
        "| [[brain/core/executor|executor.py]] | Execução de ações |\n",
        "| [[brain/core/conversation|conversation.py]] | Gerenciamento de diálogo |\n",
        "| [[MODULOS/memory_long|memory_long.py]] | Memória de longo prazo |\n",
        "| [[MODULOS/memory_short|memory_short.py]] | Memória de curto prazo |\n",
        "| [[MODULOS/voice_manager|voice_manager.py]] | Gerenciador de voz |\n",
        "| [[MODULOS/interface_server|interface_server.py]] | Servidor WebSocket |\n",
        "| [[INTERFACE/app|app.js]] | Frontend Three.js |\n",
        "\n## Diagrama de fluxo\n",
        "```\nUsuário → Voz (ear/) → NLP → Brain (router) → Executor → Ação\n"
        "                                    ↓\n"
        "                             Memória (short/long)\n```\n",
        "\n## Notas gerais\n",
        "> Adicione aqui notas sobre decisões de arquitetura, TODOs e ideias.\n",
    ]
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
# MOTOR DE SINCRONIZAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

class VaultSync:
    def __init__(self, vault: Path):
        self.vault     = vault
        self.vault.mkdir(parents=True, exist_ok=True)
        self.hash_file = vault / ".obsidian_hashes.json"
        self.hashes    = self._load_hashes()
        self.structure = {}   # folder_rel → [Path, ...]

    def _load_hashes(self) -> dict:
        if self.hash_file.exists():
            try:
                return json.loads(self.hash_file.read_text())
            except Exception:
                pass
        return {}

    def _save_hashes(self):
        self.hash_file.write_text(json.dumps(self.hashes, indent=2))

    def _vault_path(self, source: Path) -> Path:
        """Calcula onde a nota do arquivo source ficará no vault."""
        try:
            rel_parts = source.relative_to(PROJECT_ROOT).parts
        except ValueError:
            rel_parts = (source.name,)
        # Nota fica em vault/<pasta>/<stem>.md
        note_dir  = self.vault.joinpath(*rel_parts[:-1]) if len(rel_parts) > 1 else self.vault
        note_name = slugify(source.stem) + ".md"
        return note_dir / note_name

    def _write_note(self, note_path: Path, content: str):
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")

    def sync_file(self, path: Path, force: bool = False) -> bool:
        """Sincroniza um arquivo individual. Retorna True se escreveu."""
        h = file_hash(path)
        key = str(path)
        if not force and self.hashes.get(key) == h:
            return False   # sem mudança

        ext = path.suffix.lower()
        if ext == ".py":
            content = note_for_python(path)
        elif ext == ".js":
            content = note_for_js(path)
        elif ext in CODE_EXTENSIONS:
            content = note_for_generic(path)
        else:
            return False   # ignora binários etc.

        note_path = self._vault_path(path)
        self._write_note(note_path, content)
        self.hashes[key] = h
        return True

    def cleanup_orphans(self, active_sources: set):
        """Remove notas do vault cujos arquivos fonte não existem mais."""
        import shutil
        removed = 0

        # 1) Apaga notas do cache que sumiram do projeto
        dead_keys = []
        for key in list(self.hashes.keys()):
            if key.startswith("DIR:"):
                continue
            source = Path(key)
            if str(source) not in active_sources:
                note_path = self._vault_path(source)
                if note_path.exists():
                    note_path.unlink()
                    print(f"  🗑️  Removido: {note_path.name}")
                    removed += 1
                dead_keys.append(key)
        for key in dead_keys:
            del self.hashes[key]

        # 2) Varre TODAS as pastas do vault e remove as que não existem no projeto
        for vault_dir in sorted(self.vault.rglob("*"), reverse=True):
            if not vault_dir.is_dir():
                continue
            if vault_dir.name == ".obsidian":
                continue
            try:
                rel_parts = vault_dir.relative_to(self.vault)
                project_dir = PROJECT_ROOT / rel_parts
                if not project_dir.exists():
                    shutil.rmtree(vault_dir, ignore_errors=True)
                    print(f"  🗑️  Pasta removida: {rel_parts}")
                    removed += 1
            except Exception:
                pass

        # 3) Remove pastas vazias restantes
        for dirpath in sorted(self.vault.rglob("*"), reverse=True):
            if dirpath.is_dir() and dirpath.name != ".obsidian":
                try:
                    if not any(dirpath.iterdir()):
                        dirpath.rmdir()
                except Exception:
                    pass

        if removed:
            print(f"  🧹 {removed} item(ns) órfão(s) removido(s).")
        return removed

    def sync_all(self):
        print(f"\n[{ts()}] 🔄 Iniciando sincronização completa...")
        written = 0
        skipped = 0
        active_sources = set()

        all_py_files = []

        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)

            # Filtrar dirs ignorados (in-place para não descer neles)
            dirs[:] = [d for d in dirs
                       if not should_ignore(root_path / d)]

            rel_root = str(root_path.relative_to(PROJECT_ROOT)) if root_path != PROJECT_ROOT else "."
            valid_files = [root_path / f for f in files
                           if not should_ignore(root_path / f)
                           and Path(f).suffix.lower() in CODE_EXTENSIONS]

            if valid_files:
                self.structure[rel_root] = valid_files

            for fpath in valid_files:
                active_sources.add(str(fpath))
                if fpath.suffix == ".py":
                    all_py_files.append(fpath)
                try:
                    if self.sync_file(fpath):
                        print(f"  ✅ {rel(fpath)}")
                        written += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"  ❌ {rel(fpath)}: {e}")

            # Nota de pasta
            sub_dirs   = [root_path / d for d in dirs]
            folder_key = str(root_path)
            h_folder   = hashlib.md5(str(sorted([rel(f) for f in valid_files])).encode()).hexdigest()
            if self.hashes.get(f"DIR:{folder_key}") != h_folder:
                self._generate_folder_note(root_path, valid_files, sub_dirs)
                self.hashes[f"DIR:{folder_key}"] = h_folder

        # Nota raiz do projeto
        self._write_note(self.vault / "_PROJETO.md", note_overview(self.structure))

        # Remove notas de arquivos que não existem mais
        self.cleanup_orphans(active_sources)

        self._save_hashes()
        print(f"\n✨ Concluído — {written} nota(s) atualizadas, {skipped} sem mudança.")
        print(f"   Vault: {self.vault}\n")

    def _generate_folder_note(self, folder: Path, files: list, subdirs: list):
        if folder == PROJECT_ROOT:
            return
        content   = note_for_folder(folder, files, subdirs)
        note_path = self._vault_path(folder) .parent / f"_{slugify(folder.name)}.md"
        # Para a raiz-relativa do vault
        try:
            vault_folder = self.vault / folder.relative_to(PROJECT_ROOT)
        except ValueError:
            vault_folder = self.vault / folder.name
        note_path = vault_folder / f"_{slugify(folder.name)}.md"
        self._write_note(note_path, content)

    def sync_single(self, path: Path):
        """Chamado pelo watcher ao detectar mudança em um arquivo."""
        if should_ignore(path) or path.suffix.lower() not in CODE_EXTENSIONS:
            return
        try:
            if self.sync_file(path, force=True):
                print(f"[{ts()}] 📝 Atualizado: {rel(path)}")
                self._save_hashes()
        except Exception as e:
            print(f"[{ts()}] ❌ Erro ao atualizar {rel(path)}: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MODO WATCH (watchdog)
# ══════════════════════════════════════════════════════════════════════════════

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, sync: VaultSync):
        self.sync   = sync
        self._debounce: dict = {}

    def _handle(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Debounce simples: ignora eventos duplicados em < 1 s
        now = time.time()
        last = self._debounce.get(str(path), 0)
        if now - last < 1.0:
            return
        self._debounce[str(path)] = now
        self.sync.sync_single(path)

    def on_modified(self, event): self._handle(event)
    def on_created(self, event):  self._handle(event)

    def on_deleted(self, event):
        path = Path(event.src_path)
        if event.is_directory:
            # Pasta deletada: remove todas as notas que estavam dentro dela
            removed = 0
            dead_keys = [k for k in list(self.sync.hashes.keys())
                         if not k.startswith("DIR:") and str(path) in k]
            for key in dead_keys:
                note_path = self.sync._vault_path(Path(key))
                if note_path.exists():
                    note_path.unlink()
                    removed += 1
                del self.sync.hashes[key]
            # Remove a pasta correspondente no vault se estiver vazia
            try:
                vault_dir = self.sync.vault / path.relative_to(PROJECT_ROOT)
                if vault_dir.exists():
                    import shutil
                    shutil.rmtree(vault_dir)
            except Exception:
                pass
            if removed:
                print(f"[{ts()}] 🗑️  Pasta removida: {path.name} ({removed} nota(s))")
            self.sync._save_hashes()
            return
        if path.suffix.lower() not in CODE_EXTENSIONS:
            return
        note_path = self.sync._vault_path(path)
        if note_path.exists():
            note_path.unlink()
            print(f"[{ts()}] 🗑️  Removido: {note_path.name}")
        key = str(path)
        if key in self.sync.hashes:
            del self.sync.hashes[key]
            self.sync._save_hashes()

    def on_moved(self, event):
        if event.is_directory:
            return
        old = Path(event.src_path)
        old_note = self.sync._vault_path(old)
        if old_note.exists():
            old_note.unlink()
            print(f"[{ts()}] 🗑️  Removido (movido): {old_note.name}")
        if str(old) in self.sync.hashes:
            del self.sync.hashes[str(old)]
        self.sync.sync_single(Path(event.dest_path))

# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Sincronizador Projeto → Obsidian")
    parser.add_argument("--watch",  action="store_true",
                        help="Monitora mudanças em tempo real")
    parser.add_argument("--vault",  type=str, default=str(DEFAULT_VAULT),
                        help="Caminho do vault Obsidian")
    args = parser.parse_args()

    vault = Path(args.vault)
    sync  = VaultSync(vault)
    sync.sync_all()

    if args.watch:
        intervalo = 5
        print(f"👁️  Monitorando a cada {intervalo}s … (Ctrl+C para sair)\n")
        try:
            while True:
                for restante in range(intervalo, 0, -1):
                    print(f"\r  ⏱  Próxima sync em {restante}s…  ", end="", flush=True)
                    time.sleep(1)
                print(f"\r  🔄 Sincronizando agora…              ", flush=True)
                sync.sync_all()
        except KeyboardInterrupt:
            print("\n🛑 Monitor encerrado.")


if __name__ == "__main__":
    main()

```


==================================================
 ARQUIVO: .\simulador_interface.py
==================================================

```python
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

```


==================================================
 ARQUIVO: .\DADOS\apps_cache.json
==================================================

```text
{
    "adobe photoshop 2025": "D:\\adobe\\Adobe Photoshop 2025\\Photoshop.exe",
    "audacity": "C:\\Program Files\\Audacity\\Audacity.exe",
    "brave": "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    "chitubox": "C:\\Program Files\\CHITUBOX\\CHITUBOX.exe",
    "epic games launcher": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe",
    "firefox": "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
    "google chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "google drive": "C:\\Program Files\\Google\\Drive File Stream\\132.0.0.0\\GoogleDriveFS.exe",
    "microsoft edge": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "navegação privativa do firefox": "C:\\Program Files\\Mozilla Firefox\\private_browsing.exe",
    "notepad++": "C:\\Program Files\\Notepad++\\notepad++.exe",
    "onedrive": "C:\\Program Files\\Microsoft OneDrive\\OneDrive.exe",
    "tailscale": "C:\\Program Files\\Tailscale\\tailscale.exe",
    "teamviewer": "C:\\Program Files\\TeamViewer\\TeamViewer.exe",
    "techpowerup gpu-z": "C:\\Program Files (x86)\\GPU-Z\\GPU-Z.exe",
    "ultimaker cura 5.13.0": "C:\\Program Files\\UltiMaker Cura 5.13.0\\UltiMaker-Cura.exe",
    "vortex": "C:\\Program Files\\Vortex\\Vortex.exe",
    "wireshark": "C:\\Program Files\\Wireshark\\Wireshark.exe",
    "remote desktop connection": "C:\\WINDOWS\\system32\\mstsc.exe",
    "steps recorder": "C:\\WINDOWS\\system32\\psr.exe",
    "windows fax and scan": "C:\\WINDOWS\\system32\\WFS.exe",
    "character map": "C:\\WINDOWS\\system32\\charmap.exe",
    "dfrgui": "C:\\WINDOWS\\system32\\dfrgui.exe",
    "disk cleanup": "C:\\WINDOWS\\system32\\cleanmgr.exe",
    "iscsi initiator": "C:\\WINDOWS\\system32\\iscsicpl.exe",
    "memory diagnostics tool": "C:\\WINDOWS\\system32\\MdSched.exe",
    "odbc data sources (32-bit)": "C:\\WINDOWS\\syswow64\\odbcad32.exe",
    "odbc data sources (64-bit)": "C:\\WINDOWS\\system32\\odbcad32.exe",
    "recoverydrive": "C:\\WINDOWS\\system32\\RecoveryDrive.exe",
    "registry editor": "C:\\WINDOWS\\regedit.exe",
    "resource monitor": "C:\\WINDOWS\\system32\\perfmon.exe",
    "system configuration": "C:\\WINDOWS\\system32\\msconfig.exe",
    "system information": "C:\\WINDOWS\\system32\\msinfo32.exe",
    "airdroid": "C:\\Program Files (x86)\\AirDroid\\AirDroid.exe",
    "amd bug report tool": "C:\\Windows\\SysWOW64\\AMDBugReportTool.exe",
    "attack shark software": "C:\\Program Files (x86)\\Attack Shark Software\\AttackShark.exe",
    "cpu-z": "C:\\Program Files\\CPUID\\CPU-Z\\cpuz.exe",
    "hwmonitor": "C:\\Program Files\\CPUID\\HWMonitor\\HWMonitor.exe",
    "perfmonitor2": "C:\\Program Files\\CPUID\\PerfMonitor2\\PerfMonitor2.exe",
    "powermax": "C:\\Program Files\\CPUID\\powerMAX\\powerMAX.exe",
    "crystaldiskinfo": "C:\\Program Files\\CrystalDiskInfo\\DiskInfo64.exe",
    "crystaldiskmark 9": "C:\\Program Files\\CrystalDiskMark9\\DiskMark64.exe",
    "defraggler": "C:\\Program Files\\Defraggler\\Defraggler.exe",
    "app recovery": "C:\\Program Files\\Electronic Arts\\EA Desktop\\EA Desktop\\EALauncher.exe",
    "ea error reporter": "C:\\Program Files\\Electronic Arts\\EA Desktop\\EA Desktop\\ErrorReporter.exe",
    "aida64 extreme": "C:\\Program Files\\FinalWire\\AIDA64 Extreme\\aida64.exe",
    "git bash": "C:\\Program Files\\Git\\git-bash.exe",
    "configurar java": "C:\\Program Files\\Java\\jre1.8.0_503\\bin\\javacpl.exe",
    "sobre o java": "C:\\Program Files\\Java\\jre1.8.0_503\\bin\\javacpl.exe",
    "verificar atualizações": "C:\\Program Files\\Java\\jre1.8.0_503\\bin\\javacpl.exe",
    "mobadiff": "C:\\Program Files (x86)\\Mobatek\\MobaXterm\\MobaRTE.exe",
    "mobatexteditor": "C:\\Program Files (x86)\\Mobatek\\MobaXterm\\MobaRTE.exe",
    "mobaxterm": "C:\\Program Files (x86)\\Mobatek\\MobaXterm\\MobaXterm.exe",
    "node.js": "C:\\Program Files\\nodejs\\node.exe",
    "nvidia app": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\CEF\\NVIDIA App.exe",
    "nsight compute 2025.2.0": "C:\\Program Files\\NVIDIA Corporation\\Nsight Compute 2025.2.0\\host\\windows-desktop-win7-x64\\ncu-ui.exe",
    "nsight systems 2025.1.3": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2025.1.3\\host-windows-x64\\nsys-ui.exe",
    "nsight systems 2026.2.1": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\nsys-ui.exe",
    "nsight monitor": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Nsight.Monitor.exe",
    "frameview": "C:\\Program Files\\NVIDIA Corporation\\FrameView\\FrameView_x64.exe",
    "oracle virtualbox": "C:\\Program Files\\Oracle\\VirtualBox\\VirtualBox.exe",
    "pcsx2": "C:\\Program Files\\PCSX2\\pcsx2-qt.exe",
    "peace": "C:\\Program Files\\EqualizerAPO\\config\\Peace.exe",
    "application stack builder": "C:\\Program Files\\PostgreSQL\\18\\bin\\stackbuilder.exe",
    "pgadmin 4": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pgAdmin4.exe",
    "reload configuration": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_ctl.exe",
    "pageant": "C:\\Program Files\\PuTTY\\pageant.exe",
    "psftp": "C:\\Program Files\\PuTTY\\psftp.exe",
    "putty": "C:\\Program Files\\PuTTY\\putty.exe",
    "puttygen": "C:\\Program Files\\PuTTY\\puttygen.exe",
    "qbittorrent": "C:\\Program Files\\qBittorrent\\qbittorrent.exe",
    "raspberry pi imager": "C:\\Program Files\\Raspberry Pi Ltd\\Imager\\rpi-imager.exe",
    "rsi launcher": "C:\\Program Files\\Roberts Space Industries\\RSI Launcher\\RSI Launcher.exe",
    "rustdesk": "C:\\Program Files\\RustDesk\\RustDesk.exe",
    "steam": "C:\\Program Files (x86)\\Steam\\steam.exe",
    "task manager": "C:\\WINDOWS\\system32\\taskmgr.exe",
    "tlauncher": "C:\\Users\\felip\\AppData\\Roaming\\.minecraft\\TLauncher.exe",
    "voicemod": "C:\\Program Files\\Voicemod V3\\Voicemod.exe",
    "windows powershell ise (x86)": "C:\\WINDOWS\\syswow64\\WindowsPowerShell\\v1.0\\PowerShell_ISE.exe",
    "windows powershell ise": "C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\PowerShell_ISE.exe",
    "winrar": "C:\\Program Files\\WinRAR\\WinRAR.exe",
    "wise data recovery": "C:\\Program Files (x86)\\Wise\\Wise Data Recovery\\WiseDataRecovery.exe",
    "wise force deleter": "C:\\Program Files (x86)\\Wise\\Wise Force Deleter\\WiseDeleter.exe",
    "wise memory optimizer": "C:\\Program Files\\Wise\\Wise Memory Optimizer\\WiseMemoryOptimzer.exe",
    "administrative tools": "C:\\WINDOWS\\system32\\control.exe",
    "antigravity": "C:\\Users\\felip\\AppData\\Local\\Programs\\Antigravity\\Antigravity.exe",
    "arduino ide": "C:\\Users\\felip\\AppData\\Local\\Programs\\Arduino IDE\\Arduino IDE.exe",
    "artcraft launcher": "C:\\Users\\felip\\AppData\\Local\\Programs\\ArtCraft Launcher\\artcraft-launcher.exe",
    "discord": "C:\\Users\\felip\\AppData\\Local\\Discord\\app-1.0.9261\\Discord.exe",
    "docker desktop": "C:\\Program Files\\Docker\\Docker\\resources\\Docker desktop.exe",
    "drive beyond horizons": "C:\\Users\\felip\\AppData\\Local\\Programs\\Hydra\\Hydra.exe",
    "femboy futa house": "C:\\Users\\felip\\AppData\\Local\\Programs\\Hydra\\Hydra.exe",
    "gemini": "C:\\Users\\felip\\AppData\\Local\\Google\\Gemini\\Gemini.exe",
    "hydra": "C:\\Users\\felip\\AppData\\Local\\Programs\\Hydra\\Hydra.exe",
    "lightyear frontier": "C:\\Users\\felip\\AppData\\Local\\Programs\\Hydra\\Hydra.exe",
    "navegador opera gx": "C:\\Users\\felip\\AppData\\Local\\Programs\\Opera GX\\opera.exe",
    "nvidia geforce now": "C:\\Users\\felip\\AppData\\Local\\NVIDIA Corporation\\GeForceNOW\\CEF\\GeForceNOW.exe",
    "obsidian": "C:\\Users\\felip\\AppData\\Local\\Programs\\Obsidian\\Obsidian.exe",
    "ollama": "C:\\Users\\felip\\AppData\\Local\\Programs\\Ollama\\ollama app.exe",
    "pinokio": "C:\\Users\\felip\\AppData\\Local\\Programs\\Pinokio\\Pinokio.exe",
    "sapphire safari": "C:\\Users\\felip\\AppData\\Local\\Programs\\Hydra\\Hydra.exe",
    "satisfactory mod manager": "C:\\Users\\felip\\AppData\\Local\\Programs\\Satisfactory Mod Manager\\Satisfactory Mod Manager.exe",
    "livecaptions": "C:\\WINDOWS\\system32\\LiveCaptions.exe",
    "magnify": "C:\\WINDOWS\\system32\\magnify.exe",
    "narrator": "C:\\WINDOWS\\system32\\narrator.exe",
    "on-screen keyboard": "C:\\WINDOWS\\system32\\osk.exe",
    "voiceaccess": "C:\\WINDOWS\\system32\\voiceaccess.exe",
    "claude": "C:\\Users\\felip\\AppData\\Local\\AnthropicClaude\\claude.exe",
    "antigravity ide": "C:\\Users\\felip\\AppData\\Local\\Programs\\Antigravity IDE\\Antigravity IDE.exe",
    "huggingface": "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
    "nexusmods users": "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
    "autodesk fusion": "C:\\Users\\felip\\AppData\\Local\\Autodesk\\webdeploy\\production\\6a0c9611291d45bb9226980209917c3d\\FusionLauncher.exe",
    "benchmark": "C:\\Program Files\\EqualizerAPO\\Benchmark.exe",
    "equalizer apo configuration editor": "C:\\Program Files\\EqualizerAPO\\Editor.exe",
    "equalizer apo device selector": "C:\\Program Files\\EqualizerAPO\\DeviceSelector.exe",
    "dark souls iii (me3)": "C:\\Users\\felip\\AppData\\Local\\Programs\\garyttierney\\me3\\bin\\me3.exe",
    "elden ring (me3)": "C:\\Users\\felip\\AppData\\Local\\Programs\\garyttierney\\me3\\bin\\me3.exe",
    "nightreign (me3)": "C:\\Users\\felip\\AppData\\Local\\Programs\\garyttierney\\me3\\bin\\me3.exe",
    "sekiro (me3)": "C:\\Users\\felip\\AppData\\Local\\Programs\\garyttierney\\me3\\bin\\me3.exe",
    "msys2 clang64": "C:\\msys64\\clang64.exe",
    "msys2 clangarm64": "C:\\msys64\\clangarm64.exe",
    "msys2 mingw64": "C:\\msys64\\mingw64.exe",
    "msys2 msys": "C:\\msys64\\msys2.exe",
    "msys2 ucrt64": "C:\\msys64\\ucrt64.exe",
    "openclaw chat": "C:\\Users\\felip\\AppData\\Local\\OpenClawTray\\OpenClaw.Tray.WinUI.exe",
    "openclaw companion settings": "C:\\Users\\felip\\AppData\\Local\\OpenClawTray\\OpenClaw.Tray.WinUI.exe",
    "openclaw companion": "C:\\Users\\felip\\AppData\\Local\\OpenClawTray\\OpenClaw.Tray.WinUI.exe",
    "postman": "C:\\Users\\felip\\AppData\\Local\\Postman\\Postman.exe",
    "idle (python 3.11 64-bit)": "C:\\Users\\felip\\AppData\\Local\\Programs\\Python\\Python311\\pythonw.exe",
    "python 3.11 (64-bit)": "C:\\Users\\felip\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
    "python 3.11 module docs (64-bit)": "C:\\Users\\felip\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
    "roblox player": "C:\\Users\\felip\\AppData\\Local\\Roblox\\Versions\\version-cec3ad5889b447cf\\RobloxPlayerBeta.exe",
    "roblox studio": "C:\\Users\\felip\\AppData\\Local\\Roblox\\Versions\\version-d679641ad17741aa\\RobloxStudioBeta.exe",
    "sox": "C:\\Program Files (x86)\\sox-14-4-2\\sox.exe",
    "wget": "C:\\Program Files (x86)\\sox-14-4-2\\wget.exe",
    "ubisoft connect": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe",
    "visual studio code": "C:\\Users\\felip\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
    "windows powershell (x86)": "C:\\Windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe",
    "windows powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    "photoshop - atalho": "D:\\adobe\\Adobe Photoshop 2025\\Photoshop.exe",
    "spacesniffer - atalho": "C:\\Users\\felip\\Desktop\\app dia dia\\SpaceSniffer.exe",
    "cpuid cpu-z": "C:\\Program Files\\CPUID\\CPU-Z\\cpuz.exe",
    "crystaldiskmark8_0_5": "C:\\Users\\felip\\Desktop\\app dia dia\\CrystalDiskMark8_0_5.exe",
    "equalizerapo64-1.2.1": "C:\\Users\\felip\\Desktop\\app dia dia\\EqualizerAPO64-1.2.1.exe",
    "nvidia": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\CEF\\NVIDIA App.exe",
    "pgadmin4-9.3-x64": "C:\\Users\\felip\\Desktop\\app dia dia\\pgadmin4-9.3-x64.exe",
    "putty - atalho": "C:\\Program Files\\PuTTY\\putty.exe",
    "spacesniffer": "C:\\Users\\felip\\Desktop\\app dia dia\\SpaceSniffer.exe",
    "tinytask": "C:\\Users\\felip\\Desktop\\app dia dia\\tinytask.exe",
    "ultimaker-cura-5.9.0-win64-x64": "C:\\Users\\felip\\Desktop\\app dia dia\\UltiMaker-Cura-5.9.0-win64-X64.exe",
    "wise disk cleaner": "C:\\Program Files (x86)\\Wise\\Wise Disk Cleaner\\WiseDiskCleaner.exe",
    "ffmpeg": "C:\\Program Files (x86)\\AirDroid\\IncludeAdb\\ffmpeg.exe",
    "ffplay": "C:\\Users\\felip\\Desktop\\app dia dia\\BAIXA VIDEOS\\ffmpeg-8.0.1-essentials_build\\bin\\ffplay.exe",
    "ffprobe": "C:\\Users\\felip\\Desktop\\app dia dia\\BAIXA VIDEOS\\ffmpeg-8.0.1-essentials_build\\bin\\ffprobe.exe",
    "yt-dlp": "C:\\Users\\felip\\Desktop\\app dia dia\\BAIXA VIDEOS\\ffmpeg-8.0.1-essentials_build\\bin\\yt-dlp.exe",
    "diskinfo32": "C:\\Users\\felip\\Desktop\\app dia dia\\Nova pasta\\DiskInfo32.exe",
    "diskinfo64": "C:\\Program Files\\CrystalDiskInfo\\DiskInfo64.exe",
    "diskinfoa64": "C:\\Users\\felip\\Desktop\\app dia dia\\Nova pasta\\DiskInfoA64.exe",
    "alertmail": "C:\\Program Files\\CrystalDiskInfo\\CdiResource\\AlertMail.exe",
    "alertmail4": "C:\\Program Files\\CrystalDiskInfo\\CdiResource\\AlertMail4.exe",
    "alertmail48": "C:\\Program Files\\CrystalDiskInfo\\CdiResource\\AlertMail48.exe",
    "opusdec": "C:\\Program Files\\CrystalDiskInfo\\CdiResource\\opus\\opusdec.exe",
    "officedeploymenttool_17830-20162": "C:\\Users\\felip\\Desktop\\app dia dia\\Office 2024 tutorial de baixar\\officedeploymenttool_17830-20162.exe",
    "python-3.11.8-amd64": "C:\\Users\\felip\\Desktop\\app dia dia\\progamaçoa\\python-3.11.8-amd64.exe",
    "virtualbox-7.0.14-161095-win": "C:\\Users\\felip\\Desktop\\app dia dia\\progamaçoa\\VirtualBox-7.0.14-161095-Win.exe",
    "robloxmulti": "C:\\Users\\felip\\Desktop\\app dia dia\\RobloxMulti\\bin\\RobloxMulti.exe",
    "wisememoryoptimzer": "C:\\Program Files\\Wise\\Wise Memory Optimizer\\WiseMemoryOptimzer.exe",
    "equalizerapo-x64-1.4.2": "C:\\Users\\felip\\Desktop\\Aruma microfone\\EqualizerAPO-x64-1.4.2.exe",
    "librehardwaremonitor": "C:\\Users\\felip\\Desktop\\bachupa meu modelo\\BETA\\monitor\\LibreHardwareMonitor.exe",
    "git-bash": "C:\\Program Files\\Git\\git-bash.exe",
    "bash": "C:\\Program Files\\Git\\bin\\bash.exe",
    "git": "C:\\Program Files\\Git\\cmd\\git.exe",
    "git-gui": "C:\\Program Files\\Git\\cmd\\git-gui.exe",
    "git-receive-pack": "C:\\Program Files\\Git\\cmd\\git-receive-pack.exe",
    "git-upload-pack": "C:\\Program Files\\Git\\cmd\\git-upload-pack.exe",
    "gitk": "C:\\Program Files\\Git\\cmd\\gitk.exe",
    "scalar": "C:\\Program Files\\Git\\cmd\\scalar.exe",
    "tig": "C:\\Program Files\\Git\\cmd\\tig.exe",
    "python": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\python\\python.exe",
    "pythonw": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\python\\pythonw.exe",
    "bzip2": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\bzip2.exe",
    "bzip2recover": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\bzip2recover.exe",
    "lzmadec": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\lzmadec.exe",
    "lzmainfo": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\lzmainfo.exe",
    "openssl": "C:\\Program Files\\CHITUBOX\\openssl.exe",
    "sqlite3": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\sqlite3.exe",
    "tclsh": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\tclsh.exe",
    "tclsh86": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\tclsh86.exe",
    "tclsh86t": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\tclsh86t.exe",
    "wish": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\wish.exe",
    "wish86": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\wish86.exe",
    "wish86t": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\wish86t.exe",
    "xzdec": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\bin\\xzdec.exe",
    "x86_64-w64-mingw32-nmakehlp": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Library\\lib\\nmake\\x86_64-w64-mingw32-nmakehlp.exe",
    "2to3": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\2to3.exe",
    "cffi-gen-src": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\cffi-gen-src.exe",
    "ct2-fairseq-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-fairseq-converter.exe",
    "ct2-marian-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-marian-converter.exe",
    "ct2-openai-gpt2-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-openai-gpt2-converter.exe",
    "ct2-opennmt-py-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-opennmt-py-converter.exe",
    "ct2-opennmt-tf-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-opennmt-tf-converter.exe",
    "ct2-opus-mt-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-opus-mt-converter.exe",
    "ct2-transformers-converter": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\ct2-transformers-converter.exe",
    "dashscope": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\dashscope.exe",
    "distro": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\distro.exe",
    "dotenv": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\dotenv.exe",
    "edge-playback": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\edge-playback.exe",
    "edge-tts": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\edge-tts.exe",
    "f2py": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\f2py.exe",
    "fastapi": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\fastapi.exe",
    "httpx": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\httpx.exe",
    "idle": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\idle.exe",
    "idna": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\idna.exe",
    "imageio_download_bin": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\imageio_download_bin.exe",
    "imageio_remove_bin": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\imageio_remove_bin.exe",
    "jsonschema": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\jsonschema.exe",
    "litellm": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\litellm.exe",
    "normalizer": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\normalizer.exe",
    "numpy-config": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\numpy-config.exe",
    "onnxruntime_test": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\onnxruntime_test.exe",
    "openai": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\openai.exe",
    "pip": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\pip.exe",
    "pip3": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\python\\Scripts\\pip3.exe",
    "pyav": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\pyav.exe",
    "pydoc": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\pydoc.exe",
    "streamlit": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\streamlit.exe",
    "tabulate": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\tabulate.exe",
    "tqdm": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\tqdm.exe",
    "uvicorn": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\uvicorn.exe",
    "watchmedo": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\watchmedo.exe",
    "websockets": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\websockets.exe",
    "wheel": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\wheel.exe",
    "wsdump": "C:\\Users\\felip\\Desktop\\CANAL AFK\\TESTE MONEY\\lib\\python\\Scripts\\wsdump.exe",
    "me3_manager - atalho": "D:\\tudo\\MOD DUBLAGUE\\Me3_Manager_1.1.8\\Me3_Manager.exe",
    "deploytool": "C:\\Program Files (x86)\\Acer\\Care Center\\DeployTool.exe",
    "listcheck": "C:\\Program Files (x86)\\Acer\\Care Center\\ListCheck.exe",
    "pscreatedefaultprofile": "C:\\Program Files\\Acer\\NitroSense Service\\PSCreateDefaultProfile.exe",
    "pslauncher": "C:\\Program Files\\Acer\\NitroSense Service\\PSLauncher.exe",
    "pssvc": "C:\\Program Files\\Acer\\NitroSense Service\\PSSvc.exe",
    "pstoastcreator": "C:\\Program Files\\Acer\\NitroSense Service\\PSToastCreator.exe",
    "upgradetool": "C:\\Program Files (x86)\\Acer\\Care Center\\UpgradeTool.exe",
    "ccxprocess": "C:\\Program Files (x86)\\Adobe\\Adobe Creative Cloud Experience\\CCXProcess.exe",
    "node": "C:\\Program Files\\nodejs\\node.exe",
    "amdcleanuputility": "C:\\Program Files\\AMD\\CIM\\Bin64\\AMDCleanupUtility.exe",
    "amdinstalluep": "C:\\Program Files\\AMD\\InstallUEP\\AMDInstallUEP.exe",
    "amdsplashscreen": "C:\\Program Files\\AMD\\CIM\\Bin64\\AMDSplashScreen.exe",
    "installmanagerapp": "C:\\Program Files\\AMD\\CIM\\Bin64\\InstallManagerApp.exe",
    "amddmlfilters": "C:\\Program Files\\AMD\\CNext\\CNext\\amddmlfilters.exe",
    "amdgameconfigserv": "C:\\Program Files\\AMD\\CNext\\CNext\\AMDGameConfigServ.exe",
    "amdidentifywindow": "C:\\Program Files\\AMD\\CNext\\CNext\\AMDIdentifyWindow.exe",
    "amdow": "C:\\Program Files\\AMD\\CNext\\CNext\\amdow.exe",
    "amdrsserv": "C:\\Program Files\\AMD\\CNext\\CNext\\AMDRSServ.exe",
    "amdrssrcext": "C:\\Program Files\\AMD\\CNext\\CNext\\AMDRSSrcExt.exe",
    "compressionutility": "C:\\Program Files\\AMD\\CNext\\CNext\\CompressionUtility.exe",
    "cpumetricsserver": "C:\\Program Files\\AMD\\CNext\\CNext\\CPUMetricsServer.exe",
    "duplicatedesktop": "C:\\Program Files\\AMD\\CNext\\CNext\\DuplicateDesktop.exe",
    "eyefinitypro": "C:\\Program Files\\AMD\\CNext\\CNext\\EyefinityPro.exe",
    "gpuup": "C:\\Program Files\\AMD\\CNext\\CNext\\gpuup.exe",
    "launcherrsxruntime": "C:\\Program Files\\AMD\\CNext\\CNext\\LauncherRSXRuntime.exe",
    "mmloaddrv": "C:\\Program Files\\AMD\\CNext\\CNext\\MMLoadDrv.exe",
    "mmloaddrvpxdiscrete": "C:\\Program Files\\AMD\\CNext\\CNext\\MMLoadDrvPXDiscrete.exe",
    "presentmon-x64": "C:\\Program Files\\AMD\\CNext\\CNext\\PresentMon-x64.exe",
    "qtwebengineprocess": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\QtWebEngineProcess.exe",
    "radeonsoftware": "C:\\Program Files\\AMD\\CNext\\CNext\\RadeonSoftware.exe",
    "videotrim": "C:\\Program Files\\AMD\\CNext\\CNext\\videotrim.exe",
    "ziputility": "C:\\Program Files\\AMD\\CNext\\CNext\\ZipUtility.exe",
    "gfycatwrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\Gfycat\\GfycatWrapper.exe",
    "giphywrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\giphy\\GiphyWrapper.exe",
    "restreamapiwrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\restream\\RestreamAPIWrapper.exe",
    "sinaweibowrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\sinaWeibo\\SinaWeiboWrapper.exe",
    "streamableapiwrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\streamable\\StreamableAPIWrapper.exe",
    "youtubeapiwrapper": "C:\\Program Files\\AMD\\CNext\\CNext\\youtube\\YoutubeAPIWrapper.exe",
    "chrome_pwa_launcher": "C:\\Program Files\\Google\\Chrome\\Application\\155.0.8059.40\\chrome_pwa_launcher.exe",
    "cadexhost": "C:\\Program Files\\CHITUBOX\\CadExHost.exe",
    "consolerender": "C:\\Program Files\\CHITUBOX\\ConsoleRender.exe",
    "licensingtool": "C:\\Program Files\\CHITUBOX\\LicensingTool.exe",
    "cpuz": "C:\\Program Files\\CPUID\\CPU-Z\\cpuz.exe",
    "diskmark64": "C:\\Program Files\\CrystalDiskMark9\\DiskMark64.exe",
    "diskspd64": "C:\\Program Files\\CrystalDiskMark9\\CdmResource\\DiskSpd\\DiskSpd64.exe",
    "diskspd64l": "C:\\Program Files\\CrystalDiskMark9\\CdmResource\\DiskSpd\\DiskSpd64L.exe",
    "defraggler64": "C:\\Program Files\\Defraggler\\Defraggler64.exe",
    "df64": "C:\\Program Files\\Defraggler\\df64.exe",
    "docker-ai": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-ai.exe",
    "docker-buildx": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-buildx.exe",
    "docker-compose": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-compose.exe",
    "docker-debug": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-debug.exe",
    "docker-desktop": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-desktop.exe",
    "docker-dhi": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-dhi.exe",
    "docker-extension": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-extension.exe",
    "docker-init": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-init.exe",
    "docker-mcp": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-mcp.exe",
    "docker-model": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-model.exe",
    "docker-offload": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-offload.exe",
    "docker-pass": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-pass.exe",
    "docker-sandbox": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-sandbox.exe",
    "docker-scout": "C:\\Program Files\\Docker\\Docker\\resources\\cli-plugins\\docker-scout.exe",
    "7zr": "C:\\Program Files\\Docker\\Docker\\7zr.exe",
    "courgette64": "C:\\Program Files\\Docker\\Docker\\courgette64.exe",
    "buildkitd": "C:\\Program Files\\Docker\\Docker\\resources\\buildkitd.exe",
    "com.docker.admin": "C:\\Program Files\\Docker\\Docker\\resources\\com.docker.admin.exe",
    "com.docker.backend": "C:\\Program Files\\Docker\\Docker\\resources\\com.docker.backend.exe",
    "com.docker.build": "C:\\Program Files\\Docker\\Docker\\resources\\com.docker.build.exe",
    "com.docker.diagnose": "C:\\Program Files\\Docker\\Docker\\resources\\com.docker.diagnose.exe",
    "containerd-shim-runhcs-v1": "C:\\Program Files\\Docker\\Docker\\resources\\containerd-shim-runhcs-v1.exe",
    "containerd": "C:\\Program Files\\Docker\\Docker\\resources\\containerd.exe",
    "dockerd": "C:\\Program Files\\Docker\\Docker\\resources\\dockerd.exe",
    "com.docker.llama-server": "C:\\Program Files\\Docker\\Docker\\resources\\model-runner\\bin\\com.docker.llama-server.exe",
    "com.docker.nv-gpu-info": "C:\\Program Files\\Docker\\Docker\\resources\\model-runner\\bin\\com.docker.nv-gpu-info.exe",
    "dotnet": "C:\\Program Files\\dotnet\\dotnet.exe",
    "apphost": "C:\\Program Files\\dotnet\\packs\\Microsoft.NETCore.App.Host.win-x86\\7.0.20\\runtimes\\win-x86\\native\\apphost.exe",
    "singlefilehost": "C:\\Program Files\\dotnet\\packs\\Microsoft.NETCore.App.Host.win-x86\\7.0.20\\runtimes\\win-x86\\native\\singlefilehost.exe",
    "createdump": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\People Playground\\ppgModCompiler\\createdump.exe",
    "eadestager": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\Destager\\EADestager.exe",
    "eacefsubprocess": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\EACefSubProcess.exe",
    "eaconnect_microsoft": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\EAConnect_microsoft.exe",
    "eadesktop": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\compatibility32\\EADesktop.exe",
    "eagep": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\EAGEP.exe",
    "ealauncher": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\EALauncher.exe",
    "ealocalhostsvc": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\EALocalHostSvc.exe",
    "errorreporter": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\ErrorReporter.exe",
    "getgametoken": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\GetGameToken.exe",
    "link2ea": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\Link2EA.exe",
    "originlegacycompatibility": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\OriginLegacyCompatibility.exe",
    "eacoreserver": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\legacyPM\\EACoreServer.exe",
    "login": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\legacyPM\\Login.exe",
    "messagedlg": "C:\\Program Files\\Electronic Arts\\EA Desktop\\13.671.0.6184-1774651275\\EA Desktop\\legacyPM\\MessageDlg.exe",
    "dredge": "C:\\Program Files\\Epic Games\\DREDGEmKMzx\\DREDGE.exe",
    "eosbootstrapper": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Extras\\EOSBootStrapper\\EOSBootStrapper.exe",
    "idj": "C:\\Program Files\\Epic Games\\IDJ\\IDJ.exe",
    "deviceselector": "C:\\Program Files\\EqualizerAPO\\DeviceSelector.exe",
    "editor": "C:\\Program Files\\EqualizerAPO\\Editor.exe",
    "filmcraft": "C:\\Program Files\\FilmCraft\\filmcraft.exe",
    "aida64": "C:\\Program Files\\FinalWire\\AIDA64 Extreme\\aida64.exe",
    "git-lfs": "C:\\Program Files\\Git\\cmd\\git-lfs.exe",
    "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "account_export_tool": "C:\\Program Files\\Google\\Drive File Stream\\account_export_tool.exe",
    "dfd_mcp_server": "C:\\Program Files\\Google\\Drive File Stream\\dfd_mcp_server.exe",
    "diagnostic_tool": "C:\\Program Files\\Google\\Drive File Stream\\diagnostic_tool.exe",
    "googledrivefs": "C:\\Program Files\\Google\\Drive File Stream\\132.0.0.0\\GoogleDriveFS.exe",
    "switchblade_host": "C:\\Program Files\\Google\\Drive File Stream\\132.0.0.0\\switchblade_host.exe",
    "gridcraft": "C:\\Program Files\\GridCraft\\gridcraft.exe",
    "extexport": "C:\\Program Files (x86)\\Internet Explorer\\ExtExport.exe",
    "ieinstal": "C:\\Program Files (x86)\\Internet Explorer\\ieinstal.exe",
    "ielowutil": "C:\\Program Files (x86)\\Internet Explorer\\ielowutil.exe",
    "iexplore": "C:\\Program Files (x86)\\Internet Explorer\\iexplore.exe",
    "jabswitch": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\jabswitch.exe",
    "jaccessinspector": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jaccessinspector.exe",
    "jaccesswalker": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jaccesswalker.exe",
    "jar": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jar.exe",
    "jarsigner": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jarsigner.exe",
    "java": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\java.exe",
    "javac": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\javac.exe",
    "javadoc": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\javadoc.exe",
    "javap": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\javap.exe",
    "javaw": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\javaw.exe",
    "jconsole": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jconsole.exe",
    "jdb": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jdb.exe",
    "jdeprscan": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jdeprscan.exe",
    "jdeps": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jdeps.exe",
    "jfr": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jfr.exe",
    "jhsdb": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jhsdb.exe",
    "jimage": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jimage.exe",
    "jinfo": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jinfo.exe",
    "jlink": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jlink.exe",
    "jmap": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jmap.exe",
    "jmod": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jmod.exe",
    "jnativescan": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jnativescan.exe",
    "jpackage": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jpackage.exe",
    "jps": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jps.exe",
    "jrunscript": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jrunscript.exe",
    "jshell": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jshell.exe",
    "jstack": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jstack.exe",
    "jstat": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jstat.exe",
    "jstatd": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jstatd.exe",
    "jwebserver": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\jwebserver.exe",
    "keytool": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\keytool.exe",
    "kinit": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\python\\kinit.exe",
    "klist": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\klist.exe",
    "ktab": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\ktab.exe",
    "rmiregistry": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\rmiregistry.exe",
    "serialver": "C:\\Program Files\\Java\\latest\\jdk-25\\bin\\serialver.exe",
    "java-rmi": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\java-rmi.exe",
    "javacpl": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\javacpl.exe",
    "javaws": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\javaws.exe",
    "jjs": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\jjs.exe",
    "jp2launcher": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\jp2launcher.exe",
    "orbd": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\orbd.exe",
    "pack200": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\pack200.exe",
    "policytool": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\policytool.exe",
    "rmid": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\rmid.exe",
    "servertool": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\servertool.exe",
    "tnameserv": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\tnameserv.exe",
    "unpack200": "C:\\Program Files\\Java\\latest\\jre-1.8\\bin\\unpack200.exe",
    "sqldumper": "C:\\Program Files (x86)\\Microsoft Analysis Services\\AS OLEDB\\110\\SQLDumper.exe",
    "appsharinghookcontroller64": "C:\\Program Files\\Microsoft Office\\Office16\\AppSharingHookController64.exe",
    "excelcnv": "C:\\Program Files\\Microsoft Office\\Office16\\excelcnv.exe",
    "lync": "C:\\Program Files\\Microsoft Office\\Office16\\lync.exe",
    "lync99": "C:\\Program Files\\Microsoft Office\\Office16\\lync99.exe",
    "lynchtmlconv": "C:\\Program Files\\Microsoft Office\\Office16\\lynchtmlconv.exe",
    "misc": "C:\\Program Files\\Microsoft Office\\Office16\\misc.exe",
    "msoev": "C:\\Program Files\\Microsoft Office\\Office16\\msoev.exe",
    "msoia": "C:\\Program Files\\Microsoft Office\\Office16\\msoia.exe",
    "msotd": "C:\\Program Files\\Microsoft Office\\Office16\\msotd.exe",
    "ocpubmgr": "C:\\Program Files\\Microsoft Office\\Office16\\OcPubMgr.exe",
    "protocolhandler": "C:\\Program Files\\Microsoft Office\\Office16\\protocolhandler.exe",
    "ucmapi": "C:\\Program Files\\Microsoft Office\\Office16\\UcMapi.exe",
    "wordconv": "C:\\Program Files\\Microsoft Office\\Office16\\Wordconv.exe",
    "microsoft.mashup.container": "C:\\Program Files\\Microsoft Office\\Office16\\ADDINS\\Microsoft Power Query for Excel Integrated\\bin\\Microsoft.Mashup.Container.exe",
    "microsoft.mashup.container.netfx40": "C:\\Program Files\\Microsoft Office\\Office16\\ADDINS\\Microsoft Power Query for Excel Integrated\\bin\\Microsoft.Mashup.Container.NetFX40.exe",
    "microsoft.mashup.container.netfx45": "C:\\Program Files\\Microsoft Office\\Office16\\ADDINS\\Microsoft Power Query for Excel Integrated\\bin\\Microsoft.Mashup.Container.NetFX45.exe",
    "onedrive.app": "C:\\Program Files\\Microsoft OneDrive\\OneDrive.App.exe",
    "filecoauth": "C:\\Program Files\\Microsoft OneDrive\\26.178.0913.0007\\FileCoAuth.exe",
    "filesyncconfig": "C:\\Program Files\\Microsoft OneDrive\\26.178.0913.0007\\FileSyncConfig.exe",
    "onedrivefilelauncher": "C:\\Program Files\\Microsoft OneDrive\\26.178.0913.0007\\OneDriveFileLauncher.exe",
    "onedrivelauncher": "C:\\Program Files\\Microsoft OneDrive\\26.178.0913.0007\\OneDriveLauncher.exe",
    "sqlservr": "C:\\Program Files\\Microsoft SQL Server\\170\\LocalDB\\Binn\\sqlservr.exe",
    "sqllocaldb": "C:\\Program Files\\Microsoft SQL Server\\170\\Tools\\Binn\\SqlLocalDB.exe",
    "sqlwriter": "C:\\Program Files\\Microsoft SQL Server\\90\\Shared\\sqlwriter.exe",
    "pingsender": "C:\\Program Files\\Mozilla Firefox\\pingsender.exe",
    "plugin-container": "C:\\Program Files\\Mozilla Firefox\\plugin-container.exe",
    "private_browsing": "C:\\Program Files\\Mozilla Firefox\\private_browsing.exe",
    "desktop-launcher": "C:\\Program Files\\Mozilla Firefox\\desktop-launcher\\desktop-launcher.exe",
    "gup": "C:\\Program Files\\Notepad++\\updater\\GUP.exe",
    "npfinstall": "C:\\Program Files\\Npcap\\NPFInstall.exe",
    "frameview_x64": "C:\\Program Files\\NVIDIA Corporation\\FrameView\\FrameView_x64.exe",
    "enablevroverlay_x64": "C:\\Program Files\\NVIDIA Corporation\\FrameView\\bin\\EnableVROverlay_x64.exe",
    "fv_unit_test_cpu_gpu_metrics": "C:\\Program Files\\NVIDIA Corporation\\FrameView\\bin\\FV_Unit_Test_CPU_GPU_Metrics.exe",
    "presentmon_x64": "C:\\Program Files\\NVIDIA Corporation\\FrameView\\bin\\PresentMon_x64.exe",
    "cudagpuinfodumper": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\CudaGpuInfoDumper.exe",
    "nsys": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\nsys.exe",
    "ncu-ui": "C:\\Program Files\\NVIDIA Corporation\\Nsight Compute 2025.2.0\\host\\windows-desktop-win7-x64\\ncu-ui.exe",
    "qdstrmimporter": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\QdstrmImporter.exe",
    "ncu": "C:\\Program Files\\NVIDIA Corporation\\Nsight Compute 2025.2.0\\target\\windows-desktop-win7-x64\\ncu.exe",
    "dumptimeline": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\DumpTimeline.exe",
    "importnvtxt": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\ImportNvtxt.exe",
    "nsys-ui": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\nsys-ui.exe",
    "resolvesymbols": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\host-windows-x64\\ResolveSymbols.exe",
    "venvlauncher": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\python\\bin\\venvlauncher.exe",
    "pip3.12": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\python\\Scripts\\pip3.12.exe",
    "nvml_plugin": "C:\\Program Files\\NVIDIA Corporation\\Nsight Systems 2026.2.1\\target-windows-x64\\plugins\\nvml_metrics\\nvml_plugin.exe",
    "nvcontainer": "C:\\Program Files\\NVIDIA Corporation\\NvContainer\\nvcontainer.exe",
    "darkmodecheck": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\DarkModeCheck.exe",
    "nvidia overlay": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\CEF\\NVIDIA Overlay.exe",
    "nvidia app permission": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\CEF\\NvidiaAppPermissionOc\\NVIDIA App Permission.exe",
    "nvoawrappercache": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\NvBackend\\ApplicationOntology\\NvOAWrapperCache.exe",
    "oawrapper": "C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\NvBackend\\ApplicationOntology\\OAWrapper.exe",
    "vboxaudiotest": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxAudioTest.exe",
    "vboxautostartsvc": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxAutostartSvc.exe",
    "vboxballoonctrl": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxBalloonCtrl.exe",
    "vboxbugreport": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxBugReport.exe",
    "vboxdrvinst": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxDrvInst.exe",
    "vboxdtrace": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxDTrace.exe",
    "vboxheadless": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxHeadless.exe",
    "vboxmanage": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe",
    "vboxnetdhcp": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxNetDHCP.exe",
    "vboxnetnat": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxNetNAT.exe",
    "vboxsds": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxSDS.exe",
    "vboxsvc": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxSVC.exe",
    "vboxwebsrv": "C:\\Program Files\\Oracle\\VirtualBox\\VBoxWebSrv.exe",
    "virtualbox": "C:\\Program Files\\Oracle\\VirtualBox\\VirtualBox.exe",
    "virtualboxvm": "C:\\Program Files\\Oracle\\VirtualBox\\VirtualBoxVM.exe",
    "os2_util": "C:\\Program Files\\Oracle\\VirtualBox\\UnattendedTemplates\\os2_util.exe",
    "pawnioutil": "C:\\Program Files\\PawnIO\\PawnIOUtil.exe",
    "pcsx2-qt": "C:\\Program Files\\PCSX2\\pcsx2-qt.exe",
    "photocraft": "C:\\Program Files\\PhotoCraft\\photocraft.exe",
    "clusterdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\clusterdb.exe",
    "createdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\createdb.exe",
    "createuser": "C:\\Program Files\\PostgreSQL\\18\\bin\\createuser.exe",
    "dropdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\dropdb.exe",
    "dropuser": "C:\\Program Files\\PostgreSQL\\18\\bin\\dropuser.exe",
    "ecpg": "C:\\Program Files\\PostgreSQL\\18\\bin\\ecpg.exe",
    "initdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\initdb.exe",
    "oid2name": "C:\\Program Files\\PostgreSQL\\18\\bin\\oid2name.exe",
    "pgbench": "C:\\Program Files\\PostgreSQL\\18\\bin\\pgbench.exe",
    "pg_amcheck": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_amcheck.exe",
    "pg_archivecleanup": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_archivecleanup.exe",
    "pg_basebackup": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_basebackup.exe",
    "pg_checksums": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_checksums.exe",
    "pg_combinebackup": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_combinebackup.exe",
    "pg_config": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_config.exe",
    "pg_controldata": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_controldata.exe",
    "pg_createsubscriber": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_createsubscriber.exe",
    "pg_ctl": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_ctl.exe",
    "pg_dump": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pg_dump.exe",
    "pg_dumpall": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pg_dumpall.exe",
    "pg_isready": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_isready.exe",
    "pg_receivewal": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_receivewal.exe",
    "pg_recvlogical": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_recvlogical.exe",
    "pg_resetwal": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_resetwal.exe",
    "pg_restore": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pg_restore.exe",
    "pg_rewind": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_rewind.exe",
    "pg_test_fsync": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_test_fsync.exe",
    "pg_test_timing": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_test_timing.exe",
    "pg_upgrade": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_upgrade.exe",
    "pg_verifybackup": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_verifybackup.exe",
    "pg_waldump": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_waldump.exe",
    "pg_walsummary": "C:\\Program Files\\PostgreSQL\\18\\bin\\pg_walsummary.exe",
    "postgres": "C:\\Program Files\\PostgreSQL\\18\\bin\\postgres.exe",
    "psql": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\psql.exe",
    "reindexdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\reindexdb.exe",
    "stackbuilder": "C:\\Program Files\\PostgreSQL\\18\\bin\\stackbuilder.exe",
    "vacuumdb": "C:\\Program Files\\PostgreSQL\\18\\bin\\vacuumdb.exe",
    "vacuumlo": "C:\\Program Files\\PostgreSQL\\18\\bin\\vacuumlo.exe",
    "isolationtester": "C:\\Program Files\\PostgreSQL\\18\\lib\\pgxs\\src\\test\\isolation\\isolationtester.exe",
    "pg_isolation_regress": "C:\\Program Files\\PostgreSQL\\18\\lib\\pgxs\\src\\test\\isolation\\pg_isolation_regress.exe",
    "pg_regress": "C:\\Program Files\\PostgreSQL\\18\\lib\\pgxs\\src\\test\\regress\\pg_regress.exe",
    "pgadmin4": "C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pgAdmin4.exe",
    "plink": "C:\\Program Files\\PuTTY\\plink.exe",
    "pscp": "C:\\Program Files\\PuTTY\\pscp.exe",
    "rpi-imager-callback-relay": "C:\\Program Files\\Raspberry Pi Ltd\\Imager\\rpi-imager-callback-relay.exe",
    "rpi-imager": "C:\\Program Files\\Raspberry Pi Ltd\\Imager\\rpi-imager.exe",
    "elevate": "C:\\Program Files\\Vortex\\resources\\elevate.exe",
    "launchersupport": "C:\\Program Files\\Roberts Space Industries\\RSI Launcher\\resources\\LauncherSupport.exe",
    "launcher": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\launcher.exe",
    "rockstarerrorhandler": "C:\\Program Files\\Rockstar Games\\Launcher\\ThirdParty\\Crashpad\\RockstarErrorHandler.exe",
    "tailscale-ipn": "C:\\Program Files\\Tailscale\\tailscale-ipn.exe",
    "tailscaled": "C:\\Program Files\\Tailscale\\tailscaled.exe",
    "teamviewer_desktop": "C:\\Program Files\\TeamViewer\\TeamViewer_Desktop.exe",
    "teamviewer_note": "C:\\Program Files\\TeamViewer\\TeamViewer_Note.exe",
    "tv_w32": "C:\\Program Files\\TeamViewer\\tv_w32.exe",
    "tv_x64": "C:\\Program Files\\TeamViewer\\tv_x64.exe",
    "writedump": "C:\\Program Files\\TeamViewer\\WriteDump.exe",
    "teracopy": "C:\\Program Files\\TeraCopy\\32-bit\\TeraCopy.exe",
    "curaengine": "C:\\Program Files\\UltiMaker Cura 5.13.0\\CuraEngine.exe",
    "ultimaker-cura": "C:\\Program Files\\UltiMaker Cura 5.13.0\\UltiMaker-Cura.exe",
    "dpinst-amd64": "C:\\Program Files\\UltiMaker Cura 5.13.0\\share\\windows\\arduino\\dpinst-amd64.exe",
    "dpinst-x86": "C:\\Program Files\\UltiMaker Cura 5.13.0\\share\\windows\\arduino\\dpinst-x86.exe",
    "audioendpointtool": "C:\\Program Files\\Voicemod V3\\driver\\AudioEndPointTool.exe",
    "voicemodcon": "C:\\Program Files\\Voicemod V3\\driver\\voicemodcon.exe",
    "dotnetprobe": "C:\\Program Files\\Vortex\\resources\\app.asar.unpacked\\assets\\dotnetprobe.exe",
    "divine": "C:\\Program Files\\Vortex\\resources\\app.asar.unpacked\\bundledPlugins\\game-baldursgate3\\tools\\divine.exe",
    "arctool": "C:\\Program Files\\Vortex\\resources\\app.asar.unpacked\\bundledPlugins\\mtframework-arc-support\\ARCtool.exe",
    "windowsdesktop-runtime-win-x64": "C:\\Program Files\\Vortex\\resources\\temp\\windowsdesktop-runtime-win-x64.exe",
    "configsecuritypolicy": "C:\\Program Files\\Windows Defender\\ConfigSecurityPolicy.exe",
    "mipdlp": "C:\\Program Files\\Windows Defender\\MipDlp.exe",
    "mpcopyaccelerator": "C:\\Program Files\\Windows Defender\\MpCopyAccelerator.exe",
    "mpextms": "C:\\Program Files\\Windows Defender\\mpextms.exe",
    "msmpeng": "C:\\Program Files\\Windows Defender\\MsMpEng.exe",
    "nissrv": "C:\\Program Files\\Windows Defender\\NisSrv.exe",
    "offlinescannershell": "C:\\Program Files\\Windows Defender\\Offline\\OfflineScannerShell.exe",
    "wab": "C:\\Program Files (x86)\\Windows Mail\\wab.exe",
    "wabmig": "C:\\Program Files (x86)\\Windows Mail\\wabmig.exe",
    "wmlaunch": "C:\\Program Files (x86)\\Windows Media Player\\wmlaunch.exe",
    "rar": "C:\\Program Files\\WinRAR\\Rar.exe",
    "unrar": "C:\\Program Files\\WinRAR\\UnRAR.exe",
    "capinfos": "C:\\Program Files\\Wireshark\\capinfos.exe",
    "captype": "C:\\Program Files\\Wireshark\\captype.exe",
    "dumpcap": "C:\\Program Files\\Wireshark\\dumpcap.exe",
    "editcap": "C:\\Program Files\\Wireshark\\editcap.exe",
    "mergecap": "C:\\Program Files\\Wireshark\\mergecap.exe",
    "mmdbresolve": "C:\\Program Files\\Wireshark\\mmdbresolve.exe",
    "npcap-1.88": "C:\\Program Files\\Wireshark\\npcap-1.88.exe",
    "randpkt": "C:\\Program Files\\Wireshark\\randpkt.exe",
    "rawshark": "C:\\Program Files\\Wireshark\\rawshark.exe",
    "reordercap": "C:\\Program Files\\Wireshark\\reordercap.exe",
    "sharkd": "C:\\Program Files\\Wireshark\\sharkd.exe",
    "text2pcap": "C:\\Program Files\\Wireshark\\text2pcap.exe",
    "tshark": "C:\\Program Files\\Wireshark\\tshark.exe",
    "androiddump": "C:\\Program Files\\Wireshark\\extcap\\androiddump.exe",
    "ciscodump": "C:\\Program Files\\Wireshark\\extcap\\ciscodump.exe",
    "etwdump": "C:\\Program Files\\Wireshark\\extcap\\etwdump.exe",
    "randpktdump": "C:\\Program Files\\Wireshark\\extcap\\randpktdump.exe",
    "sshdump": "C:\\Program Files\\Wireshark\\extcap\\sshdump.exe",
    "udpdump": "C:\\Program Files\\Wireshark\\extcap\\udpdump.exe",
    "wifidump": "C:\\Program Files\\Wireshark\\extcap\\wifidump.exe",
    "msrdc": "C:\\Program Files\\WSL\\msrdc.exe",
    "wsl": "C:\\Program Files\\WSL\\wsl.exe",
    "wslg": "C:\\Program Files\\WSL\\wslg.exe",
    "wslhost": "C:\\Program Files\\WSL\\wslhost.exe",
    "wslrelay": "C:\\Program Files\\WSL\\wslrelay.exe",
    "wslsettings": "C:\\Program Files\\WSL\\wslsettings\\wslsettings.exe",
    "accapplauncher": "C:\\Program Files (x86)\\Acer\\Care Center\\ACCAppLauncher.exe",
    "accnvmedst": "C:\\Program Files (x86)\\Acer\\Care Center\\AccNvmeDST.exe",
    "accstd": "C:\\Program Files (x86)\\Acer\\Care Center\\ACCStd.exe",
    "accsvc": "C:\\Program Files (x86)\\Acer\\Care Center\\ACCSvc.exe",
    "accublauncher": "C:\\Program Files (x86)\\Acer\\Care Center\\ACCUBLauncher.exe",
    "fub": "C:\\Program Files (x86)\\Acer\\Care Center\\FUB.exe",
    "getfub": "C:\\Program Files (x86)\\Acer\\Care Center\\GetFUB.exe",
    "idcard": "C:\\Program Files (x86)\\Acer\\Care Center\\IDCard.exe",
    "ram_test": "C:\\Program Files (x86)\\Acer\\Care Center\\RAM_TEST.exe",
    "smartctl-nc": "C:\\Program Files (x86)\\Acer\\Care Center\\smartmontools\\bin\\smartctl-nc.exe",
    "smartctl": "C:\\Program Files (x86)\\Acer\\Care Center\\smartmontools\\bin\\smartctl.exe",
    "smartd": "C:\\Program Files (x86)\\Acer\\Care Center\\smartmontools\\bin\\smartd.exe",
    "wtssendmsg": "C:\\Program Files (x86)\\Acer\\Care Center\\smartmontools\\bin\\wtssendmsg.exe",
    "aapt": "C:\\Program Files (x86)\\AirDroid\\IncludeAdb\\aapt.exe",
    "airdroid_adb": "C:\\Program Files (x86)\\AirDroid\\IncludeAdb\\AirDroid_adb.exe",
    "ffmpeg_amr": "C:\\Program Files (x86)\\AirDroid\\IncludeAdb\\ffmpeg_amr.exe",
    "attackshark": "C:\\Program Files (x86)\\Attack Shark Software\\AttackShark.exe",
    "easyanticheat": "C:\\Program Files (x86)\\EasyAntiCheat\\EasyAntiCheat.exe",
    "easyanticheat_eos": "C:\\Program Files (x86)\\EasyAntiCheat_EOS\\EasyAntiCheat_EOS.exe",
    "eosoverlayrenderer-win32-shipping": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Extras\\Overlay\\EOSOverlayRenderer-Win32-Shipping.exe",
    "eosoverlayrenderer-win64-shipping": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Extras\\Overlay\\EOSOverlayRenderer-Win64-Shipping.exe",
    "epicgameslauncher": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe",
    "unrealenginelauncher": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Engine\\Binaries\\Win64\\UnrealEngineLauncher.exe",
    "unrealversionselector": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Engine\\Binaries\\Win64\\UnrealVersionSelector.exe",
    "installchainer": "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Extras\\EOS\\InstallChainer.exe",
    "remote_assistance_host": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remote_assistance_host.exe",
    "remote_assistance_host_uiaccess": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remote_assistance_host_uiaccess.exe",
    "remote_open_url": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remote_open_url.exe",
    "remote_security_key": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remote_security_key.exe",
    "remote_webauthn": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remote_webauthn.exe",
    "remoting_desktop": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remoting_desktop.exe",
    "remoting_host": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remoting_host.exe",
    "remoting_native_messaging_host": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remoting_native_messaging_host.exe",
    "remoting_start_host": "C:\\Program Files (x86)\\Google\\Chrome Remote Desktop\\154.0.8037.40\\remoting_start_host.exe",
    "gpu-z": "C:\\Program Files (x86)\\GPU-Z\\GPU-Z.exe",
    "copilotapp": "C:\\Program Files (x86)\\Microsoft\\EdgeCore\\Optimized\\copilotapp.exe",
    "cookie_exporter": "C:\\Program Files (x86)\\Microsoft\\EdgeWebView\\Application\\155.0.4283.45\\cookie_exporter.exe",
    "ie_to_edge_stub": "C:\\Program Files (x86)\\Microsoft\\EdgeWebView\\Application\\155.0.4283.45\\BHO\\ie_to_edge_stub.exe",
    "copilotapphost": "C:\\Program Files (x86)\\Microsoft\\Copilot\\Application\\undocked_copilot\\copilotapphost.exe",
    "msedge": "C:\\Program Files (x86)\\Microsoft\\EdgeCore\\Optimized\\msedge.exe",
    "msedge_pwa_launcher": "C:\\Program Files (x86)\\Microsoft\\EdgeCore\\Optimized\\msedge_pwa_launcher.exe",
    "passkey_authenticator_plugin": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\155.0.4283.45\\passkey_authenticator_plugin.exe",
    "mscopilot": "C:\\Program Files (x86)\\Microsoft\\EdgeCore\\Optimized\\mscopilot.exe",
    "msedgewebview2": "C:\\Program Files (x86)\\Microsoft\\EdgeWebView\\Application\\155.0.4283.45\\msedgewebview2.exe",
    "microsoftedgecomregistershellarm64": "C:\\Program Files (x86)\\Microsoft\\EdgeUpdate\\1.3.287.9\\MicrosoftEdgeComRegisterShellARM64.exe",
    "microsoftedge_x64_155.0.4283.45_154.0.4258.62": "C:\\Program Files (x86)\\Microsoft\\EdgeUpdate\\Download\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}\\155.0.4283.45\\MicrosoftEdge_X64_155.0.4283.45_154.0.4258.62.exe",
    "copilotundockedhost_x64_155.0.4283.45": "C:\\Program Files (x86)\\Microsoft\\EdgeUpdate\\Download\\{C50565E9-CCCF-44B4-BA15-5AC5C6569197}\\155.0.4283.45\\CopilotUndockedHost_X64_155.0.4283.45.exe",
    "microsoftedge_x64_155.0.4283.45": "C:\\Program Files (x86)\\Microsoft\\EdgeUpdate\\Download\\{C50565E9-CCCF-44B4-BA15-5AC5C6569197}\\155.0.4283.45\\MicrosoftEdge_X64_155.0.4283.45.exe",
    "appsharinghookcontroller": "C:\\Program Files (x86)\\Microsoft Office\\Office16\\AppSharingHookController.exe",
    "common.dbconnection": "C:\\Program Files (x86)\\Microsoft Office\\Office16\\DCF\\Common.DBConnection.exe",
    "common.dbconnection64": "C:\\Program Files (x86)\\Microsoft Office\\Office16\\DCF\\Common.DBConnection64.exe",
    "common.showhelp": "C:\\Program Files (x86)\\Microsoft Office\\Office16\\DCF\\Common.ShowHelp.exe",
    "filecompare": "C:\\Program Files (x86)\\Microsoft Office\\Office16\\DCF\\filecompare.exe",
    "mobarte": "C:\\Program Files (x86)\\Mobatek\\MobaXterm\\MobaRTE.exe",
    "nsight.coredumploader": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Nsight.CoreDumpLoader.exe",
    "nsight.monitor": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Nsight.Monitor.exe",
    "nvda.gpu.debugtool": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Nvda.Gpu.DebugTool.exe",
    "nvda.gpu.configuration.dump": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Injection64\\Nvda.Gpu.Configuration.Dump.exe",
    "nvda.processinfo": "C:\\Program Files (x86)\\NVIDIA Corporation\\Nsight Visual Studio Edition 2025.2\\Monitor\\Common\\Injection64\\Nvda.ProcessInfo.exe",
    "oalinst": "C:\\Program Files (x86)\\OpenAL\\oalinst.exe",
    "robloxplayerbeta": "C:\\Program Files (x86)\\Roblox\\Versions\\version-36a2600cebf1487d\\RobloxPlayerBeta.exe",
    "gameoverlayui64": "C:\\Program Files (x86)\\Steam\\gameoverlayui64.exe",
    "steamerrorreporter": "C:\\Program Files (x86)\\Steam\\steamerrorreporter.exe",
    "steamerrorreporter64": "C:\\Program Files (x86)\\Steam\\steamerrorreporter64.exe",
    "steamsysinfo": "C:\\Program Files (x86)\\Steam\\steamsysinfo.exe",
    "writeminidump": "C:\\Program Files (x86)\\Steam\\WriteMiniDump.exe",
    "fossilize-replay": "C:\\Program Files (x86)\\Steam\\bin\\fossilize-replay.exe",
    "fossilize-replay64": "C:\\Program Files (x86)\\Steam\\bin\\fossilize-replay64.exe",
    "secure_desktop_capture": "C:\\Program Files (x86)\\Steam\\bin\\secure_desktop_capture.exe",
    "steamxboxutil": "C:\\Program Files (x86)\\Steam\\bin\\steamxboxutil.exe",
    "steamxboxutil64": "C:\\Program Files (x86)\\Steam\\bin\\steamxboxutil64.exe",
    "steam_monitor": "C:\\Program Files (x86)\\Steam\\bin\\steam_monitor.exe",
    "x64launcher": "C:\\Program Files (x86)\\Steam\\bin\\x64launcher.exe",
    "x86launcher": "C:\\Program Files (x86)\\Steam\\bin\\x86launcher.exe",
    "swiss selector": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Car Mechanic Simulator 2018\\cms2018_Data\\Managed\\Swiss Selector.exe",
    "gamble with your friends": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Gamble With Your Friends\\Gamble With Your Friends.exe",
    "geareo": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Geareo Demo\\geareo.exe",
    "kingdomtwocrowns": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Kingdom Two Crowns\\KingdomTwoCrowns.exe",
    "people playground": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\People Playground\\People Playground.exe",
    "ppgmodcompiler": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\People Playground\\ppgModCompiler\\PPGModCompiler.exe",
    "scritchyscratchy": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Scritchy Scratchy\\ScritchyScratchy.exe",
    "stardewmoddingapi": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Stardew Valley\\StardewModdingAPI.exe",
    "ndp462-kb3151800-x86-x64-allos-enu": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Steamworks Shared\\_CommonRedist\\DotNet\\4.6\\NDP462-KB3151800-x86-x64-AllOS-ENU.exe",
    "upload labs": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Upload Labs\\Upload Labs.exe",
    "wallpaper32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\wallpaper32.exe",
    "wallpaper64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\wallpaper64.exe",
    "applicationwallpaperinject32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\applicationwallpaperinject32.exe",
    "applicationwallpaperinject64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\applicationwallpaperinject64.exe",
    "apputil32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\apputil32.exe",
    "diagnostics32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\diagnostics32.exe",
    "diagnostics64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\diagnostics64.exe",
    "edgewallpaper64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\edgewallpaper64.exe",
    "resourcecompiler32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\resourcecompiler32.exe",
    "resourcecompiler64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\resourcecompiler64.exe",
    "wallpaperui": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\wallpaperui.exe",
    "webwallpaper64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\webwallpaper64.exe",
    "winrtutil32": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\winrtutil32.exe",
    "winrtutil64": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\distribution\\bin\\winrtutil64.exe",
    "sheep": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\wallpaper_engine\\projects\\defaultprojects\\sheep\\sheep.exe",
    "ubisoftconnect": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe",
    "ubisoftextension": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftExtension.exe",
    "ubisoftgamelauncher": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftGameLauncher.exe",
    "ubisoftgamelauncher64": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftGameLauncher64.exe",
    "upc": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\upc.exe",
    "uplaywebcore": "C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UplayWebCore.exe",
    "wisedatarecovery": "C:\\Program Files (x86)\\Wise\\Wise Data Recovery\\WiseDataRecovery.exe",
    "wisediskcleaner": "C:\\Program Files (x86)\\Wise\\Wise Disk Cleaner\\WiseDiskCleaner.exe",
    "wisedeleter": "C:\\Program Files (x86)\\Wise\\Wise Force Deleter\\WiseDeleter.exe",
    "wisefd": "C:\\Program Files (x86)\\Wise\\Wise Force Deleter\\wisefd.exe"
}
```


==================================================
 ARQUIVO: .\DADOS\config_paths.json
==================================================

```text
{"ssd_path": "C:/modelos", "hd_path": "D:/modelosgrades"}
```


==================================================
 ARQUIVO: .\DADOS\jarvis_identity.json
==================================================

```text
{
    "cpu_modelo": "AMD Ryzen 5 3550H with Radeon Vega Mobile Gfx",
    "cpu_cores": "4 cores / 8 threads",
    "gpu_modelo": "NVIDIA GeForce GTX 1650",
    "vram_total_gb": 4.0,
    "ram_total_gb": 29.94,
    "os_versao": "Windows 11",
    "mapeado_em": "Felipe"
}
```


==================================================
 ARQUIVO: .\DADOS\lembretes.json
==================================================

```text
[
  {
    "id": "rem_001",
    "texto": "Reunião de alinhamento estratégico do projeto",
    "horario": "14:30",
    "criado_em": "15/10/2026 09:00",
    "concluido": false
  },
  {
    "id": "rem_002",
    "texto": "Revisar telemetria de sensores e núcleos de IA",
    "horario": "17:00",
    "criado_em": "15/10/2026 09:15",
    "concluido": false
  }
]
```


==================================================
 ARQUIVO: .\DADOS\mcp_servers.json
==================================================

```text
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "description": "Servidor MCP oficial para busca e extração de páginas web"
    },
    "web-search": {
      "command": "python",
      "args": ["-m", "MODULOS.skills.mcp_client", "--server"],
      "description": "Servidor interno Jarvis de busca na internet e ferramentas em tempo real"
    }
  }
}

```


==================================================
 ARQUIVO: .\DADOS\model_registry.json
==================================================

```text
{
  "_perfil_detectado": "LOW",
  "_hardware_detectado": {
    "vram_gb": 4.0,
    "ram_gb": 29.94,
    "cpu_cores": 4,
    "cpu_modelo": "AMD Ryzen 5 3550H with Radeon Vega Mobile Gfx",
    "gpu_modelo": "NVIDIA GeForce GTX 1650"
  },
  "_descricao_perfil": "VRAM 4-6 GB — Modelos balanceados com quantização leve e AirLLM.",
  "modelo_roteador": "qwen3:1.7b",
  "especialistas": {
    "HARDWARE": {
      "tipo": "funcao_local",
      "modulo": "hardware_module",
      "descricao": "Monitoramento de CPU, GPU, RAM e temperaturas."
    },
    "ABRIR_APP": {
      "tipo": "funcao_local",
      "modulo": "actions_module",
      "descricao": "Execução de programas e comandos do Windows."
    },
    "CONVERSA": {
      "tipo": "llm",
      "modelo_ollama": "llama3.2:3b",
      "descricao": "Interações sociais, perguntas e dúvidas gerais."
    },
    "CODIGO": {
      "tipo": "airllm",
      "repo_id": "Qwen/Qwen2.5-Coder-32B-Instruct",
      "descricao": "Criação de scripts, depuração e lógica de programação."
    },
    "VISAO": {
      "tipo": "llm",
      "modelo_ollama": "moondream",
      "descricao": "Análise de tela e imagens."
    },
    "TAREFA_LONGA": {
      "tipo": "airllm",
      "repo_id": "Qwen/Qwen2.5-72B-Instruct",
      "descricao": "Raciocínio complexo, planejamento e tarefas que exigem múltiplos passos."
    },
    "MEMORIA": {
      "tipo": "llm",
      "modelo_ollama": "llama3.2:3b",
      "descricao": "Guardar, lembrar ou esquecer informações e fatos pessoais. Ativado por palavras como: guarda, salva, lembra, anota, grava, esquece, sabe que."
    },
    "WEB_MCP": {
      "tipo": "llm",
      "modelo_ollama": "llama3.2:3b",
      "descricao": "Pesquisas na internet, notícias em tempo real, previsão do tempo, cotações e ferramentas online via protocolo MCP."
    }
  }
}
```


==================================================
 ARQUIVO: .\DADOS\news_config.json
==================================================

```text
{
    "categorias": [
        "mundo",
        "economia",
        "brasil",
        "tecnologia"
    ],
    "incluir_cotacoes": true,
    "detalhamento": "completo"
}
```


==================================================
 ARQUIVO: .\DADOS\voice_config.json
==================================================

```text
{
    "motor": "edge",
    "voz": "pt-BR-AntonioNeural",
    "nome": "⚡ Neural: Antonio (Zero CPU - Rápido)",
    "efeito_jarvis": true
}
```


==================================================
 ARQUIVO: .\INTERFACE\app.js
==================================================

```text
window.setupIniciadoManualmente = false;

// ═══════════════════════════════════════════════════════
//  EXPOSIÇÃO DE GLOBAIS E CONTROLE DE ESTADOS
// ═══════════════════════════════════════════════════════
window.showGraphs = function(v) {
    const p = document.getElementById('page-graphs');
    if (p) {
        p.style.display = v ? 'flex' : 'none';
        if (typeof targetPattern !== 'undefined') targetPattern = v ? 'codigo' : 'dormindo';
    }
};

window.debugSetState = (s) => {
    window.setupIniciadoManualmente = true;
    const overlay = document.getElementById('setup-overlay');
    if (s === 'home') { 
        if(overlay) overlay.remove(); 
        if (typeof targetPattern !== 'undefined') targetPattern = 'dormindo'; 
    }
    else if (s === 'setup') { 
        if(overlay) overlay.remove(); 
        abrirPortalSetup(); 
    }
    else if (s === 'download') { 
        if(!overlay) abrirPortalSetup(); 
        mudarParaInterfaceDownload(); 
    }
    else if (s === 'sharding') { 
        if(!overlay) abrirPortalSetup(); 
        mudarParaInterfaceSharding(); 
    }
    else if (s === 'graphs') { 
        window.showGraphs(true); 
    }
};

// ═══════════════════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════════════════
const subText = document.getElementById('subtitles');
const label = document.getElementById('status-label');

let targetColor = null;
let targetIntensity = 0.1;
let currentIntensity = 0.1;
let corEstado = '#00ffff';
let falando = false;
let timerVolta = null;

let currentPattern = 'conversa';
let targetPattern = 'conversa';
let patternBlend = 1.0;
let frozenPattern = null;

function initColors() {
    if (typeof THREE !== 'undefined' && !targetColor) {
        targetColor = new THREE.Color('#00ffff');
    }
}

// ═══════════════════════════════════════════════════════
//  PADRÕES DE MOVIMENTO DA ESFERA NEURAL
// ═══════════════════════════════════════════════════════
function getPatternState(name, t, intensity) {
    switch(name) {
        case 'dormindo': return { rotX: 0.00008, rotY: 0.0003, rotZ: 0.00005, offsetX: 0, offsetY: 0, noiseSpeed: 0.15, noiseScale: 0.3 * intensity };
        case 'ouvindo': return { rotX: 0.0004 + 0.0003 * Math.sin(t * 0.5), rotY: 0.002, rotZ: 0.0001, offsetX: 0.05 * Math.sin(t * 0.3), offsetY: 0.03 * Math.sin(t * 0.2), noiseSpeed: 0.3, noiseScale: 0.6 * intensity };
        case 'conversa': return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
        case 'hardware': return { rotX: 0.0, rotY: 0.006, rotZ: 0.0, offsetX: 0, offsetY: 0, noiseSpeed: 0.2, noiseScale: 0.8 * intensity };
        case 'app': return { rotX: 0.0001, rotY: 0.002, rotZ: 0.004, offsetX: 0, offsetY: 0, noiseSpeed: 0.5, noiseScale: 1.5 * intensity };
        case 'memoria': return { rotX: 0.001, rotY: 0.001, rotZ: 0.001, offsetX: 0.12 * Math.sin(t * 0.8), offsetY: 0.12 * Math.cos(t * 0.8), noiseSpeed: 0.35, noiseScale: 1.2 * intensity };
        case 'codigo': return { rotX: 0.003 * Math.sin(t * 0.4), rotY: 0.004, rotZ: 0.002 * Math.cos(t * 0.3), offsetX: 0, offsetY: 0, noiseSpeed: 0.6, noiseScale: 1.8 * intensity };
        case 'tarefa': return { rotX: 0.0015, rotY: 0.003, rotZ: 0.001, offsetX: 0, offsetY: 0, noiseSpeed: 0.25, noiseScale: 1.0 * intensity };
        case 'alerta': return { rotX: 0.002 * Math.sin(t * 8.0), rotY: 0.008, rotZ: 0.003 * Math.cos(t * 7.0), offsetX: 0.15 * Math.sin(t * 12.0), offsetY: 0.08 * Math.cos(t * 9.0), noiseSpeed: 1.2, noiseScale: 3.0 * intensity };
        default: return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
    }
}

function lerpPattern(a, b, alpha) {
    const l = (x, y, t) => x + (y - x) * t;
    return {
        rotX: l(a.rotX, b.rotX, alpha), rotY: l(a.rotY, b.rotY, alpha), rotZ: l(a.rotZ, b.rotZ, alpha),
        offsetX: l(a.offsetX, b.offsetX, alpha), offsetY: l(a.offsetY, b.offsetY, alpha),
        noiseSpeed: l(a.noiseSpeed, b.noiseSpeed, alpha), noiseScale: l(a.noiseScale, b.noiseScale, alpha),
    };
}

function getBlendedPattern(t, intensity) {
    const pB = getPatternState(targetPattern, t, intensity);
    if (patternBlend >= 1.0) return pB;
    const pA = frozenPattern || getPatternState(currentPattern, t, intensity);
    return lerpPattern(pA, pB, patternBlend);
}

// ═══════════════════════════════════════════════════════
//  WEBSOCKET E SINCRONIZAÇÃO EM TEMPO REAL
// ═══════════════════════════════════════════════════════
let socket;
function conectarWS() {
    socket = new WebSocket('ws://' + window.location.host + '/ws');
    socket.onmessage = function(event) {
        try {
            const d = JSON.parse(event.data);
            
            if (d.type === "hardware_update") {
                atualizarGraficosHardware(d.hardware);
                return;
            }
            if (d.type === "mic_mute_update") {
                atualizarVisualMute(d.muted);
            }
            if (d.type === "download_update") {
                if (document.getElementById('donuts-container')) {
                    atualizarProgressoVisual(d.download);
                } else if (d.download.ativo && !window.setupIniciadoManualmente) {
                    atualizarProgressoVisual(d.download);
                }
                return;
            }
            if (d.type === "sharding_update") {
                if (d.sharding.ativo) {
                    if (!document.getElementById('shard-msg')) {
                        if (!document.getElementById('setup-overlay')) abrirPortalSetup();
                        mudarParaInterfaceSharding();
                    }
                    atualizarShardingVisual(d.sharding);
                } else if (document.getElementById('setup-overlay') && !window.setupIniciadoManualmente) {
                    setTimeout(() => { const o = document.getElementById('setup-overlay'); if(o) o.remove(); }, 2000);
                }
                return;
            }

            if (d.type === "briefing_start") {
                lidarBriefingStart(d);
                return;
            }
            if (d.type === "briefing_card_focus") {
                lidarBriefingCardFocus(d.card, d.indice, d.total);
                return;
            }
            if (d.type === "briefing_end") {
                lidarBriefingEnd(d);
                return;
            }

            if (d.cor) { 
                corEstado = d.cor; 
                initColors();
                if(targetColor) targetColor.set(d.cor); 
                atualizarCorUI(d.cor); 
            }

            if (d.texto !== undefined) {
                if (subText) {
                    subText.innerText = d.texto;
                    subText.scrollTop = subText.scrollHeight;
                }
                if (d.texto && d.texto.trim()) {
                    adicionarAoHistoricoLog("JARVIS", d.texto);
                }
            }

            if (d.intensidade !== undefined) {
                targetIntensity = d.intensidade;
                if (d.intensidade > 0.15) {
                    falando = true;
                    if (timerVolta) clearTimeout(timerVolta);
                } else if (falando) {
                    falando = false;
                    timerVolta = setTimeout(() => { 
                        if (targetColor) targetColor.set(corEstado); 
                        atualizarCorUI(corEstado); 
                    }, 600);
                }
            }

            if (d.padrao && d.padrao !== targetPattern) {
                const snap = getBlendedPattern(Date.now() * 0.001, currentIntensity);
                frozenPattern = { ...snap }; 
                currentPattern = targetPattern; 
                targetPattern = d.padrao; 
                patternBlend = 0.0;
                atualizarCardAtividade(d.padrao, d.texto);
            }
        } catch(e) { 
            console.error('Erro no processamento do WebSocket:', e); 
        }
    };
    socket.onclose = function() { setTimeout(conectarWS, 2000); };
    socket.onerror = function() { socket.close(); };
}

function atualizarCorUI(hex) {
    if (subText) {
        subText.style.color = hex; 
        subText.style.textShadow = `0 0 15px ${hex}`;
        subText.style.borderColor = `${hex}55`;
    }
    if (label) {
        label.style.color = hex; 
        label.style.textShadow = `0 0 10px ${hex}`;
    }
    const dot = document.getElementById('system-status-dot');
    if (dot) {
        dot.style.background = hex;
        dot.style.boxShadow = `0 0 10px ${hex}`;
    }
}

// ═══════════════════════════════════════════════════════
//  HARDWARE HUD & MINI-BADGES
// ═══════════════════════════════════════════════════════
const historyCpu = []; 
const historyGpu = []; 
const historyRam = [];

function atualizarGraficosHardware(hw) {
    const cpu = Math.round(hw.cpu_usage || 0);
    const gpu = Math.round(hw.gpu_load || 0);
    const ram = Math.round(hw.ram_usage || 0);

    // 1. Atualiza Mini-Badges no Top Bar
    const topCpu = document.getElementById('top-cpu'); if(topCpu) topCpu.innerText = `${cpu}%`;
    const topGpu = document.getElementById('top-gpu'); if(topGpu) topGpu.innerText = `${gpu}%`;
    const topRam = document.getElementById('top-ram'); if(topRam) topRam.innerText = `${ram}%`;

    // 2. Atualiza Dashboard Modal Completo
    const mc = document.getElementById('metric-cpu'); if(mc) mc.innerText = cpu;
    const mg = document.getElementById('metric-gpu'); if(mg) mg.innerText = gpu;
    const mr = document.getElementById('metric-ram'); if(mr) mr.innerText = ram;

    const tc = document.getElementById('cpu-temp'); 
    if(tc && hw.cpu_temp !== "N/A" && hw.cpu_temp !== undefined) tc.innerText = `TEMP: ${hw.cpu_temp}°C`;

    const gs = document.getElementById('gpu-stats'); 
    if(gs && hw.gpu_temp !== "N/A" && hw.gpu_temp !== undefined) {
        gs.innerText = `TEMP: ${hw.gpu_temp}°C | VRAM: ${hw.vram_used_gb || '--'} GB | PWR: ${hw.gpu_power || '--'}W`;
    }

    pushChartData('chart-cpu', historyCpu, cpu);
    pushChartData('chart-gpu', historyGpu, gpu);
    pushChartData('chart-ram', historyRam, ram);
}

function pushChartData(id, history, val) {
    history.push(val); 
    if (history.length > 40) history.shift();
    const c = document.getElementById(id); 
    if (c) c.innerHTML = history.map(v => `<div class="chart-bar" style="height: ${v}%"></div>`).join('');
}

// ═══════════════════════════════════════════════════════
//  GAVETA LATERAL RETRÁTIL & ATIVIDADES
// ═══════════════════════════════════════════════════════
const PATTERN_INFO = {
    'dormindo': { nome: 'Modo de Espera', tag: 'STANDBY', led: '#00ffff', desc: 'Aguardando comandos de voz ou texto...' },
    'conversa': { nome: 'Conversação Neural', tag: 'FALANDO', led: '#00ff88', desc: 'Respondendo interação do usuário.' },
    'ouvindo': { nome: 'Audição & VAD', tag: 'ESCUTANDO', led: '#00ffff', desc: 'Microfone ativo captando comandos.' },
    'tarefa': { nome: 'Executor de Tarefas', tag: 'EXECUÇÃO', led: '#ffaa00', desc: 'Processando fluxo de automação ou scripts.' },
    'codigo': { nome: 'Núcleo de Código', tag: 'ANÁLISE', led: '#00ffff', desc: 'Análise sintática, geração ou execução de scripts.' },
    'memoria': { nome: 'Memória Semântica', tag: 'CHROMA', led: '#aa00ff', desc: 'Consultando ou registrando vetores neurais.' },
    'hardware': { nome: 'Sentinela Térmico', tag: 'TELEMETRIA', led: '#00ffff', desc: 'Coletando métricas e verificando sensores.' },
    'alerta': { nome: 'Sistema de Alerta', tag: 'ALERTA', led: '#ff0055', desc: 'Aviso crítico de proteção ou temperatura elevada.' },
    'app': { nome: 'Controle de Aplicativos', tag: 'SISTEMA', led: '#00ffff', desc: 'Interagindo com sistema operacional e janelas.' }
};

function atualizarCardAtividade(padrao, textoOpcional) {
    const info = PATTERN_INFO[padrao] || PATTERN_INFO['conversa'];
    const nameEl = document.getElementById('current-agent-name');
    const tagEl = document.getElementById('current-agent-tag');
    const ledEl = document.getElementById('current-agent-led');
    const descEl = document.getElementById('current-agent-desc');
    const timeEl = document.getElementById('current-agent-time');

    if (nameEl) nameEl.innerText = info.nome;
    if (tagEl) {
        tagEl.innerText = info.tag;
        tagEl.style.color = info.led;
        tagEl.style.borderColor = `${info.led}55`;
        tagEl.style.background = `${info.led}15`;
    }
    if (ledEl) {
        ledEl.style.background = info.led;
        ledEl.style.boxShadow = `0 0 8px ${info.led}`;
    }
    if (descEl) {
        descEl.innerText = (textoOpcional && textoOpcional.length > 5) ? textoOpcional : info.desc;
    }
    if (timeEl) {
        const d = new Date();
        timeEl.innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
}

window.toggleAgentsDrawer = function(force) {
    const drawer = document.getElementById('agents-drawer');
    const btn = document.getElementById('btn-toggle-drawer');
    if (!drawer) return;
    const currentlyOpen = drawer.classList.contains('open');
    const newState = force !== undefined ? force : !currentlyOpen;
    if (newState) {
        drawer.classList.add('open');
        if (btn) btn.classList.add('active');
    } else {
        drawer.classList.remove('open');
        if (btn) btn.classList.remove('active');
    }
};

function adicionarAoHistoricoLog(remetente, mensagem) {
    const list = document.getElementById('drawer-history-list');
    if (!list || !mensagem || !mensagem.trim()) return;

    const lastItem = list.lastElementChild;
    if (lastItem && lastItem.dataset.msg === mensagem) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const item = document.createElement('div');
    item.className = 'history-item ' + (remetente === 'VOCÊ' ? 'user' : (remetente === 'SISTEMA' ? 'system' : 'jarvis'));
    item.dataset.msg = mensagem;

    item.innerHTML = `<span class="history-time">${timeStr}</span><span class="history-sender">${remetente}:</span><span class="history-body">${mensagem}</span>`;
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
}

window.limparHistoricoLog = function() {
    const list = document.getElementById('drawer-history-list');
    if (list) {
        list.innerHTML = `<div class="history-item system"><span class="history-time">RESET</span><span class="history-sender">SISTEMA:</span><span class="history-body">Histórico limpo pelo usuário.</span></div>`;
    }
};

// ═══════════════════════════════════════════════════════
//  SISTEMA MENU DROPDOWN
// ═══════════════════════════════════════════════════════
window.toggleSysMenu = function(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById('sys-dropdown');
    const btn = document.getElementById('btn-sys-menu');
    if (!menu) return;
    const isOpen = menu.classList.contains('open');
    if (isOpen) {
        menu.classList.remove('open');
        if (btn) btn.classList.remove('active');
    } else {
        menu.classList.add('open');
        if (btn) btn.classList.add('active');
    }
};

window.closeSysMenu = function() {
    const menu = document.getElementById('sys-dropdown');
    const btn = document.getElementById('btn-sys-menu');
    if (menu) menu.classList.remove('open');
    if (btn) btn.classList.remove('active');
};

document.addEventListener('click', function(e) {
    const wrapper = document.querySelector('.dropdown-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
        window.closeSysMenu();
    }
});

// ═══════════════════════════════════════════════════════
//  CONTROLE E SELETOR DE VOZ (TTS) & MODO STARK DSP
// ═══════════════════════════════════════════════════════
window.currentVoiceMotor = 'edge';
window.currentVoiceVoz = 'pt-BR-AntonioNeural';
window.currentVoiceNome = '⚡ Neural: Antonio (Zero CPU - Rápido)';
window.efeitoJarvisAtivo = true;

window.carregarConfigVoz = async function() {
    try {
        const r = await fetch('/api/voice/config');
        const data = await r.json();
        if (data && data.config) {
            window.currentVoiceMotor = data.config.motor || 'edge';
            window.currentVoiceVoz = data.config.voz || 'pt-BR-AntonioNeural';
            window.currentVoiceNome = data.config.nome || '⚡ Neural: Antonio (Zero CPU - Rápido)';
            window.efeitoJarvisAtivo = data.config.efeito_jarvis !== undefined ? !!data.config.efeito_jarvis : true;
            atualizarUISelecaoVoz(window.currentVoiceMotor, window.currentVoiceVoz);
            atualizarUIDsp(window.efeitoJarvisAtivo);
        }
    } catch(e) {
        console.warn("[VOZ] Erro ao obter configuração de voz:", e);
    }
};

window.selecionarVoz = async function(motor, voz, nome) {
    window.currentVoiceMotor = motor;
    window.currentVoiceVoz = voz;
    window.currentVoiceNome = nome;

    // Se for Jarvis Blend, ativa por padrão o Modo Stark
    if (voz === 'blend_jarvis' && window.efeitoJarvisAtivo === undefined) {
        window.efeitoJarvisAtivo = true;
    }

    atualizarUISelecaoVoz(motor, voz);
    atualizarUIDsp(window.efeitoJarvisAtivo);

    try {
        const r = await fetch('/api/voice/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                motor: motor,
                voz: voz,
                nome: nome,
                efeito_jarvis: window.efeitoJarvisAtivo
            })
        });
        const res = await r.json();
        console.log("[VOZ] Configuração atualizada:", res);
    } catch(e) {
        console.error("[VOZ] Falha ao alterar voz:", e);
    }
};

window.alternarEfeitoJarvis = async function() {
    window.efeitoJarvisAtivo = !window.efeitoJarvisAtivo;
    atualizarUIDsp(window.efeitoJarvisAtivo);
    try {
        const r = await fetch('/api/voice/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                motor: window.currentVoiceMotor,
                voz: window.currentVoiceVoz,
                nome: window.currentVoiceNome,
                efeito_jarvis: window.efeitoJarvisAtivo
            })
        });
        const res = await r.json();
        console.log("[VOZ] Modo Stark DSP atualizado:", res);
    } catch(e) {
        console.error("[VOZ] Falha ao alternar Modo Stark DSP:", e);
    }
};

function atualizarUIDsp(ativo) {
    const btn = document.getElementById('btn-toggle-dsp');
    const label = document.getElementById('dsp-toggle-text');
    const badge = document.getElementById('dsp-badge');
    if (!btn) return;

    if (ativo) {
        btn.classList.remove('inactive');
        btn.classList.add('active');
        if (label) label.textContent = 'Modo Stark (ON)';
        if (badge) {
            badge.textContent = 'ATIVO';
        }
    } else {
        btn.classList.remove('active');
        btn.classList.add('inactive');
        if (label) label.textContent = 'Modo Stark (OFF)';
        if (badge) {
            badge.textContent = 'OFF';
        }
    }
}

function atualizarUISelecaoVoz(motor, voz) {
    document.querySelectorAll('.voice-opt').forEach(el => el.classList.remove('selected'));
    let targetId = '';
    if (motor === 'kokoro') {
        if (voz === 'pm_alex') targetId = 'vopt-kokoro_alex';
        else if (voz === 'pf_dora') targetId = 'vopt-kokoro_dora';
        else if (voz === 'pm_santa') targetId = 'vopt-kokoro_santa';
        else if (voz === 'blend_jarvis') targetId = 'vopt-kokoro_blend';
    } else if (motor === 'edge') {
        if (voz.includes('Antonio')) targetId = 'vopt-edge_antonio';
        else if (voz.includes('Francisca')) targetId = 'vopt-edge_francisca';
    }
    const btn = document.getElementById(targetId);
    if (btn) {
        btn.classList.add('selected');
    }
}

// ═══════════════════════════════════════════════════════
//  BRIEFING EXECUTIVO DE NOTÍCIAS & COTAÇÕES
// ═══════════════════════════════════════════════════════
window.newsConfig = {
    categorias: ['mundo', 'economia', 'brasil', 'tecnologia'],
    incluir_cotacoes: true,
    detalhamento: 'completo'
};

window.carregarConfigNoticias = async function() {
    try {
        const r = await fetch('/api/news/config');
        const data = await r.json();
        if (data && Array.isArray(data.categorias)) {
            window.newsConfig = data;
            atualizarUINoticias();
        }
    } catch(e) {
        console.warn("[NOTÍCIAS] Erro ao carregar preferências de notícias:", e);
    }
};

window.alternarCategoriaNoticia = async function(cat) {
    if (!window.newsConfig.categorias) {
        window.newsConfig.categorias = ['mundo', 'economia', 'brasil', 'tecnologia'];
    }
    const idx = window.newsConfig.categorias.indexOf(cat);
    if (idx >= 0) {
        window.newsConfig.categorias.splice(idx, 1);
    } else {
        window.newsConfig.categorias.push(cat);
    }
    atualizarUINoticias();
    await salvarConfigNoticias();
};

window.alternarCotacoesNoticia = async function() {
    window.newsConfig.incluir_cotacoes = !window.newsConfig.incluir_cotacoes;
    atualizarUINoticias();
    await salvarConfigNoticias();
};

async function salvarConfigNoticias() {
    try {
        const r = await fetch('/api/news/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(window.newsConfig)
        });
        const res = await r.json();
        console.log("[NOTÍCIAS] Preferências salvas:", res);
    } catch(e) {
        console.error("[NOTÍCIAS] Falha ao salvar preferências:", e);
    }
}

function atualizarUINoticias() {
    const cats = window.newsConfig.categorias || [];
    const setBtn = (id, active) => {
        const el = document.getElementById(id);
        if (!el) return;
        const check = el.querySelector('.toggle-check');
        if (active) {
            el.classList.add('active');
            el.classList.remove('inactive');
            if (check) check.textContent = '✓';
        } else {
            el.classList.remove('active');
            el.classList.add('inactive');
            if (check) check.textContent = '';
        }
    };
    setBtn('news-toggle-mundo', cats.includes('mundo'));
    setBtn('news-toggle-cotacoes', !!window.newsConfig.incluir_cotacoes);
    setBtn('news-toggle-brasil', cats.includes('brasil'));
    setBtn('news-toggle-tecnologia', cats.includes('tecnologia'));
}

// ═══════════════════════════════════════════════════════
//  SETUP / DOWNLOAD / SHARDING
// ═══════════════════════════════════════════════════════
async function verificarSetup() {
    try {
        const r = await fetch('/system/status'); 
        const data = await r.json();
        if (!data.configurado) abrirPortalSetup();
        else if (data.download && data.download.ativo) { 
            abrirPortalSetup(); 
            mudarParaInterfaceDownload(); 
        }
    } catch(e) { 
        setTimeout(verificarSetup, 2000); 
    }
}

async function selecionarPasta(id) {
    try { 
        const r = await fetch('/system/pick_folder'); 
        const d = await r.json(); 
        if (d.path) document.getElementById(id).value = d.path; 
    } catch(e) {}
}

window.baixarModelosPesados = async function() {
    if (!confirm("Deseja iniciar o download dos modelos pesados (AirLLM 32B/72B)? Isso exigirá bastante espaço em disco e tempo.")) {
        return;
    }
    const btn = document.getElementById('btn-download-heavy');
    if (btn) btn.disabled = true;
    try {
        const r = await fetch('/system/download_heavy', { method: 'POST' });
        const d = await r.json();
        if (d.status === 'iniciado') {
            abrirPortalSetup();
            mudarParaInterfaceDownload();
        } else {
            alert(d.mensagem || "Status: " + d.status);
        }
    } catch(e) {
        alert("Erro ao solicitar download dos modelos pesados: " + e);
    } finally {
        if (btn) btn.disabled = false;
    }
};

async function abrirPortalSetup() {
    if (document.getElementById('setup-overlay')) return;
    let modelosHTML = "Carregando núcleos...";
    try {
        const r = await fetch('/system/proposed_models'); 
        const d = await r.json(); 
        const m = d.modelos;
        modelosHTML = `<div style="font-size:11px; color:#7799aa; margin-bottom:15px; text-align:left;"><b style="color:#00ffff">PERFIL:</b> ${d.perfil}<div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; margin-top:8px; border:1px solid rgba(0,255,255,0.1);">• Roteador: ${m.ROTEADOR[0]}<br>• Visão: ${m.VISAO[0]}<br>• Conversa: ${m.CONVERSA[0]}</div></div>`;
    } catch(e) {}

    const html = `<div id="setup-overlay"><div class="setup-box" id="setup-content"><h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center; font-family:'Orbitron', sans-serif;">JARVIS SETUP</h1><p style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">CONFIGURAÇÃO DE DIRETÓRIOS NEURAIS</p>${modelosHTML}<div class="setup-input-group"><label>SSD (Modelos Leves)</label><div class="setup-input-row"><input type="text" id="path-ssd" class="setup-input" placeholder="C:\\Jarvis\\Ollama"><button onclick="selecionarPasta('path-ssd')" class="setup-btn-sel">PROCURAR</button></div></div><div class="setup-input-group"><label>HD (Modelos Pesados)</label><div class="setup-input-row"><input type="text" id="path-hd" class="setup-input" placeholder="D:\\ModelosIA"><button onclick="selecionarPasta('path-hd')" class="setup-btn-sel">PROCURAR</button></div></div><button onclick="confirmarSetup()" class="setup-btn-main">CONECTAR NÚCLEOS</button><button onclick="baixarModelosPesados()" class="setup-btn-main" style="margin-top:10px; border-color:#ffaa00; color:#ffaa00;">BAIXAR MODELOS PESADOS (OPCIONAL 32B/72B)</button></div></div>`;
    document.body.insertAdjacentHTML('beforeend', html);
}

async function confirmarSetup() {
    const ssd = document.getElementById('path-ssd').value; 
    const hd = document.getElementById('path-hd').value;
    if(!ssd || !hd) return alert("Senhor, indique os caminhos dos diretórios.");
    try { 
        const r = await fetch('/system/setup', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({ ssd_path: ssd, hd_path: hd }) 
        }); 
        if((await r.json()).status === "success") mudarParaInterfaceDownload(); 
    } catch(e) { 
        alert("Erro ao confirmar setup: " + e); 
    }
}

function mudarParaInterfaceDownload() {
    const box = document.getElementById('setup-content'); 
    if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center; font-family:'Orbitron', sans-serif;">SINC NEURAL</h1><p id="dl-msg" style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">TRANSFERINDO PACOTES...</p><div id="donuts-container"></div><div class="progress-global"><div id="dl-bar-global" class="progress-bar"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#00ffff; font-family:'Orbitron', sans-serif;"><span>PROGRESSO</span><span id="dl-pct-total">0%</span></div>`;
    donutsInstanciados = false;
}

function mudarParaInterfaceSharding() {
    const box = document.getElementById('setup-content'); 
    if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#ff00ff; text-shadow:0 0 20px #ff00ff; text-align:center; font-family:'Orbitron', sans-serif;">FATIAMENTO</h1><p id="shard-msg" style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">REORGANIZANDO CAMADAS NEURAIS...</p><div id="sharding-visual"></div><div class="progress-global"><div id="shard-bar" class="progress-bar" style="background:#ff00ff;"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#ff00ff; font-family:'Orbitron', sans-serif;"><span>SHARDS</span><span id="shard-pct">0%</span></div>`;
}

let donutsInstanciados = false; 
const coresDonuts = ["#00ffff", "#ff00ff", "#00ff00", "#ffff00", "#ff8800", "#9d00ff", "#00ff88"];

function atualizarProgressoVisual(stat) {
    if (!stat || !stat.ativo) return;
    if (!document.getElementById('donuts-container')) { 
        abrirPortalSetup(); 
        mudarParaInterfaceDownload(); 
    }
    const bar = document.getElementById('dl-bar-global'); if(bar) bar.style.width = stat.progresso_total + "%";
    const pct = document.getElementById('dl-pct-total'); if(pct) pct.innerText = stat.progresso_total + "%";
    const msg = document.getElementById('dl-msg'); if(msg) msg.innerText = stat.mensagem.toUpperCase();
    if (stat.modelos && Object.keys(stat.modelos).length > 0) {
        const container = document.getElementById('donuts-container');
        if (!donutsInstanciados) {
            container.innerHTML = ""; 
            let idx = 0;
            for (const mid in stat.modelos) {
                const cor = coresDonuts[idx % coresDonuts.length]; 
                const short = mid.split('/').pop().split(':').shift();
                container.innerHTML += `<div class="donut-item"><div style="position:relative; width:60px; height:60px;"><svg width="60" height="60" viewBox="0 0 80 80"><circle cx="40" cy="40" r="34" stroke="#111" stroke-width="8" fill="none" /><circle id="circle-${mid}" cx="40" cy="40" r="34" stroke="${cor}" stroke-width="8" fill="none" stroke-dasharray="213.6" stroke-dashoffset="213.6" style="transition:0.4s; filter:drop-shadow(0 0 3px ${cor});" /></svg><div id="pct-${mid}" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:10px; font-weight:bold; color:${cor}; font-family:'Orbitron', sans-serif;">0%</div></div><div class="donut-label">${short}</div></div>`;
                idx++;
            }
            donutsInstanciados = true;
        }
        for (const mid in stat.modelos) {
            const circle = document.getElementById(`circle-${mid}`);
            if (circle) { 
                circle.style.strokeDashoffset = 213.6 - (213.6 * stat.modelos[mid] / 100); 
                document.getElementById(`pct-${mid}`).innerText = Math.round(stat.modelos[mid]) + "%"; 
            }
        }
    }
}

function atualizarShardingVisual(stat) {
    const bar = document.getElementById('shard-bar'); if(bar) bar.style.width = stat.progresso + "%";
    const pct = document.getElementById('shard-pct'); if(pct) pct.innerText = Math.round(stat.progresso) + "%";
    const msg = document.getElementById('shard-msg'); if(msg) msg.innerText = (stat.mensagem || "FATIANDO...").toUpperCase();
    const visual = document.getElementById('sharding-visual');
    if (visual) {
        const target = Math.floor((stat.progresso / 100) * 20);
        for (let i = visual.children.length; i < target; i++) {
            const layer = document.createElement('div'); 
            layer.style.width = (80 + Math.random() * 20) + "%"; 
            layer.style.height = "4px"; 
            layer.style.background = "#ff00ff"; 
            layer.style.boxShadow = "0 0 10px #ff00ff"; 
            layer.style.opacity = "0"; 
            layer.style.transition = "0.5s"; 
            visual.appendChild(layer);
            setTimeout(() => layer.style.opacity = "1", 10);
        }
    }
}

// ═══════════════════════════════════════════════════════
//  THREE.JS CORE (OTIMIZAÇÃO PESADA DE PERFORMANCE)
// ═══════════════════════════════════════════════════════
const simplex = new SimplexNoise(); 
const scene = new THREE.Scene(); 
const camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" }); 
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.getElementById('canvas-container').appendChild(renderer.domElement);

// Geometria otimizada (detalhe 5 em vez de 10 reduz vértices em mais de 75%)
const geometry = new THREE.IcosahedronGeometry(2, 5); 
const originalPositions = geometry.attributes.position.array.slice();

// Pré-cálculo dos vetores normais unitários fora do loop para eliminar Math.sqrt a cada frame
const dirNormals = new Float32Array(originalPositions.length);
for (let i = 0; i < originalPositions.length; i += 3) {
    const vx = originalPositions[i];
    const vy = originalPositions[i + 1];
    const vz = originalPositions[i + 2];
    const len = Math.sqrt(vx * vx + vy * vy + vz * vz) || 1.0;
    dirNormals[i] = vx / len;
    dirNormals[i + 1] = vy / len;
    dirNormals[i + 2] = vz / len;
}

const pointsMat = new THREE.PointsMaterial({ 
    color: 0x00ffff, 
    size: 0.055, 
    transparent: true, 
    blending: THREE.AdditiveBlending, 
    depthWrite: false 
});

const wireMat = new THREE.MeshBasicMaterial({ 
    color: 0x00ffff, 
    wireframe: true, 
    transparent: true, 
    opacity: 0.11, 
    blending: THREE.AdditiveBlending, 
    depthWrite: false 
});

function criarTexturaGlow() { 
    const size = 128; 
    const canvas = document.createElement('canvas'); 
    canvas.width = canvas.height = size; 
    const ctx = canvas.getContext('2d'); 
    const grad = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2); 
    grad.addColorStop(0, 'rgba(255,255,255,1)'); 
    grad.addColorStop(0.3, 'rgba(255,255,255,0.4)'); 
    grad.addColorStop(1, 'rgba(255,255,255,0)'); 
    ctx.fillStyle = grad; 
    ctx.fillRect(0, 0, size, size); 
    return new THREE.CanvasTexture(canvas); 
}

const glowMat = new THREE.SpriteMaterial({ 
    map: criarTexturaGlow(), 
    color: 0x00ffff, 
    transparent: true, 
    opacity: 0.65, 
    blending: THREE.AdditiveBlending 
});

const points = new THREE.Points(geometry, pointsMat); 
const sphere = new THREE.Mesh(geometry, wireMat); 
const glow = new THREE.Sprite(glowMat); 
glow.scale.set(6, 6, 1);

scene.add(points); 
scene.add(sphere); 
scene.add(glow); 
camera.position.z = 6;

let frameCount = 0;

function animate() {
    requestAnimationFrame(animate); 
    frameCount++;
    const t = Date.now() * 0.001; 
    initColors();
    if (!targetColor) return; 

    currentIntensity += (targetIntensity - currentIntensity) * 0.08; 
    patternBlend = Math.min(1.0, patternBlend + 0.08); 
    const p = getBlendedPattern(t, currentIntensity);

    points.rotation.x += p.rotX; 
    points.rotation.y += p.rotY; 
    points.rotation.z += p.rotZ; 
    sphere.rotation.copy(points.rotation);

    points.position.set(p.offsetX, p.offsetY, 0); 
    sphere.position.copy(points.position);

    // Controle de framerate inteligente:
    // Em estado 'dormindo' e sem falar, atualiza o ruído/deformação apenas a cada 2 frames
    const devePularDeformacao = (targetPattern === 'dormindo' && !falando && (frameCount % 2 !== 0));
    
    if (!devePularDeformacao) {
        const pos = geometry.attributes.position.array;
        const speed = t * p.noiseSpeed;
        const scale = p.noiseScale;
        for (let i = 0; i < pos.length; i += 3) {
            const vX = originalPositions[i];
            const vY = originalPositions[i + 1];
            const vZ = originalPositions[i + 2];
            const off = simplex.noise3D(vX + speed, vY + speed, vZ + speed) * scale;
            pos[i] = vX + dirNormals[i] * off; 
            pos[i + 1] = vY + dirNormals[i + 1] * off; 
            pos[i + 2] = vZ + dirNormals[i + 2] * off;
        }
        geometry.attributes.position.needsUpdate = true;
    }

    if (targetColor) {
        pointsMat.color.lerp(targetColor, 0.06); 
        wireMat.color.copy(pointsMat.color); 
        glowMat.color.copy(pointsMat.color);
    }

    const gs = 5 + (currentIntensity * 4); 
    glow.scale.set(gs, gs, 1); 
    renderer.render(scene, camera);
}

window.addEventListener('resize', () => { 
    camera.aspect = innerWidth / innerHeight; 
    camera.updateProjectionMatrix(); 
    renderer.setSize(innerWidth, innerHeight); 
});

animate(); 
conectarWS(); 
verificarSetup(); 
checarStatusMuteMic();

// ═══════════════════════════════════════════════════════
//  CONTROLE MANUAL DE ÁUDIO E COMANDOS (BOTÕES HUD)
// ═══════════════════════════════════════════════════════
async function pararGravacaoMic() {
    const btn = document.getElementById('btn-stop-mic');
    if (btn) {
        btn.classList.add('btn-active');
        btn.innerHTML = '<span class="btn-icon">⚡</span><span class="btn-text">ENVIANDO...</span>';
    }
    
    if (subText) {
        subText.innerText = "Interrompendo microfone e transcrevendo áudio...";
        subText.style.color = "#00ffff";
    }

    try {
        await fetch('/api/mic/stop', { method: 'POST' });
        console.log('[MIC] Parada manual solicitada via HUD.');
    } catch(e) {
        console.error('Erro ao parar gravação:', e);
    }

    setTimeout(() => {
        if (btn) {
            btn.innerHTML = '<span class="btn-icon">⏹️</span><span class="btn-text">PARAR E ENVIAR</span>';
            btn.classList.remove('btn-active');
        }
    }, 2500);
}

async function enviarComandoManual() {
    const input = document.getElementById('input-comando');
    if (!input) return;
    const texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    if (subText) {
        subText.innerText = `"${texto}"`;
        subText.style.color = "#00ffff";
        subText.scrollTop = subText.scrollHeight;
    }

    adicionarAoHistoricoLog("VOCÊ", texto);
    atualizarCardAtividade("tarefa", `Processando comando: "${texto}"`);

    try {
        await fetch('/api/comando_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: texto })
        });
        console.log('[CMD] Comando manual enviado:', texto);
    } catch(e) {
        console.error('Erro ao enviar comando manual:', e);
    }
}

async function alternarMuteMic() {
    const btn = document.getElementById('btn-mute-mic');
    if (btn) btn.disabled = true;
    try {
        const r = await fetch('/api/mic/toggle_mute', { method: 'POST' });
        const d = await r.json();
        atualizarVisualMute(d.muted);
    } catch(e) {
        console.error('Erro ao alternar microfone:', e);
    } finally {
        if (btn) btn.disabled = false;
    }
}

function atualizarVisualMute(isMuted) {
    const btn = document.getElementById('btn-mute-mic');
    const icon = document.getElementById('mute-icon');
    const text = document.getElementById('mute-text');
    if (!btn) return;

    if (isMuted) {
        btn.classList.add('mic-muted');
        if (icon) icon.innerText = '🔇';
        if (text) text.innerText = 'MUTADO';
        btn.title = 'Microfone Mutado (Clique para Ativar)';
    } else {
        btn.classList.remove('mic-muted');
        if (icon) icon.innerText = '🎤';
        if (text) text.innerText = 'MIC ATIVO';
        btn.title = 'Microfone Ativo (Clique para Mutar)';
    }
}

async function checarStatusMuteMic() {
    try {
        const r = await fetch('/api/mic/status');
        const d = await r.json();
        atualizarVisualMute(d.muted);
    } catch(e) {}
}

// ═══════════════════════════════════════════════════════
//  SISTEMA DE BRIEFING MATINAL COREOGRAFADO & CARDS HUD
// ═══════════════════════════════════════════════════════
let briefingCards = [];
let cardAtualHero = null;
let briefingTimerEncerramento = null;
let briefingPillsTimer = null;
const BRIEFING_AUTO_FECHAR_MS = 60000;

// ── MODO DE LAYOUT: esfera Mini-Core no canto quando há conteúdo no centro ──
function atualizarModoLayoutBriefing() {
    const stage = document.getElementById('briefing-stage');
    const dock = document.getElementById('briefing-dock');
    const canvas = document.getElementById('canvas-container');

    const stageVisivel = !!(stage && !stage.classList.contains('hidden') && stage.children.length > 0);
    const dockVisivel = !!(dock && !dock.classList.contains('hidden'));

    // Esfera encolhe para o canto enquanto existe um card em destaque no centro
    if (canvas) canvas.classList.toggle('canvas-mini-corner', stageVisivel);
    // Legenda inferior some enquanto houver qualquer holograma (centro ou dock)
    document.body.classList.toggle('briefing-ativo', stageVisivel || dockVisivel);
}

function agendarAutoFechamentoBriefing() {
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    briefingTimerEncerramento = setTimeout(fecharBriefingDock, BRIEFING_AUTO_FECHAR_MS);
}

function pararPillsTelemetria() {
    if (briefingPillsTimer) {
        clearInterval(briefingPillsTimer);
        briefingPillsTimer = null;
    }
}

// Move o card atual para o dock com animação FLIP (o card "encolhe e encaixa" na fileira)
function arquivarCardNoDock(card, heroEl) {
    const dock = document.getElementById('briefing-dock');
    const dockRow = document.getElementById('briefing-dock-row');
    if (!card || !dockRow) return;
    if (dock) dock.classList.remove('hidden');

    let mini = document.getElementById(`mini-${card.id}`);
    const jaExistia = !!mini;
    if (!mini) {
        mini = criarElementoMiniCard(card);
        dockRow.appendChild(mini);
    }
    dockRow.querySelectorAll('.briefing-card-mini').forEach(m => m.classList.remove('mini-ativo'));
    mini.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });

    if (!heroEl || jaExistia || typeof heroEl.animate !== 'function') {
        mini.classList.add('mini-arrived');
        return;
    }

    const from = heroEl.getBoundingClientRect();
    const to = mini.getBoundingClientRect();
    if (!from.width || !to.width) {
        mini.classList.add('mini-arrived');
        return;
    }

    const ghost = heroEl.cloneNode(true);
    ghost.removeAttribute('id');
    ghost.classList.add('hero-ghost');
    Object.assign(ghost.style, {
        left: `${from.left}px`,
        top: `${from.top}px`,
        width: `${from.width}px`,
        height: `${from.height}px`
    });
    document.body.appendChild(ghost);
    mini.style.opacity = '0';

    const dx = to.left - from.left;
    const dy = to.top - from.top;
    const sx = to.width / from.width;
    const sy = to.height / from.height;

    const anim = ghost.animate([
        { transform: 'translate(0px, 0px) scale(1, 1)', opacity: 1, filter: 'blur(0px)' },
        { transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`, opacity: 0.15, filter: 'blur(1px)' }
    ], { duration: 650, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'forwards' });

    anim.onfinish = () => {
        ghost.remove();
        mini.style.opacity = '';
        mini.classList.add('mini-arrived');
    };
}

function lidarBriefingStart(dados) {
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    pararPillsTelemetria();
    briefingCards = [];
    cardAtualHero = null;

    const dock = document.getElementById('briefing-dock');
    const dockRow = document.getElementById('briefing-dock-row');
    const stage = document.getElementById('briefing-stage');

    if (dockRow) dockRow.innerHTML = '';
    if (dock) dock.classList.add('hidden');

    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = `
            <div class="briefing-card-hero" id="hero-card-telemetry">
                <div class="card-header-row">
                    <div class="card-cat-badge">📡 TELEMETRIA MATINAL // JARVIS HUD</div>
                    <div class="card-counter-badge">${dados.hora || 'SISTEMA ATIVO'}</div>
                </div>
                <div class="telemetry-card-content">
                    <div class="telemetry-header-title">CONSOLIDANDO RADAR DE SISTEMAS...</div>
                    <p class="card-body-text">Iniciando varredura multi-fontes de sensores de meteorologia, agenda pessoal, indicadores do mercado financeiro e notícias prioritárias globais.</p>
                    <div class="telemetry-radar-pills">
                        ${(dados.etapas || []).map((etapa, idx) => `
                            <div class="radar-pill ${idx === 0 ? 'active' : ''}" id="radar-pill-${idx}">
                                <span class="pill-dot"></span>
                                <span>${etapa}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="card-footer-row">
                    <span class="card-source-tag"><span class="card-live-dot"></span>Varredura Multimodal Ativa</span>
                    <span style="font-family: var(--font-display); font-size: 9px; color: rgba(0, 255, 255, 0.7);">MARK VII OS</span>
                </div>
            </div>
        `;

        // Pílulas acendem em sequência enquanto o Jarvis fala a introdução
        let pillIdx = 0;
        const totalPills = (dados.etapas || []).length;
        briefingPillsTimer = setInterval(() => {
            pillIdx++;
            const pill = document.getElementById(`radar-pill-${pillIdx}`);
            if (!pill || pillIdx >= totalPills) {
                pararPillsTelemetria();
                return;
            }
            pill.classList.add('active');
        }, 650);
    }
    atualizarModoLayoutBriefing();
}

function lidarBriefingCardFocus(card, indice, total) {
    if (!card) return;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    pararPillsTelemetria();

    const stage = document.getElementById('briefing-stage');
    const heroAnterior = stage ? stage.querySelector('.briefing-card-hero') : null;

    // O card que acabou de ser falado encolhe e encaixa na fileira inferior
    if (cardAtualHero && cardAtualHero.id !== card.id) {
        arquivarCardNoDock(cardAtualHero, heroAnterior);
    }

    cardAtualHero = card;
    if (!briefingCards.some(c => c.id === card.id)) {
        briefingCards.push(card);
    }

    // Renderiza o novo card hero no centro da tela
    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = renderHeroCardHtml(card, indice, total);
    }
    atualizarModoLayoutBriefing();
}

function lidarBriefingEnd(dados) {
    pararPillsTelemetria();
    const stage = document.getElementById('briefing-stage');
    const heroAtual = stage ? stage.querySelector('.briefing-card-hero') : null;

    // Ao terminar, o último card também encolhe para o dock e o centro é liberado
    if (cardAtualHero) {
        arquivarCardNoDock(cardAtualHero, heroAtual);
        cardAtualHero = null;
    }
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    atualizarModoLayoutBriefing();

    // Cards permanecem enfileirados e clicáveis por 60s (ou até o usuário limpar a tela)
    agendarAutoFechamentoBriefing();
}

function escapeHtmlBriefing(txt) {
    return String(txt ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderHeroCardHtml(card, indice, total, isExpanded = false) {
    const numAtual = (indice !== undefined && indice !== null) ? indice + 1 : 1;
    const numTotal = total || briefingCards.length || 7;
    const badge = card.categoria || 'RADAR MATINAL';

    let corpo = '';

    if (card.tipo === 'clima') {
        corpo = `
            <div class="weather-hero-block">
                <div>
                    <div class="weather-main-temp">${card.temp_atual || '--'}</div>
                    <div class="weather-condition-text">${card.condicao || 'Estável'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-family: var(--font-display); font-size: 13px; color: var(--cyan); font-weight: 700;">${card.cidade || 'Passo Fundo'}</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px;">Sensação: ${card.sensacao || card.temp_atual}</div>
                </div>
            </div>
            <div class="weather-stats-grid">
                <div class="weather-stat-box">
                    <span class="weather-stat-label">FAIXA TÉRMICA</span>
                    <span class="weather-stat-val">${card.min_max || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">UMIDADE DO AR</span>
                    <span class="weather-stat-val">${card.umidade || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">VENTO</span>
                    <span class="weather-stat-val">${card.vento || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">SENSORES</span>
                    <span class="weather-stat-val" style="color: var(--green-active);">ONLINE</span>
                </div>
            </div>
        `;
    } else if (card.tipo === 'agenda') {
        const itens = card.itens || [];
        corpo = `
            <div class="card-title-text">${card.titulo || 'Agenda & Lembretes do Dia'}</div>
            <div class="agenda-items-list">
                ${itens.length > 0 ? itens.map(it => `
                    <div class="agenda-item-row">
                        <span class="agenda-time-pill">${it.horario || '--:--'}</span>
                        <span class="agenda-text-desc">${it.texto}</span>
                    </div>
                `).join('') : `
                    <div style="padding: 16px; text-align: center; color: rgba(255,255,255,0.6); font-style: italic; background: rgba(0,0,0,0.3); border-radius: 8px;">
                        Nenhum compromisso pendente registrado para hoje. Agenda livre.
                    </div>
                `}
            </div>
        `;
    } else if (card.tipo === 'mercado') {
        const cotacoes = card.cotacoes || [];
        corpo = `
            <div class="card-title-text">${card.titulo || 'Cotações & Mercado Financeiro'}</div>
            <div class="market-tickers-list">
                ${cotacoes.map(c => `
                    <div class="market-ticker-row">
                        <div class="ticker-name-box">
                            <span class="ticker-name">${c.nome}</span>
                            <span class="ticker-symbol">${c.simbolo}</span>
                        </div>
                        <div class="ticker-val-box">
                            <span class="ticker-price">${c.valor}</span>
                            <span class="ticker-var-badge ${c.alta ? 'alta' : 'baixa'}">${c.var}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        const img = card.imagem || 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80';
        const textoCorpo = card.conteudo_completo || card.resumo || '';
        const paragrafos = textoCorpo.split('\n\n').filter(p => p && p.trim().length > 0);
        const htmlParagrafos = paragrafos.length > 0 
            ? paragrafos.map(p => `<p>${escapeHtmlBriefing(p.trim())}</p>`).join('')
            : `<p>${escapeHtmlBriefing(textoCorpo)}</p>`;

        corpo = `
            <div class="card-img-wrapper">
                <img src="${escapeHtmlBriefing(img)}" alt="${escapeHtmlBriefing(card.titulo)}" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80'">
                <div class="card-img-overlay"></div>
            </div>
            <div class="card-title-text">${escapeHtmlBriefing(card.titulo)}</div>
            <div class="card-scrollable-body">
                ${htmlParagrafos}
            </div>
        `;
    }

    return `
        <div class="briefing-card-hero ${isExpanded ? 'expanded-reading' : ''}" id="hero-${card.id}">
            <div class="card-header-row">
                <div class="card-cat-badge">${badge}</div>
                <div style="display:flex; align-items:center;">
                    <div class="card-counter-badge">${numAtual} / ${numTotal}</div>
                    <button class="hero-close-btn" onclick="fecharHeroCard()" title="Recolher card para a fileira">✕</button>
                </div>
            </div>
            ${corpo}
            <div class="card-footer-row">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="card-source-tag"><span class="card-live-dot"></span>${escapeHtmlBriefing(card.fonte || card.cidade || 'JARVIS RADAR')}</span>
                    <span style="font-family: var(--font-display); font-size: 9px; color: rgba(0, 255, 255, 0.7);">${card.tipo.toUpperCase()}</span>
                </div>
                ${card.tipo === 'noticia' ? `
                    <div class="card-footer-actions">
                        <button class="btn-card-action" onclick="ouvirDetalhesCard('${escapeHtmlBriefing(card.id)}')" title="Ouvir matéria narrada em detalhes pelo Jarvis">🔊 Ouvir Detalhes</button>
                        ${card.link ? `<button class="btn-card-action btn-card-link" onclick="window.open('${escapeHtmlBriefing(card.link)}', '_blank')" title="Abrir artigo original na fonte">🌐 Ler na Fonte ↗</button>` : ''}
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function criarElementoMiniCard(card) {
    const mini = document.createElement('div');
    mini.className = 'briefing-card-mini';
    mini.id = `mini-${card.id}`;
    mini.onclick = () => reabrirCardHero(card.id);

    const catCurta = card.categoria ? card.categoria.replace('RADAR // ', '').replace('// ', '') : card.tipo.toUpperCase();

    let thumbHtml = '';
    if (card.imagem) {
        thumbHtml = `
            <div class="mini-img-thumb">
                <img src="${escapeHtmlBriefing(card.imagem)}" alt="${escapeHtmlBriefing(card.titulo)}" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80'">
            </div>
        `;
    } else if (card.tipo === 'clima') {
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main">${card.temp_atual || '--'}</div>
                <div class="mini-data-sub">${escapeHtmlBriefing(card.condicao || card.cidade || 'Clima')}</div>
            </div>
        `;
    } else if (card.tipo === 'mercado') {
        const prim = card.cotacoes && card.cotacoes.length > 0 ? card.cotacoes[0] : null;
        const corVar = prim && !prim.alta ? 'var(--red-alert)' : 'var(--green-active)';
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main" style="font-size: 15px;">${prim ? prim.valor : 'MERCADO'}</div>
                <div class="mini-data-sub">${prim ? prim.simbolo : ''} <span style="color:${corVar}; font-weight:700;">${prim ? prim.var : ''}</span></div>
            </div>
        `;
    } else if (card.tipo === 'agenda') {
        const qtd = card.itens ? card.itens.length : 0;
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main">${qtd}</div>
                <div class="mini-data-sub">${qtd === 1 ? 'compromisso pendente' : 'compromissos pendentes'}</div>
            </div>
        `;
    }

    mini.innerHTML = `
        <span class="mini-cat-label">${escapeHtmlBriefing(catCurta)}</span>
        ${thumbHtml}
        <div class="mini-title">${escapeHtmlBriefing(card.titulo)}</div>
        <div class="mini-footer">
            <span>${escapeHtmlBriefing(card.fonte || card.cidade || 'Jarvis')}</span>
            <span style="color: var(--cyan); font-weight: 700;">EXPANDIR ↗</span>
        </div>
    `;
    return mini;
}

function reabrirCardHero(cardId) {
    const card = briefingCards.find(c => c.id === cardId);
    if (!card) return;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);

    // Se havia um card em destaque que ainda não está na fileira, guarda ele antes
    const stage = document.getElementById('briefing-stage');
    if (cardAtualHero && cardAtualHero.id !== card.id && !document.getElementById(`mini-${cardAtualHero.id}`)) {
        arquivarCardNoDock(cardAtualHero, stage ? stage.querySelector('.briefing-card-hero') : null);
    }

    cardAtualHero = card;
    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = renderHeroCardHtml(card, briefingCards.indexOf(card), briefingCards.length, true);
    }
    document.querySelectorAll('#briefing-dock-row .briefing-card-mini').forEach(m => {
        m.classList.toggle('mini-ativo', m.id === `mini-${card.id}`);
    });
    atualizarModoLayoutBriefing();
    agendarAutoFechamentoBriefing();
}

window.ouvirDetalhesCard = async function(cardId) {
    const card = briefingCards.find(c => c.id === cardId);
    if (!card) return;

    const textoComando = `Jarvis, me detalhe a notícia: "${card.titulo}"`;
    adicionarAoHistoricoLog("VOCÊ", textoComando);
    atualizarCardAtividade("tarefa", `Lendo detalhes: "${card.titulo}"`);
    if (subText) {
        subText.innerText = `Lendo detalhes de: "${card.titulo}"...`;
        subText.style.color = "#00ffff";
    }

    try {
        await fetch('/api/comando_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: textoComando })
        });
    } catch(e) {
        console.error("Erro ao solicitar detalhes da notícia:", e);
    }
};

// Recolhe apenas o card central (a esfera volta ao centro, a fileira continua visível)
function fecharHeroCard() {
    const stage = document.getElementById('briefing-stage');
    if (cardAtualHero) {
        arquivarCardNoDock(cardAtualHero, stage ? stage.querySelector('.briefing-card-hero') : null);
        cardAtualHero = null;
    }
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    document.querySelectorAll('#briefing-dock-row .briefing-card-mini').forEach(m => m.classList.remove('mini-ativo'));
    atualizarModoLayoutBriefing();
    agendarAutoFechamentoBriefing();
}

// Limpa todos os hologramas e devolve a esfera majestosa ao centro
function fecharBriefingDock() {
    const dock = document.getElementById('briefing-dock');
    const stage = document.getElementById('briefing-stage');
    if (dock) dock.classList.add('hidden');
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    document.querySelectorAll('.hero-ghost').forEach(g => g.remove());
    pararPillsTelemetria();
    cardAtualHero = null;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    briefingTimerEncerramento = null;
    atualizarModoLayoutBriefing();
}

async function iniciarBriefingManual() {
    const btn = document.getElementById('btn-trigger-briefing');
    if (btn) {
        btn.classList.add('briefing-pulse');
        btn.disabled = true;
    }

    try {
        const resp = await fetch('/api/briefing/start', { method: 'POST' });
        const data = await resp.json();
        console.log('[BRIEFING] Solicitado via HUD:', data);
    } catch(e) {
        console.error('Erro ao disparar briefing:', e);
    } finally {
        setTimeout(() => {
            if (btn) {
                btn.classList.remove('briefing-pulse');
                btn.disabled = false;
            }
        }, 3000);
    }
}

// ═══════════════════════════════════════════════════════
//  SISTEMA DE AGENDA & LEMBRETES (DRAWER & MODAL)
// ═══════════════════════════════════════════════════════

async function carregarLembretes() {
    const listEl = document.getElementById('drawer-reminders-list');
    if (!listEl) return;

    try {
        const resp = await fetch('/api/reminders');
        const data = await resp.json();
        const lista = data.reminders || [];

        if (lista.length === 0) {
            listEl.innerHTML = '<div class="reminder-empty">Nenhum lembrete registrado no momento.</div>';
            return;
        }

        listEl.innerHTML = lista.map(rem => `
            <div class="reminder-item ${rem.concluido ? 'concluido' : ''}" id="rem-${rem.id}">
                <span class="reminder-check" onclick="toggleLembrete('${rem.id}')" title="Marcar como ${rem.concluido ? 'pendente' : 'concluído'}">
                    ${rem.concluido ? '☑' : '☐'}
                </span>
                <span class="reminder-texto" onclick="toggleLembrete('${rem.id}')" title="Clique para alternar status">
                    ${rem.texto}
                </span>
                ${rem.horario ? `<span class="reminder-horario">${rem.horario}</span>` : ''}
                <button class="reminder-del-btn" onclick="deletarLembrete('${rem.id}')" title="Excluir lembrete">✕</button>
            </div>
        `).join('');
    } catch(e) {
        console.error('Erro ao carregar lembretes:', e);
        listEl.innerHTML = '<div class="reminder-empty">Falha ao carregar lembretes.</div>';
    }
}

function abrirModalLembrete() {
    const modal = document.getElementById('modal-lembrete');
    if (modal) {
        modal.classList.remove('hidden');
        const input = document.getElementById('input-rem-texto');
        if (input) {
            input.value = '';
            setTimeout(() => input.focus(), 100);
        }
        const inputHora = document.getElementById('input-rem-horario');
        if (inputHora) inputHora.value = '';
    }
}

function fecharModalLembrete() {
    const modal = document.getElementById('modal-lembrete');
    if (modal) modal.classList.add('hidden');
}

async function salvarNovoLembrete() {
    const inputTexto = document.getElementById('input-rem-texto');
    const inputHora = document.getElementById('input-rem-horario');
    if (!inputTexto) return;

    const texto = inputTexto.value.trim();
    const horario = inputHora ? inputHora.value.trim() : '';

    if (!texto) {
        inputTexto.focus();
        return;
    }

    try {
        await fetch('/api/reminders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto, horario })
        });
        fecharModalLembrete();
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao salvar lembrete:', e);
    }
}

async function toggleLembrete(remId) {
    try {
        await fetch(`/api/reminders/${remId}/toggle`, { method: 'POST' });
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao alternar lembrete:', e);
    }
}

async function deletarLembrete(remId) {
    try {
        await fetch(`/api/reminders/${remId}`, { method: 'DELETE' });
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao deletar lembrete:', e);
    }
}

// ═══════════════════════════════════════════════════════
//  EXPOSIÇÃO DE MÉTODOS GLOBAIS AO WINDOW
// ═══════════════════════════════════════════════════════
window.selecionarPasta = selecionarPasta; 
window.confirmarSetup = confirmarSetup;
window.pararGravacaoMic = pararGravacaoMic;
window.enviarComandoManual = enviarComandoManual;
window.alternarMuteMic = alternarMuteMic;
window.selecionarVoz = selecionarVoz;
window.carregarConfigVoz = carregarConfigVoz;
window.alternarEfeitoJarvis = alternarEfeitoJarvis;
window.carregarConfigNoticias = carregarConfigNoticias;
window.alternarCategoriaNoticia = alternarCategoriaNoticia;
window.alternarCotacoesNoticia = alternarCotacoesNoticia;

window.lidarBriefingStart = lidarBriefingStart;
window.lidarBriefingCardFocus = lidarBriefingCardFocus;
window.lidarBriefingEnd = lidarBriefingEnd;
window.reabrirCardHero = reabrirCardHero;
window.fecharBriefingDock = fecharBriefingDock;
window.fecharHeroCard = fecharHeroCard;
window.iniciarBriefingManual = iniciarBriefingManual;
window.carregarLembretes = carregarLembretes;
window.abrirModalLembrete = abrirModalLembrete;
window.fecharModalLembrete = fecharModalLembrete;
window.salvarNovoLembrete = salvarNovoLembrete;
window.toggleLembrete = toggleLembrete;
window.deletarLembrete = deletarLembrete;

// Inicialização imediata de voz, microfone, lembretes e briefing de notícias
window.carregarConfigVoz();
window.carregarConfigNoticias();
window.carregarLembretes();
checarStatusMuteMic();



```


==================================================
 ARQUIVO: .\INTERFACE\index.html
==================================================

```text
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS CORE V5</title>
    <link rel="stylesheet" href="/INTERFACE/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>

<!-- 🌌 BARRA SUPERIOR HUD FUTURISTA -->
<header id="hud-top-bar">
    <div class="hud-brand-telemetry">
        <div class="hud-brand">
            <span class="hud-pulse-dot" id="system-status-dot"></span>
            <span class="hud-title">JARVIS</span>
            <span class="hud-divider">//</span>
            <span class="hud-sub">NEURAL CORE</span>
        </div>
        <div class="hud-badges" onclick="showGraphs(true)" title="Telemetria Neural - Clique para abrir Dashboard">
            <div class="telemetry-badge" id="badge-cpu">
                <span class="badge-label">CPU</span>
                <span class="badge-val" id="top-cpu">--%</span>
            </div>
            <div class="telemetry-badge" id="badge-gpu">
                <span class="badge-label">GPU</span>
                <span class="badge-val" id="top-gpu">--%</span>
            </div>
            <div class="telemetry-badge" id="badge-ram">
                <span class="badge-label">RAM</span>
                <span class="badge-val" id="top-ram">--%</span>
            </div>
        </div>
    </div>

    <div class="hud-top-actions">
        <!-- Menu Sistema Dropdown -->
        <div class="dropdown-wrapper">
            <button id="btn-sys-menu" class="hud-top-btn" onclick="toggleSysMenu(event)">
                <span class="btn-icon">⚙️</span> SISTEMA <span class="arrow-down">▾</span>
            </button>
            <div id="sys-dropdown" class="hud-dropdown-menu">
                <div class="dropdown-header">GESTÃO DO NÚCLEO</div>
                <button class="dropdown-item" onclick="debugSetState('setup'); closeSysMenu();">
                    <span class="item-icon">📁</span> Configurar Diretórios (Setup)
                </button>
                <button class="dropdown-item" onclick="baixarModelosPesados(); closeSysMenu();">
                    <span class="item-icon">⚡</span> Baixar Modelos Pesados (32B/72B)
                </button>
                <button class="dropdown-item" onclick="showGraphs(true); closeSysMenu();">
                    <span class="item-icon">📊</span> Telemetria Completa (HUD)
                </button>
                <div class="dropdown-divider"></div>
                <div class="dropdown-header">VOZ DO JARVIS (TTS)</div>
                <button class="dropdown-item voice-opt" id="vopt-kokoro_alex" onclick="selecionarVoz('kokoro', 'pm_alex', '🎙️ Kokoro: Alex (Local CPU)')">
                    <span class="item-icon">🎙️</span> Kokoro: Alex (Local CPU)
                </button>
                <button class="dropdown-item voice-opt" id="vopt-kokoro_dora" onclick="selecionarVoz('kokoro', 'pf_dora', '🎙️ Kokoro: Dora (Local CPU - Clara)')">
                    <span class="item-icon">🎙️</span> Kokoro: Dora (Local CPU - Clara)
                </button>
                <button class="dropdown-item voice-opt" id="vopt-kokoro_santa" onclick="selecionarVoz('kokoro', 'pm_santa', '🎙️ Kokoro: Santa (Local CPU - Grave)')">
                    <span class="item-icon">🎙️</span> Kokoro: Santa (Local CPU - Grave)
                </button>
                <button class="dropdown-item voice-opt" id="vopt-kokoro_blend" onclick="selecionarVoz('kokoro', 'blend_jarvis', '🎙️ Kokoro: Jarvis Blend (Local CPU)')">
                    <span class="item-icon">🎙️</span> Kokoro: Jarvis Blend
                </button>
                <button class="dropdown-item voice-opt selected" id="vopt-edge_antonio" onclick="selecionarVoz('edge', 'pt-BR-AntonioNeural', '⚡ Neural: Antonio (Zero CPU - Rápido)')">
                    <span class="item-icon">⚡</span> Neural: Antonio (Zero CPU - Rápido)
                </button>
                <button class="dropdown-item voice-opt" id="vopt-edge_francisca" onclick="selecionarVoz('edge', 'pt-BR-FranciscaNeural', '⚡ Neural: Francisca (Zero CPU - Rápido)')">
                    <span class="item-icon">⚡</span> Neural: Francisca (Zero CPU - Rápido)
                </button>
                <div class="dropdown-divider"></div>
                <div class="dropdown-header">PROCESSAMENTO VOCAL</div>
                <button class="dropdown-item toggle-dsp-btn active" id="btn-toggle-dsp" onclick="alternarEfeitoJarvis()" title="Ativar ou desativar efeito metálico de capacete/HUD do Jarvis">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="item-icon">🎛️</span>
                        <span id="dsp-toggle-text">Modo Stark (ON)</span>
                    </div>
                    <span class="dsp-state-badge" id="dsp-badge">ATIVO</span>
                </button>
                <div class="dropdown-divider"></div>
                <div class="dropdown-header">BRIEFING DE NOTÍCIAS</div>
                <button class="dropdown-item news-toggle active" id="news-toggle-mundo" onclick="alternarCategoriaNoticia('mundo')" title="Alternar Notícias Internacionais, EUA e Geopolítica">
                    <div class="news-item-label">
                        <span class="item-icon">🌍</span>
                        <span>Internacional & EUA</span>
                    </div>
                    <span class="toggle-check">✓</span>
                </button>
                <button class="dropdown-item news-toggle active" id="news-toggle-cotacoes" onclick="alternarCotacoesNoticia()" title="Alternar Cotações do Dólar, Euro, Bitcoin, Ibovespa e S&P 500">
                    <div class="news-item-label">
                        <span class="item-icon">📈</span>
                        <span>Mercado & Cotações</span>
                    </div>
                    <span class="toggle-check">✓</span>
                </button>
                <button class="dropdown-item news-toggle active" id="news-toggle-brasil" onclick="alternarCategoriaNoticia('brasil')" title="Alternar Notícias de Política e Brasil">
                    <div class="news-item-label">
                        <span class="item-icon">🇧🇷</span>
                        <span>Política & Brasil</span>
                    </div>
                    <span class="toggle-check">✓</span>
                </button>
                <button class="dropdown-item news-toggle active" id="news-toggle-tecnologia" onclick="alternarCategoriaNoticia('tecnologia')" title="Alternar Notícias de Tecnologia, Ciência e Inteligência Artificial">
                    <div class="news-item-label">
                        <span class="item-icon">💻</span>
                        <span>Tecnologia & IA</span>
                    </div>
                    <span class="toggle-check">✓</span>
                </button>
                <div class="dropdown-divider"></div>
                <div class="dropdown-header">DEBUG VIEWS</div>
                <button class="dropdown-item sub-item" onclick="debugSetState('home'); closeSysMenu();">
                    • Esfera Normal (Home)
                </button>
                <button class="dropdown-item sub-item" onclick="debugSetState('download'); closeSysMenu();">
                    • Interface Download
                </button>
                <button class="dropdown-item sub-item" onclick="debugSetState('sharding'); closeSysMenu();">
                    • Interface Sharding
                </button>
            </div>
        </div>

        <!-- Botão Rápido Briefing Matinal -->
        <button id="btn-trigger-briefing" class="hud-top-btn briefing-btn" onclick="iniciarBriefingManual()" title="Disparar Briefing Matinal Coreografado com Hologramas">
            <span class="btn-icon">🌅</span> BRIEFING
        </button>

        <!-- Botão Gaveta de Agentes -->
        <button id="btn-toggle-drawer" class="hud-top-btn" onclick="toggleAgentsDrawer()" title="Ver Agentes e Atividades em 2º Plano">
            <span class="btn-icon">⚡</span> AGENTES
        </button>
    </div>
</header>

<!-- ⚡ GAVETA LATERAL RETRÁTIL (AGENTES & HISTÓRICO) -->
<aside id="agents-drawer">
    <div id="drawer-handle" onclick="toggleAgentsDrawer()" title="Alternar Gaveta de Agentes">
        <span id="handle-arrow">◀</span>
        <span class="handle-text">AGENTES</span>
    </div>
    <div class="drawer-content">
        <div class="drawer-header">
            <div class="drawer-title">
                <span class="drawer-icon">⚡</span>
                <span>AGENTES NEURAIS</span>
            </div>
            <button class="drawer-close" onclick="toggleAgentsDrawer(false)">✕</button>
        </div>

        <!-- SEÇÃO 1: AGENTES E TAREFAS EM 2º PLANO -->
        <div class="drawer-section">
            <div class="section-title">ATIVIDADE EM SEGUNDO PLANO</div>
            <div id="active-agent-card" class="agent-card">
                <div class="agent-card-header">
                    <span class="agent-status-led" id="current-agent-led"></span>
                    <span class="agent-name" id="current-agent-name">Roteador Neural</span>
                    <span class="agent-tag" id="current-agent-tag">ATIVO</span>
                </div>
                <div class="agent-card-desc" id="current-agent-desc">Aguardando comandos de voz ou texto...</div>
                <div class="agent-card-time" id="current-agent-time">Agora</div>
            </div>

            <div class="agent-cards-grid">
                <div class="mini-agent-card" id="card-mcp">
                    <div class="mini-agent-title"><span>🌐</span> Web MCP</div>
                    <div class="mini-agent-status" id="status-mcp">DuckDuckGo / Wiki</div>
                </div>
                <div class="mini-agent-card" id="card-vision">
                    <div class="mini-agent-title"><span>👁️</span> Visão</div>
                    <div class="mini-agent-status" id="status-vision">Moondream Standby</div>
                </div>
                <div class="mini-agent-card" id="card-memory">
                    <div class="mini-agent-title"><span>🧠</span> Memória</div>
                    <div class="mini-agent-status" id="status-memory">ChromaDB Conectado</div>
                </div>
                <div class="mini-agent-card" id="card-sentinel">
                    <div class="mini-agent-title"><span>🛡️</span> Sentinela</div>
                    <div class="mini-agent-status" id="status-sentinel">Proteção Térmica</div>
                </div>
            </div>
        </div>

        <!-- SEÇÃO 2: AGENDA & LEMBRETES -->
        <div class="drawer-section">
            <div class="section-title-row">
                <span class="section-title">AGENDA & LEMBRETES</span>
                <button class="add-rem-btn" onclick="abrirModalLembrete()" title="Adicionar Lembrete">+ NOVO</button>
            </div>
            <div id="drawer-reminders-list" class="reminders-list">
                <div class="reminder-empty">Carregando agenda...</div>
            </div>
        </div>

        <!-- SEÇÃO 3: HISTÓRICO RECENTE DE INTERAÇÕES (LOG) -->
        <div class="drawer-section flex-grow">
            <div class="section-title-row">
                <span class="section-title">LOG DE INTERAÇÕES</span>
                <button class="clear-log-btn" onclick="limparHistoricoLog()" title="Limpar Histórico">Limpar</button>
            </div>
            <div id="drawer-history-list" class="history-list">
                <div class="history-item system">
                    <span class="history-time">BOOT</span>
                    <span class="history-sender">SISTEMA:</span>
                    <span class="history-body">Jarvis Neural Core V5 inicializado e conectado.</span>
                </div>
            </div>
        </div>
    </div>
</aside>

<!-- DASHBOARD DE HARDWARE (HUD MODAL) -->
<div id="page-graphs">
    <div style="width:100%; display:flex; justify-content:flex-end; max-width:1200px;">
        <button class="debug-btn hud-close-btn" onclick="showGraphs(false)">FECHAR HUD [X]</button>
    </div>
    <h2 style="color:#00ffff; letter-spacing:15px; margin-bottom:40px; font-weight:300; text-shadow:0 0 10px #00ffff; text-align:center;">SISTEMA NEURAL</h2>
    <div class="grid-container">
        <div class="card">
            <div class="card-title">PROCESSADOR (CPU)</div>
            <div class="metric-value"><span id="metric-cpu">0</span><span class="metric-unit">%</span></div>
            <div id="chart-cpu" class="chart-container"></div>
            <div style="font-size:11px; color:#666;" id="cpu-temp">TEMP: --°C</div>
        </div>
        <div class="card">
            <div class="card-title">ACELERAÇÃO NEURAL (GPU)</div>
            <div class="metric-value"><span id="metric-gpu">0</span><span class="metric-unit">%</span></div>
            <div id="chart-gpu" class="chart-container"></div>
            <div style="font-size:11px; color:#666;" id="gpu-stats">TEMP: --°C | VRAM: -- | PWR: --</div>
        </div>
        <div class="card">
            <div class="card-title">MEMÓRIA RAM</div>
            <div class="metric-value"><span id="metric-ram">0</span><span class="metric-unit">%</span></div>
            <div id="chart-ram" class="chart-container"></div>
        </div>
        <div class="card">
            <div class="card-title">AIRLLM (ESTIMATIVA)</div>
            <div class="metric-value">READY</div>
            <div style="font-size:11px; color:#666;">I/O: 350MB/s (SSD/HD)</div>
        </div>
    </div>
</div>

<!-- GRADE BLUEPRINT HUD (CAMADA FIXA DE TELA CHEIA, INDEPENDENTE DA ESFERA) -->
<div class="bg-blueprint-grid" aria-hidden="true"></div>

<!-- CANVAS DA ESFERA THREE.JS -->
<div id="canvas-container"></div>

<!-- 🌌 STAGE HOLOGRÁFICO DO BRIEFING MATINAL (CARDS CENTRAIS EM DESTAQUE) -->
<div id="briefing-stage" class="hidden"></div>

<!-- 🌌 DOCK INFERIOR: CARDS DE VIDRO FLUTUANTES (SEM CAIXA DE FUNDO) -->
<div id="briefing-dock" class="hidden">
    <div id="briefing-dock-row"></div>
    <button id="btn-briefing-clear" class="briefing-clear-btn" onclick="fecharBriefingDock()" title="Fechar os hologramas do briefing">✕ Limpar Tela</button>
</div>

<!-- 📋 MODAL DE NOVO LEMBRETE -->
<div id="modal-lembrete" class="modal-overlay hidden" onclick="if(event.target===this) fecharModalLembrete()">
    <div class="modal-card">
        <div class="modal-header">
            <span class="modal-title">NOVO LEMBRETE // AGENDA</span>
            <button class="drawer-close" onclick="fecharModalLembrete()">✕</button>
        </div>
        <div class="modal-body">
            <input type="text" id="input-rem-texto" class="modal-input" placeholder="O que o senhor deseja agendar/lembrar?..." onkeydown="if(event.key==='Enter') salvarNovoLembrete()">
            <input type="text" id="input-rem-horario" class="modal-input" placeholder="Horário opcional (ex: 14:30)..." onkeydown="if(event.key==='Enter') salvarNovoLembrete()">
        </div>
        <div class="modal-actions">
            <button class="modal-btn secondary" onclick="fecharModalLembrete()">CANCELAR</button>
            <button class="modal-btn primary" onclick="salvarNovoLembrete()">SALVAR LEMBRETE</button>
        </div>
    </div>
</div>

<!-- CAMADA DE LEGENDA COMPACTA (POSICIONADA ACIMA DO CONTROL DOCK) -->
<div id="ui-layer">
    <div class="label" id="status-label">Neural Core V5 Active</div>
    <div id="subtitles">INICIALIZANDO SISTEMAS...</div>
</div>

<!-- DOCK DE CONTROLE INFERIOR FLUTUANTE -->
<div id="control-bar">
    <button id="btn-mute-mic" class="hud-btn-mute" onclick="alternarMuteMic()" title="Mutar/Desmutar Microfone">
        <span class="btn-icon" id="mute-icon">🎤</span>
        <span class="btn-text" id="mute-text">MIC ATIVO</span>
    </button>
    <button id="btn-stop-mic" class="hud-btn-stop" onclick="pararGravacaoMic()" title="Interrompe o microfone e envia o áudio imediatamente">
        <span class="btn-icon">⏹️</span>
        <span class="btn-text">PARAR E ENVIAR</span>
    </button>
    <div class="input-command-wrapper">
        <input type="text" id="input-comando" placeholder="Ou digite um comando aqui..." onkeydown="if(event.key === 'Enter') enviarComandoManual()">
        <button id="btn-send-cmd" onclick="enviarComandoManual()">ENVIAR</button>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/simplex-noise/2.4.0/simplex-noise.min.js"></script>
<script src="/INTERFACE/app.js"></script>

</body>
</html>
```


==================================================
 ARQUIVO: .\INTERFACE\indexoriginal(CASO TER BUG).html
==================================================

```text
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>JARVIS CORE V5</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #000; overflow: hidden; font-family: 'Segoe UI', sans-serif; }
        #canvas-container { position: absolute; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; }
        #ui-layer { position: absolute; bottom: 8%; width: 100%; text-align: center; pointer-events: none; }
        .label    { text-transform: uppercase; letter-spacing: 5px; font-size: 14px; opacity: 0.5; transition: color 1.2s ease, text-shadow 1.2s ease; }
        #subtitles { font-size: 26px; margin-top: 10px; font-weight: 300; font-style: italic; transition: color 1.2s ease, text-shadow 1.2s ease; }

        /* 🛠️ ESTILOS DE DEBUG (TEMPORÁRIO) */
        #debug-switcher {
            position: fixed; top: 10px; left: 10px; z-index: 10000;
            display: flex; gap: 5px; background: rgba(0,0,0,0.5); padding: 5px; border-radius: 5px;
            border: 1px solid rgba(0,255,255,0.2);
        }
        .debug-btn {
            background: #222; color: #00ffff; border: 1px solid #00ffff; 
            padding: 5px 10px; font-size: 10px; cursor: pointer; border-radius: 3px;
            text-transform: uppercase; font-weight: bold;
        }
        .debug-btn:hover { background: #00ffff; color: black; }

        /* ═══════════════════════════════════════════════════════
           ESTILOS DO INSTALADOR (DONUTS E SETUP)
           ═══════════════════════════════════════════════════════ */
        #setup-overlay { 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: #050505; z-index: 9999; 
            display: flex; flex-direction: column; align-items: center; justify-content: center; 
            color: white; 
        }
        .setup-box {
            background: rgba(255,255,255,0.02); padding: 40px; border-radius: 15px; 
            border: 1px solid rgba(0,255,255,0.1); width: 620px;
        }
        .setup-input-group { margin-bottom: 20px; }
        .setup-input-group label { display: block; margin-bottom: 8px; color: #00ffff; font-size: 14px; }
        .setup-input-row { display: flex; gap: 10px; }
        .setup-input { flex: 1; background: black; border: 1px solid #333; color: white; padding: 10px; border-radius: 5px; }
        .setup-btn-sel { background: #00ffff; color: black; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .setup-btn-main { width: 100%; padding: 15px; background: transparent; border: 2px solid #00ffff; color: #00ffff; letter-spacing: 5px; font-weight: bold; cursor: pointer; border-radius: 5px; transition: 0.3s; margin-top: 20px; }
        .setup-btn-main:hover { background: #00ffff; color: black; }

        /* Container das Rosquinhas */
        #donuts-container {
            display: flex; flex-wrap: wrap; gap: 25px; justify-content: center;
            margin-top: 20px; width: 100%;
        }
        .donut-item { display: flex; flex-direction: column; align-items: center; width: 100px; }
        .donut-label { font-size: 10px; margin-top: 5px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        
        .progress-global { width: 100%; background: #111; height: 4px; border-radius: 2px; margin-top: 30px; }
        .progress-bar { width: 0%; height: 100%; background: #00ffff; box-shadow: 0 0 10px #00ffff; transition: 0.5s; }
    </style>
</head>
<body>

<!-- 🛠️ SWITCHER DE DEBUG -->
<div id="debug-switcher">
    <button class="debug-btn" onclick="debugSetState('home')">Home</button>
    <button class="debug-btn" onclick="debugSetState('setup')">Setup</button>
    <button class="debug-btn" onclick="debugSetState('download')">Download</button>
    <button class="debug-btn" onclick="debugSetState('sharding')">Sharding</button>
</div>

<div id="canvas-container"></div>
<div id="ui-layer">
    <div class="label" id="status-label">Neural Core V5 Active</div>
    <div id="subtitles">INICIALIZANDO SISTEMAS...</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/simplex-noise/2.4.0/simplex-noise.min.js"></script>
<script>

// ═══════════════════════════════════════════════════════
//  ESTADO GLOBAL (CÓDIGO ORIGINAL DO USUÁRIO)
// ═══════════════════════════════════════════════════════
const subText  = document.getElementById('subtitles');
const label    = document.getElementById('status-label');

let targetColor      = new THREE.Color('#1a0033');
let targetIntensity  = 0.1;
let currentIntensity = 0.1;
let corEstado        = '#1a0033';
let falando          = false;
let timerVolta       = null;

let currentPattern = 'dormindo';
let targetPattern  = 'dormindo';
let patternBlend   = 1.0;
let frozenPattern  = null;

// ═══════════════════════════════════════════════════════
//  PADRÕES DE MOVIMENTO (CÓDIGO ORIGINAL DO USUÁRIO - SOUL GUARD)
// ═══════════════════════════════════════════════════════
function getPatternState(name, t, intensity) {
    switch(name) {
        case 'dormindo':
            return { rotX: 0.00008, rotY: 0.0003, rotZ: 0.00005, offsetX: 0, offsetY: 0, noiseSpeed: 0.15, noiseScale: 0.3 * intensity };
        case 'ouvindo':
            return { rotX: 0.0004 + 0.0003 * Math.sin(t * 0.5), rotY: 0.002, rotZ: 0.0001, offsetX: 0.05 * Math.sin(t * 0.3), offsetY: 0.03 * Math.sin(t * 0.2), noiseSpeed: 0.3, noiseScale: 0.6 * intensity };
        case 'conversa':
            return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
        case 'hardware':
            return { rotX: 0.0, rotY: 0.006, rotZ: 0.0, offsetX: 0, offsetY: 0, noiseSpeed: 0.2, noiseScale: 0.8 * intensity };
        case 'app':
            return { rotX: 0.0001, rotY: 0.002, rotZ: 0.004, offsetX: 0, offsetY: 0, noiseSpeed: 0.5, noiseScale: 1.5 * intensity };
        case 'memoria':
            return { rotX: 0.001, rotY: 0.001, rotZ: 0.001, offsetX: 0.12 * Math.sin(t * 0.8), offsetY: 0.12 * Math.cos(t * 0.8), noiseSpeed: 0.35, noiseScale: 1.2 * intensity };
        case 'codigo':
            return { rotX: 0.003 * Math.sin(t * 0.4), rotY: 0.004, rotZ: 0.002 * Math.cos(t * 0.3), offsetX: 0, offsetY: 0, noiseSpeed: 0.6, noiseScale: 1.8 * intensity };
        case 'tarefa':
            return { rotX: 0.0015, rotY: 0.003, rotZ: 0.001, offsetX: 0, offsetY: 0, noiseSpeed: 0.25, noiseScale: 1.0 * intensity };
        case 'alerta':
            return { rotX: 0.002 * Math.sin(t * 8.0), rotY: 0.008, rotZ: 0.003 * Math.cos(t * 7.0), offsetX: 0.15 * Math.sin(t * 12.0), offsetY: 0.08 * Math.cos(t * 9.0), noiseSpeed: 1.2, noiseScale: 3.0 * intensity };
        default:
            return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
    }
}

function lerpPattern(a, b, alpha) {
    const lerp = (x, y, t) => x + (y - x) * t;
    return {
        rotX:       lerp(a.rotX,       b.rotX,       alpha),
        rotY:       lerp(a.rotY,       b.rotY,       alpha),
        rotZ:       lerp(a.rotZ,       b.rotZ,       alpha),
        offsetX:    lerp(a.offsetX,    b.offsetX,    alpha),
        offsetY:    lerp(a.offsetY,    b.offsetY,    alpha),
        noiseSpeed: lerp(a.noiseSpeed, b.noiseSpeed, alpha),
        noiseScale: lerp(a.noiseScale, b.noiseScale, alpha),
    };
}

function getBlendedPattern(t, intensity) {
    const pB = getPatternState(targetPattern, t, intensity);
    if (patternBlend >= 1.0) return pB;
    const pA = frozenPattern || getPatternState(currentPattern, t, intensity);
    return lerpPattern(pA, pB, patternBlend);
}

// ═══════════════════════════════════════════════════════
//  WEBSOCKET
// ═══════════════════════════════════════════════════════
function atualizarCorUI(hex) {
    subText.style.color      = hex;
    subText.style.textShadow = `0 0 15px ${hex}`;
    label.style.color        = hex;
    label.style.textShadow   = `0 0 10px ${hex}`;
}

let socket;
function conectarWS() {
    socket = new WebSocket('ws://' + window.location.host + '/ws');

    socket.onmessage = function(event) {
        try {
            const d = JSON.parse(event.data);
            if (d.type === "download_update") {
                // Só atualiza visualmente se o elemento existir ou se for forçado
                if (document.getElementById('donuts-container')) {
                    atualizarProgressoVisual(d.download);
                } else if (d.download.ativo && !window.setupIniciadoManualmente) {
                    // Se o download começou agora e não estamos mexendo no setup, mostra
                    atualizarProgressoVisual(d.download);
                }
                return;
            }
            if (d.type === "sharding_update") {
                if (d.sharding.ativo) {
                    if (!document.getElementById('shard-msg')) {
                        if (!document.getElementById('setup-overlay')) abrirPortalSetup();
                        mudarParaInterfaceSharding();
                    }
                    atualizarShardingVisual(d.sharding);
                } else if (document.getElementById('setup-overlay') && !window.setupIniciadoManualmente) {
                    // Se o sharding acabou, remove o overlay após um delay
                    setTimeout(() => {
                        const overlay = document.getElementById('setup-overlay');
                        if (overlay) overlay.remove();
                    }, 2000);
                }
                return;
            }
            if (d.cor) {
                corEstado = d.cor;
                targetColor.set(d.cor);
                atualizarCorUI(d.cor);
            }
            if (d.texto !== undefined) subText.innerText = d.texto;
            if (d.intensidade !== undefined) {
                targetIntensity = d.intensidade;
                if (d.intensidade > 0.15) {
                    falando = true;
                    if (timerVolta) clearTimeout(timerVolta);
                } else if (falando) {
                    falando = false;
                    timerVolta = setTimeout(() => {
                        targetColor.set(corEstado);
                        atualizarCorUI(corEstado);
                    }, 600);
                }
            }
            if (d.padrao && d.padrao !== targetPattern) {
                const tNow = Date.now() * 0.001;
                const snap = getBlendedPattern(tNow, currentIntensity);
                frozenPattern  = { ...snap };
                currentPattern = targetPattern;
                targetPattern  = d.padrao;
                patternBlend   = 0.0;
            }
        } catch(e) { console.error(e); }
    };

    socket.onclose = function() { setTimeout(conectarWS, 2000); };
    socket.onerror = function() { socket.close(); };
}
conectarWS();

// ═══════════════════════════════════════════════════════
//  🛠️ LÓGICA DE DEBUG E TRANSIÇÕES
// ═══════════════════════════════════════════════════════
window.setupIniciadoManualmente = false;

function debugSetState(state) {
    console.log("[DEBUG] Mudando para estado:", state);
    window.setupIniciadoManualmente = true; // Impede o WS de sequestrar a tela
    const overlay = document.getElementById('setup-overlay');
    
    if (state === 'home') {
        if (overlay) overlay.remove();
        targetPattern = 'dormindo';
    } else if (state === 'setup') {
        if (overlay) overlay.remove();
        abrirPortalSetup();
    } else if (state === 'download') {
        if (!overlay) abrirPortalSetup();
        setTimeout(mudarParaInterfaceDownload, 50);
    } else if (state === 'sharding') {
        if (!overlay) abrirPortalSetup();
        setTimeout(mudarParaInterfaceSharding, 50);
    }
}

// ═══════════════════════════════════════════════════════
//  FUNÇÕES DE SETUP E DOWNLOAD (DONUTS)
// ═══════════════════════════════════════════════════════
async function verificarSetup() {
    try {
        const resp = await fetch('/system/status');
        const data = await resp.json();
        if (!data.configurado) {
            abrirPortalSetup();
        } else if (data.download && data.download.ativo) {
            abrirPortalSetup();
            mudarParaInterfaceDownload();
        }
    } catch(e) { setTimeout(verificarSetup, 2000); }
}

async function selecionarPasta(idInput) {
    try {
        const resp = await fetch('/system/pick_folder');
        const data = await resp.json();
        if (data.path) document.getElementById(idInput).value = data.path;
    } catch(e) { console.error("Erro seletor:", e); }
}

async function abrirPortalSetup() {
    if (document.getElementById('setup-overlay')) return;
    
    let modelosHTML = "Carregando núcleos recomendados...";
    try {
        const resp = await fetch('/system/proposed_models');
        const data = await resp.json();
        const m = data.modelos;
        modelosHTML = `
            <div style="font-size:11px; color:#555; margin-bottom:15px; text-align:left;">
                <b style="color:#00ffff">PERFIL RECONHECIDO:</b> ${data.perfil}<br>
                <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; margin-top:8px; border:1px solid rgba(0,255,255,0.05);">
                    • Roteador Neural: ${m.ROTEADOR[0]}<br>
                    • Visão Computacional: ${m.VISAO[0]}<br>
                    • Linguagem Principal: ${m.CONVERSA[0]}
                </div>
            </div>
        `;
    } catch(e) {}

    const setupHTML = `
    <div id="setup-overlay">
        <div class="setup-box" id="setup-content">
            <h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center;">JARVIS SETUP</h1>
            <p style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">CONFIGURAÇÃO DE DIRETÓRIOS NEURAIS</p>
            
            ${modelosHTML}

            <div class="setup-input-group">
                <label>NÚCLEOS LEVES (Pasta para SSD)</label>
                <div class="setup-input-row">
                    <input type="text" id="path-ssd" class="setup-input" placeholder="Ex: C:\\Jarvis\\Ollama">
                    <button onclick="selecionarPasta('path-ssd')" class="setup-btn-sel">Escolher</button>
                </div>
            </div>

            <div class="setup-input-group">
                <label>NÚCLEOS GIGANTES (Pasta para HD)</label>
                <div class="setup-input-row">
                    <input type="text" id="path-hd" class="setup-input" placeholder="Ex: D:\\ModelosIA">
                    <button onclick="selecionarPasta('path-hd')" class="setup-btn-sel">Escolher</button>
                </div>
            </div>

            <button onclick="confirmarSetup()" class="setup-btn-main">CONECTAR NÚCLEOS</button>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', setupHTML);
}

async function confirmarSetup() {
    const ssd = document.getElementById('path-ssd').value;
    const hd = document.getElementById('path-hd').value;
    if(!ssd || !hd) return alert("Senhor, por favor indique os caminhos de destino.");
    
    try {
        const r = await fetch('/system/setup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ssd_path: ssd, hd_path: hd })
        });
        if((await r.json()).status === "success") mudarParaInterfaceDownload();
    } catch(e) { alert("Erro de conexão."); }
}

function mudarParaInterfaceDownload() {
    const box = document.getElementById('setup-content');
    if (!box) return;
    box.innerHTML = `
        <h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center;">DOWNLOAD ATIVO</h1>
        <p id="dl-msg" style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">SINCRONIZANDO NÚCLEOS NEURAIS...</p>
        
        <div id="donuts-container">
            <div style="color:#333; font-size:12px;">Aguardando sinal dos pacotes...</div>
        </div>

        <div class="progress-global">
            <div id="dl-bar-global" class="progress-bar"></div>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#00ffff; opacity:0.8;">
            <span>PROGRESSO TOTAL</span>
            <span id="dl-pct-total">0%</span>
        </div>
    `;
    donutsInstanciados = false;
}

function mudarParaInterfaceSharding() {
    const box = document.getElementById('setup-content');
    if (!box) return;
    box.innerHTML = `
        <h1 style="letter-spacing:10px; margin-bottom:10px; color:#ff00ff; text-shadow:0 0 20px #ff00ff; text-align:center;">FATIAMENTO NEURAL</h1>
        <p id="shard-msg" style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">REORGANIZANDO CAMADAS PARA PERFORMANCE...</p>
        
        <div id="sharding-visual" style="height:150px; width:100%; display:flex; flex-direction:column-reverse; align-items:center; gap:4px; overflow:hidden; margin-bottom:20px;">
            <!-- Camadas animadas via JS -->
        </div>

        <div class="progress-global">
            <div id="shard-bar" class="progress-bar" style="background:#ff00ff; box-shadow:0 0 10px #ff00ff;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#ff00ff; opacity:0.8;">
            <span>ESTABILIZANDO SHARDS</span>
            <span id="shard-pct">0%</span>
        </div>
    `;
}

const coresDonuts = ["#00ffff", "#ff00ff", "#00ff00", "#ffff00", "#ff8800", "#9d00ff", "#00ff88"];
let donutsInstanciados = false;

function atualizarProgressoVisual(stat) {
    if (!stat || !stat.ativo) return;
    
    // Se não temos a interface de download e devemos mostrar
    if (!document.getElementById('donuts-container')) {
        abrirPortalSetup();
        mudarParaInterfaceDownload();
    }

    const barGlobal = document.getElementById('dl-bar-global');
    const pctTotal = document.getElementById('dl-pct-total');
    const msgLabel = document.getElementById('dl-msg');

    if (barGlobal) barGlobal.style.width = stat.progresso_total + "%";
    if (pctTotal) pctTotal.innerText = stat.progresso_total + "%";
    if (msgLabel) msgLabel.innerText = stat.mensagem.toUpperCase();

    if (stat.modelos && Object.keys(stat.modelos).length > 0) {
        const container = document.getElementById('donuts-container');
        if (!donutsInstanciados) {
            container.innerHTML = "";
            let idx = 0;
            for (const mid in stat.modelos) {
                const cor = coresDonuts[idx % coresDonuts.length];
                const shortName = mid.split('/').pop().split(':').shift();
                container.innerHTML += `
                    <div class="donut-item">
                        <div style="position:relative; width:60px; height:60px;">
                            <svg width="60" height="60" viewBox="0 0 80 80">
                                <circle cx="40" cy="40" r="34" stroke="#111" stroke-width="8" fill="none" />
                                <circle id="circle-${mid}" cx="40" cy="40" r="34" stroke="${cor}" stroke-width="8" fill="none" 
                                        stroke-dasharray="213.6" stroke-dashoffset="213.6" stroke-linecap="round" 
                                        style="transition:0.4s; filter:drop-shadow(0 0 3px ${cor});" />
                            </svg>
                            <div id="pct-${mid}" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:10px; font-weight:bold; color:${cor};">0%</div>
                        </div>
                        <div class="donut-label">${shortName}</div>
                    </div>`;
                idx++;
            }
            donutsInstanciados = true;
        }
        for (const mid in stat.modelos) {
            const circle = document.getElementById(`circle-${mid}`);
            if (circle) {
                circle.style.strokeDashoffset = 213.6 - (213.6 * stat.modelos[mid] / 100);
                document.getElementById(`pct-${mid}`).innerText = Math.round(stat.modelos[mid]) + "%";
            }
        }
    }
}

function atualizarShardingVisual(stat) {
    const bar = document.getElementById('shard-bar');
    const pct = document.getElementById('shard-pct');
    const msg = document.getElementById('shard-msg');
    const visual = document.getElementById('sharding-visual');

    if (bar) bar.style.width = stat.progresso + "%";
    if (pct) pct.innerText = Math.round(stat.progresso) + "%";
    if (msg) msg.innerText = (stat.mensagem || "FATIANDO MODELO NEURAL...").toUpperCase();

    if (visual) {
        const numLayersExpected = 20;
        const currentLayers = visual.children.length;
        const targetLayers = Math.floor((stat.progresso / 100) * numLayersExpected);

        if (targetLayers > currentLayers) {
            for (let i = currentLayers; i < targetLayers; i++) {
                const layer = document.createElement('div');
                layer.style.width = (80 + Math.random() * 20) + "%";
                layer.style.height = "4px";
                layer.style.background = "#ff00ff";
                layer.style.boxShadow = "0 0 10px #ff00ff";
                layer.style.opacity = "0";
                layer.style.transform = "translateY(20px)";
                layer.style.transition = "0.5s";
                visual.appendChild(layer);
                setTimeout(() => {
                    layer.style.opacity = "1";
                    layer.style.transform = "translateY(0)";
                }, 10);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════
//  THREE.JS SETUP (SOUL GUARD - ORIGINAL DO USUÁRIO)
// ═══════════════════════════════════════════════════════
const container = document.getElementById('canvas-container');
const simplex   = new SimplexNoise();
const scene     = new THREE.Scene();
const camera    = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 1000);
const renderer  = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(innerWidth, innerHeight);
container.appendChild(renderer.domElement);

const geometry          = new THREE.IcosahedronGeometry(2, 10);
const originalPositions = geometry.attributes.position.array.slice();

const pointsMat = new THREE.PointsMaterial({ color: 0x00ffff, size: 0.06, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
const wireMat   = new THREE.MeshBasicMaterial({ color: 0x00ffff, wireframe: true, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false });

function criarTexturaGlow() {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
    grad.addColorStop(0,   'rgba(255,255,255,1)');
    grad.addColorStop(0.3, 'rgba(255,255,255,0.4)');
    grad.addColorStop(1,   'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}

const glowMat = new THREE.SpriteMaterial({ map: criarTexturaGlow(), color: 0x00ffff, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending });

const points = new THREE.Points(geometry, pointsMat);
const sphere = new THREE.Mesh(geometry, wireMat);
const glow   = new THREE.Sprite(glowMat);
glow.scale.set(6, 6, 1);

scene.add(points); scene.add(sphere); scene.add(glow);
camera.position.z = 6;

const renderColor = new THREE.Color('#1a0033');

// ═══════════════════════════════════════════════════════
//  LOOP DE ANIMAÇÃO (SOUL GUARD - ORIGINAL DO USUÁRIO)
// ═══════════════════════════════════════════════════════
function animate() {
    requestAnimationFrame(animate);
    const t = Date.now() * 0.001;

    currentIntensity += (targetIntensity - currentIntensity) * 0.08;
    patternBlend = Math.min(1.0, patternBlend + 0.08);

    const p = getBlendedPattern(t, currentIntensity);

    points.rotation.x += p.rotX;
    points.rotation.y += p.rotY;
    points.rotation.z += p.rotZ;
    sphere.rotation.x  = points.rotation.x;
    sphere.rotation.y  = points.rotation.y;
    sphere.rotation.z  = points.rotation.z;

    points.position.x = p.offsetX;
    points.position.y = p.offsetY;
    sphere.position.x = p.offsetX;
    sphere.position.y = p.offsetY;

    const positions = geometry.attributes.position.array;
    for (let i = 0; i < positions.length; i += 3) {
        const vX = originalPositions[i];
        const vY = originalPositions[i+1];
        const vZ = originalPositions[i+2];
        const offset = simplex.noise3D(
            vX + t * p.noiseSpeed,
            vY + t * p.noiseSpeed,
            vZ + t * p.noiseSpeed
        ) * p.noiseScale;
        const len = Math.sqrt(vX*vX + vY*vY + vZ*vZ);
        positions[i]   = vX + (vX/len) * offset;
        positions[i+1] = vY + (vY/len) * offset;
        positions[i+2] = vZ + (vZ/len) * offset;
    }
    geometry.attributes.position.needsUpdate = true;

    renderColor.lerp(targetColor, 0.06);
    pointsMat.color.copy(renderColor);
    wireMat.color.copy(renderColor);
    glowMat.color.copy(renderColor);

    const gs = 5 + (currentIntensity * 4);
    glow.scale.set(gs, gs, 1);

    renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
});

animate();
verificarSetup();
</script>
</body>
</html>
```


==================================================
 ARQUIVO: .\INTERFACE\style.css
==================================================

```text
/* ═══════════════════════════════════════════════════════
   JARVIS NEURAL CORE V5 - SCI-FI HUD DESIGN SYSTEM
   ═══════════════════════════════════════════════════════ */

:root {
    --bg-dark: #04070d;
    --cyan: #00ffff;
    --cyan-dim: rgba(0, 255, 255, 0.18);
    --cyan-glow: rgba(0, 255, 255, 0.45);
    --green-active: #00ff88;
    --red-alert: #ff0055;
    --magenta: #ff00ff;
    --font-display: 'Orbitron', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-ui: 'Rajdhani', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    background: var(--bg-dark);
    color: #e0f8ff;
    overflow: hidden;
    font-family: var(--font-ui);
    height: 100vh;
    width: 100vw;
    user-select: none;
}

/* ═══════════════════════════════════════════════════════
   1. TOP BAR HUD (BARRA SUPERIOR MINIMALISTA)
   ═══════════════════════════════════════════════════════ */
#hud-top-bar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 52px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 24px;
    z-index: 2000;
    background: linear-gradient(180deg, rgba(5, 10, 18, 0.92) 0%, rgba(5, 10, 18, 0.65) 100%);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid rgba(0, 255, 255, 0.16);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.6);
}

.hud-brand-telemetry {
    display: flex;
    align-items: center;
    gap: 22px;
}

.hud-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-display);
    letter-spacing: 2.5px;
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}

.hud-pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--cyan);
    box-shadow: 0 0 10px var(--cyan);
    animation: pulseDot 2s infinite ease-in-out;
}

@keyframes pulseDot {
    0% { transform: scale(0.9); opacity: 0.6; box-shadow: 0 0 4px var(--cyan); }
    50% { transform: scale(1.25); opacity: 1; box-shadow: 0 0 14px var(--cyan); }
    100% { transform: scale(0.9); opacity: 0.6; box-shadow: 0 0 4px var(--cyan); }
}

.hud-title {
    color: var(--cyan);
    text-shadow: 0 0 12px rgba(0, 255, 255, 0.6);
}

.hud-divider {
    color: rgba(0, 255, 255, 0.3);
    font-weight: 300;
}

.hud-sub {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.65);
    letter-spacing: 1.5px;
}

/* Badges de Telemetria */
.hud-badges {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: transform 0.2s ease;
}

.hud-badges:hover {
    transform: translateY(-1px);
}

.telemetry-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 255, 255, 0.04);
    border: 1px solid rgba(0, 255, 255, 0.18);
    border-radius: 14px;
    padding: 3px 10px;
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 1px;
    transition: all 0.25s ease;
}

.telemetry-badge:hover {
    border-color: var(--cyan);
    background: rgba(0, 255, 255, 0.12);
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.3);
}

.badge-label {
    color: rgba(0, 255, 255, 0.6);
    font-weight: 600;
}

.badge-val {
    color: #ffffff;
    font-weight: 700;
    min-width: 28px;
    text-align: right;
}

/* Ações do Top Bar */
.hud-top-actions {
    display: flex;
    align-items: center;
    gap: 12px;
}

.hud-top-btn {
    background: rgba(0, 255, 255, 0.05);
    border: 1px solid rgba(0, 255, 255, 0.22);
    color: #e0f8ff;
    padding: 6px 14px;
    border-radius: 18px;
    font-family: var(--font-display);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    outline: none;
}

.hud-top-btn:hover, .hud-top-btn.active {
    background: rgba(0, 255, 255, 0.18);
    border-color: var(--cyan);
    color: #ffffff;
    box-shadow: 0 0 14px rgba(0, 255, 255, 0.45);
}

.arrow-down {
    font-size: 8px;
    opacity: 0.7;
    margin-left: 2px;
}

/* Dropdown de Sistema */
.dropdown-wrapper {
    position: relative;
}

.hud-dropdown-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 280px;
    background: rgba(6, 12, 22, 0.96);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(0, 255, 255, 0.25);
    border-radius: 10px;
    box-shadow: 0 10px 35px rgba(0, 0, 0, 0.8), 0 0 15px rgba(0, 255, 255, 0.15);
    padding: 8px;
    display: none;
    flex-direction: column;
    gap: 3px;
    z-index: 2500;
    animation: fadeInMenu 0.2s ease-out;
}

.hud-dropdown-menu.open {
    display: flex;
}

@keyframes fadeInMenu {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
}

.dropdown-header {
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 1.5px;
    color: rgba(0, 255, 255, 0.5);
    padding: 6px 10px 4px;
    text-transform: uppercase;
}

.dropdown-item {
    background: transparent;
    border: none;
    color: #d0f0ff;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-family: var(--font-ui);
    font-weight: 600;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
}

.dropdown-item:hover {
    background: rgba(0, 255, 255, 0.15);
    color: var(--cyan);
    padding-left: 15px;
}

.dropdown-item.voice-opt {
    font-size: 11px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    letter-spacing: 0.2px;
}

.dropdown-item.voice-opt.selected {
    background: rgba(0, 255, 255, 0.2);
    border: 1px solid rgba(0, 255, 255, 0.45);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.35);
}

.dropdown-item.voice-opt.selected::after {
    content: "✓";
    color: var(--cyan);
    font-weight: 800;
    font-size: 12px;
    margin-left: 6px;
    text-shadow: 0 0 8px var(--cyan);
}

.toggle-dsp-btn {
    font-size: 11px;
    padding: 7px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    letter-spacing: 0.2px;
    border-radius: 6px;
    border: 1px solid rgba(0, 255, 255, 0.2);
    transition: all 0.25s ease;
    background: rgba(0, 255, 255, 0.05);
}

.toggle-dsp-btn.active {
    background: rgba(0, 255, 255, 0.18);
    border: 1px solid rgba(0, 255, 255, 0.6);
    color: #ffffff;
    box-shadow: 0 0 14px rgba(0, 255, 255, 0.35);
}

.toggle-dsp-btn.inactive {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #8899aa;
    box-shadow: none;
}

.dsp-state-badge {
    font-family: var(--font-display);
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: all 0.2s ease;
}

.toggle-dsp-btn.active .dsp-state-badge {
    background: rgba(0, 255, 255, 0.3);
    color: var(--cyan);
    border: 1px solid var(--cyan);
    text-shadow: 0 0 6px var(--cyan);
}

.toggle-dsp-btn.inactive .dsp-state-badge {
    background: rgba(255, 255, 255, 0.05);
    color: #778899;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Toggles de Categorias do Briefing de Notícias */
.dropdown-item.news-toggle {
    font-size: 11px;
    padding: 7px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    letter-spacing: 0.2px;
    border-radius: 6px;
    border: 1px solid rgba(0, 255, 255, 0.15);
    transition: all 0.2s ease;
    background: rgba(0, 255, 255, 0.04);
    cursor: pointer;
    margin-bottom: 3px;
    color: #e0f4f8;
}

.dropdown-item.news-toggle .news-item-label {
    display: flex;
    align-items: center;
    gap: 8px;
}

.dropdown-item.news-toggle:hover {
    border-color: rgba(0, 255, 255, 0.4);
    background: rgba(0, 255, 255, 0.1);
}

.dropdown-item.news-toggle.active {
    background: rgba(0, 255, 255, 0.16);
    border: 1px solid rgba(0, 255, 255, 0.55);
    color: #ffffff;
    box-shadow: 0 0 10px rgba(0, 255, 255, 0.22);
}

.dropdown-item.news-toggle.inactive {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #6d7f8f;
    box-shadow: none;
}

.dropdown-item.news-toggle .toggle-check {
    font-family: var(--font-display);
    font-size: 12px;
    font-weight: 800;
    color: var(--cyan);
    text-shadow: 0 0 8px var(--cyan);
    min-width: 14px;
    text-align: right;
}

.dropdown-item.news-toggle.inactive .toggle-check {
    opacity: 0;
}

.dropdown-item.sub-item {
    font-size: 11px;
    color: #88bbcc;
    padding-left: 16px;
}

.dropdown-item.sub-item:hover {
    color: #ffffff;
    background: rgba(0, 255, 255, 0.1);
}

.dropdown-divider {
    height: 1px;
    background: rgba(0, 255, 255, 0.1);
    margin: 4px 6px;
}

/* ═══════════════════════════════════════════════════════
   2. GAVETA LATERAL RETRÁTIL (AGENTES & LOG)
   ═══════════════════════════════════════════════════════ */
#agents-drawer {
    position: fixed;
    top: 52px;
    right: 0;
    bottom: 0;
    width: 360px;
    background: rgba(7, 12, 20, 0.94);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-left: 1px solid rgba(0, 255, 255, 0.25);
    z-index: 1500;
    transform: translateX(100%);
    transition: transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.35s ease;
    display: flex;
    flex-direction: column;
}

#agents-drawer.open {
    transform: translateX(0);
    box-shadow: -10px 0 40px rgba(0, 0, 0, 0.8), -2px 0 15px rgba(0, 255, 255, 0.15);
}

/* Puxador da gaveta */
#drawer-handle {
    position: absolute;
    left: -32px;
    top: 100px;
    width: 32px;
    height: 105px;
    background: rgba(7, 12, 20, 0.92);
    border: 1px solid rgba(0, 255, 255, 0.3);
    border-right: none;
    border-radius: 8px 0 0 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--cyan);
    box-shadow: -4px 0 15px rgba(0, 0, 0, 0.6);
    transition: all 0.25s ease;
}

#drawer-handle:hover {
    background: rgba(0, 255, 255, 0.15);
    color: #ffffff;
    box-shadow: -6px 0 20px rgba(0, 255, 255, 0.4);
}

#handle-arrow {
    font-size: 10px;
    transition: transform 0.3s ease;
}

#agents-drawer.open #handle-arrow {
    transform: rotate(180deg);
}

.handle-text {
    writing-mode: vertical-rl;
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 2px;
    font-weight: 700;
}

.drawer-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 16px;
    gap: 16px;
}

.drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(0, 255, 255, 0.15);
}

.drawer-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-display);
    font-size: 12px;
    letter-spacing: 2px;
    color: var(--cyan);
    font-weight: 700;
}

.drawer-close {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s ease;
}

.drawer-close:hover {
    color: var(--red-alert);
    background: rgba(255, 0, 85, 0.1);
}

.drawer-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.drawer-section.flex-grow {
    flex: 1;
    min-height: 0;
}

.section-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.section-title {
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 1.5px;
    color: rgba(0, 255, 255, 0.65);
    text-transform: uppercase;
    font-weight: 700;
}

.clear-log-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    font-size: 10px;
    cursor: pointer;
    font-family: var(--font-ui);
    transition: color 0.2s ease;
}

.clear-log-btn:hover {
    color: var(--cyan);
}

/* Card de Agente Ativo */
.agent-card {
    background: rgba(0, 255, 255, 0.04);
    border: 1px solid rgba(0, 255, 255, 0.25);
    border-radius: 10px;
    padding: 12px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
    transition: border-color 0.3s ease;
}

.agent-card.active-pulse {
    border-color: var(--cyan);
    box-shadow: 0 0 15px rgba(0, 255, 255, 0.25);
}

.agent-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}

.agent-status-led {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--green-active);
    box-shadow: 0 0 8px var(--green-active);
}

.agent-name {
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
    flex: 1;
}

.agent-tag {
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 1px;
    color: var(--green-active);
    background: rgba(0, 255, 136, 0.12);
    border: 1px solid rgba(0, 255, 136, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
}

.agent-card-desc {
    font-size: 12px;
    color: rgba(220, 240, 255, 0.75);
    line-height: 1.4;
    font-style: italic;
    word-break: break-word;
}

.agent-card-time {
    font-size: 10px;
    color: rgba(0, 255, 255, 0.4);
    text-align: right;
    margin-top: 4px;
    font-family: var(--font-display);
}

/* Grid de mini-cards de serviços */
.agent-cards-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.mini-agent-card {
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(0, 255, 255, 0.12);
    border-radius: 8px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    transition: border-color 0.2s ease;
}

.mini-agent-card:hover {
    border-color: rgba(0, 255, 255, 0.3);
}

.mini-agent-title {
    font-size: 11px;
    font-weight: 600;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 5px;
}

.mini-agent-status {
    font-size: 10px;
    color: rgba(0, 255, 255, 0.6);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Lista de Histórico */
.history-list {
    flex: 1;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(0, 255, 255, 0.1);
    border-radius: 8px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.history-item {
    font-size: 12px;
    line-height: 1.4;
    padding: 6px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.02);
    border-left: 2px solid rgba(0, 255, 255, 0.3);
    word-break: break-word;
    user-select: text;
}

.history-item.user {
    border-left-color: var(--green-active);
    background: rgba(0, 255, 136, 0.04);
}

.history-item.system {
    border-left-color: rgba(0, 255, 255, 0.5);
}

.history-time {
    font-family: var(--font-display);
    font-size: 9px;
    color: rgba(0, 255, 255, 0.45);
    margin-right: 6px;
}

.history-sender {
    font-weight: 700;
    font-size: 11px;
    margin-right: 4px;
}

.history-item.user .history-sender { color: var(--green-active); }
.history-item.system .history-sender { color: var(--cyan); }
.history-item:not(.user):not(.system) .history-sender { color: var(--cyan); }

.history-body {
    color: #e0f0ff;
}

/* ═══════════════════════════════════════════════════════
   3. CANVAS 3D & UI LAYER DE LEGENDA
   ═══════════════════════════════════════════════════════ */
#canvas-container {
    position: absolute;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1;
}

#ui-layer {
    position: absolute;
    bottom: 95px;
    left: 50%;
    transform: translateX(-50%);
    width: 90%;
    max-width: 680px;
    text-align: center;
    pointer-events: none;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.label {
    text-transform: uppercase;
    letter-spacing: 4px;
    font-size: 11px;
    font-family: var(--font-display);
    font-weight: 600;
    opacity: 0.65;
    margin-bottom: 8px;
    transition: color 1.2s ease, text-shadow 1.2s ease;
}

#subtitles {
    pointer-events: auto;
    font-size: 16px;
    line-height: 1.5;
    font-weight: 500;
    max-height: 85px;
    width: 100%;
    overflow-y: auto;
    padding: 10px 20px;
    border-radius: 14px;
    background: rgba(6, 12, 22, 0.72);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(0, 255, 255, 0.22);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.7), inset 0 0 12px rgba(0, 255, 255, 0.04);
    transition: color 1.2s ease, text-shadow 1.2s ease, border-color 0.4s ease;
    word-break: break-word;
    user-select: text;
}

/* ═══════════════════════════════════════════════════════
   4. CONTROL BAR (DOCK INFERIOR FLUTUANTE)
   ═══════════════════════════════════════════════════════ */
#control-bar {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(8, 14, 24, 0.88);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    padding: 7px 16px;
    border-radius: 40px;
    border: 1px solid rgba(0, 255, 255, 0.25);
    box-shadow: 0 6px 30px rgba(0, 0, 0, 0.75), inset 0 0 15px rgba(0, 255, 255, 0.05);
    transition: all 0.3s ease;
}

#control-bar:hover {
    border-color: rgba(0, 255, 255, 0.45);
    box-shadow: 0 8px 36px rgba(0, 255, 255, 0.2);
}

.hud-btn-mute {
    background: linear-gradient(135deg, rgba(0, 255, 136, 0.15), rgba(0, 255, 200, 0.25));
    border: 1px solid var(--green-active);
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 30px;
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 0 14px rgba(0, 255, 136, 0.4);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    outline: none;
    text-transform: uppercase;
}

.hud-btn-mute:hover {
    background: rgba(0, 255, 136, 0.3);
    box-shadow: 0 0 22px rgba(0, 255, 136, 0.8);
    transform: scale(1.03);
}

.hud-btn-mute:active {
    transform: scale(0.96);
}

.hud-btn-mute.mic-muted {
    background: linear-gradient(135deg, rgba(255, 0, 85, 0.25), rgba(255, 0, 85, 0.45));
    border: 1px solid var(--red-alert);
    color: #ffffff;
    box-shadow: 0 0 15px rgba(255, 0, 85, 0.6);
    animation: pulseMute 1.5s infinite ease-in-out;
}

.hud-btn-mute.mic-muted:hover {
    background: var(--red-alert);
    box-shadow: 0 0 25px rgba(255, 0, 85, 0.9);
}

@keyframes pulseMute {
    0% {
        box-shadow: 0 0 8px rgba(255, 0, 85, 0.4);
        border-color: rgba(255, 0, 85, 0.6);
    }
    50% {
        box-shadow: 0 0 22px rgba(255, 0, 85, 0.95);
        border-color: var(--red-alert);
    }
    100% {
        box-shadow: 0 0 8px rgba(255, 0, 85, 0.4);
        border-color: rgba(255, 0, 85, 0.6);
    }
}

.hud-btn-stop {
    background: linear-gradient(135deg, rgba(255, 45, 85, 0.25), rgba(255, 0, 60, 0.4));
    border: 1px solid var(--red-alert);
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 30px;
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 0 12px rgba(255, 0, 85, 0.35);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    outline: none;
    text-transform: uppercase;
}

.hud-btn-stop:hover {
    background: var(--red-alert);
    color: #ffffff;
    box-shadow: 0 0 25px rgba(255, 0, 85, 0.8);
    transform: scale(1.03);
}

.hud-btn-stop:active, .hud-btn-stop.btn-active {
    transform: scale(0.96);
    background: #cc0044;
}

.btn-icon {
    font-size: 13px;
    filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.4));
}

.input-command-wrapper {
    display: flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.65);
    border: 1px solid rgba(0, 255, 255, 0.2);
    border-radius: 25px;
    overflow: hidden;
    padding-left: 14px;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.input-command-wrapper:focus-within {
    border-color: var(--cyan);
    box-shadow: 0 0 14px rgba(0, 255, 255, 0.35);
}

#input-comando {
    background: transparent;
    border: none;
    outline: none;
    color: var(--cyan);
    font-size: 13px;
    font-family: var(--font-ui);
    font-weight: 500;
    width: 280px;
    padding: 8px 0;
}

#input-comando::placeholder {
    color: rgba(0, 255, 255, 0.35);
    font-style: italic;
    font-size: 12px;
}

#btn-send-cmd {
    background: rgba(0, 255, 255, 0.12);
    border: none;
    border-left: 1px solid rgba(0, 255, 255, 0.2);
    color: var(--cyan);
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 10px 18px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-transform: uppercase;
}

#btn-send-cmd:hover {
    background: var(--cyan);
    color: #000000;
    box-shadow: 0 0 16px rgba(0, 255, 255, 0.6);
}

/* ═══════════════════════════════════════════════════════
   5. DASHBOARD HUD DE GRÁFICOS (MODAL)
   ═══════════════════════════════════════════════════════ */
#page-graphs {
    position: fixed;
    inset: 0;
    z-index: 9998;
    display: none;
    padding-top: 60px;
    flex-direction: column;
    align-items: center;
    padding: 80px 20px 20px;
    overflow-y: auto;
    background: rgba(3, 7, 14, 0.88);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}

.hud-close-btn {
    background: rgba(255, 0, 85, 0.15) !important;
    border-color: var(--red-alert) !important;
    color: var(--red-alert) !important;
}

.hud-close-btn:hover {
    background: var(--red-alert) !important;
    color: #ffffff !important;
}

.debug-btn {
    background: #111;
    color: var(--cyan);
    border: 1px solid var(--cyan);
    padding: 6px 14px;
    font-size: 11px;
    font-family: var(--font-display);
    cursor: pointer;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: bold;
    transition: all 0.2s ease;
}

.debug-btn:hover {
    background: var(--cyan);
    color: black;
    box-shadow: 0 0 12px var(--cyan);
}

.grid-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
    width: 100%;
    max-width: 1200px;
}

.card {
    background: rgba(0, 255, 255, 0.03);
    border: 1px solid rgba(0, 255, 255, 0.15);
    border-radius: 12px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
}

.card-title {
    color: var(--cyan);
    font-size: 11px;
    font-family: var(--font-display);
    letter-spacing: 2px;
    text-transform: uppercase;
    opacity: 0.85;
}

.chart-container {
    height: 65px;
    position: relative;
    display: flex;
    align-items: flex-end;
    gap: 3px;
    background: rgba(0, 0, 0, 0.45);
    padding: 6px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid rgba(0, 255, 255, 0.08);
}

.chart-bar {
    flex: 1;
    background: var(--cyan);
    min-height: 2px;
    transition: height 0.3s ease;
    opacity: 0.7;
    border-radius: 1px;
}

.metric-value {
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 300;
    color: #fff;
}

.metric-unit {
    font-size: 13px;
    color: rgba(0, 255, 255, 0.6);
    margin-left: 5px;
}

/* ═══════════════════════════════════════════════════════
   6. SETUP / DOWNLOAD / SHARDING (WIZARD MODAL)
   ═══════════════════════════════════════════════════════ */
#setup-overlay { 
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%; 
    background: rgba(3, 6, 12, 0.95);
    backdrop-filter: blur(14px);
    z-index: 9999; 
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center; 
    color: white; 
}

.setup-box {
    background: rgba(10, 18, 30, 0.8);
    padding: 36px;
    border-radius: 16px; 
    border: 1px solid rgba(0, 255, 255, 0.25);
    width: 90%;
    max-width: 620px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(0, 255, 255, 0.1);
}

.setup-input-group { margin-bottom: 18px; }
.setup-input-group label { display: block; margin-bottom: 6px; color: var(--cyan); font-size: 13px; font-weight: 600; }
.setup-input-row { display: flex; gap: 10px; }
.setup-input { flex: 1; background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(0, 255, 255, 0.2); color: white; padding: 10px 14px; border-radius: 6px; font-family: var(--font-ui); font-size: 13px; outline: none; }
.setup-input:focus { border-color: var(--cyan); box-shadow: 0 0 10px rgba(0, 255, 255, 0.3); }
.setup-btn-sel { background: var(--cyan); color: black; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; font-family: var(--font-display); font-size: 11px; }
.setup-btn-main { width: 100%; padding: 14px; background: transparent; border: 2px solid var(--cyan); color: var(--cyan); letter-spacing: 4px; font-weight: bold; font-family: var(--font-display); font-size: 12px; cursor: pointer; border-radius: 6px; transition: 0.3s; margin-top: 16px; }
.setup-btn-main:hover { background: var(--cyan); color: black; box-shadow: 0 0 20px var(--cyan); }

#donuts-container {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    justify-content: center;
    margin-top: 20px;
    width: 100%;
}

.donut-item { display: flex; flex-direction: column; align-items: center; width: 100px; }
.donut-label { font-size: 10px; margin-top: 5px; color: #888; text-transform: uppercase; letter-spacing: 1px; font-family: var(--font-display); }

.progress-global { width: 100%; background: #111; height: 5px; border-radius: 3px; margin-top: 25px; overflow: hidden; }
.progress-bar { width: 0%; height: 100%; background: var(--cyan); box-shadow: 0 0 12px var(--cyan); transition: 0.4s; }

#sharding-visual {
    height: 140px;
    width: 100%;
    display: flex;
    flex-direction: column-reverse;
    align-items: center;
    gap: 4px;
    overflow: hidden;
    margin-bottom: 20px;
}

/* ═══════════════════════════════════════════════════════
   7. SCROLLBARS CUSTOMIZADAS SCI-FI
   ═══════════════════════════════════════════════════════ */
::-webkit-scrollbar {
    width: 5px;
    height: 5px;
}
::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.4);
}
::-webkit-scrollbar-thumb {
    background: rgba(0, 255, 255, 0.3);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--cyan);
}

/* ═══════════════════════════════════════════════════════
   8. HOLOGRAPHIC BLUEPRINT GRID & BRIEFING HUD SYSTEM
   ═══════════════════════════════════════════════════════ */

/* Grade blueprint em camada própria: permanece em tela cheia mesmo com a esfera minimizada */
.bg-blueprint-grid {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background-image: 
        linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
}

#canvas-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 1;
    transform-origin: center center;
    transition: transform 0.8s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.6s ease;
    will-change: transform;
}

/* Modo Mini-Core: esfera recolhida no canto superior esquerdo enquanto há conteúdo no centro */
#canvas-container.canvas-mini-corner {
    transform: translate(-38vw, -28vh) scale(0.28);
    pointer-events: none;
    z-index: 50;
}

/* Legenda inferior some enquanto os hologramas do briefing estão na tela */
#ui-layer {
    transition: opacity 0.4s ease, transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

body.briefing-ativo #ui-layer {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
    pointer-events: none;
}

body.briefing-ativo #ui-layer #subtitles {
    pointer-events: none;
}

/* Botão Top HUD Briefing */
.hud-top-btn.briefing-btn {
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.18), rgba(0, 100, 200, 0.12));
    border: 1px solid rgba(0, 255, 255, 0.45);
    color: #00ffff;
    font-weight: 700;
    letter-spacing: 1px;
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.2);
    transition: all 0.25s ease;
}

.hud-top-btn.briefing-btn:hover {
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.32), rgba(0, 100, 200, 0.22));
    border-color: #00ffff;
    box-shadow: 0 0 20px rgba(0, 255, 255, 0.45);
    transform: translateY(-1px);
}

/* ── STAGE CENTRAL DO BRIEFING (HERO CARD) ── */
#briefing-stage {
    position: fixed;
    top: 68px;
    left: 0;
    right: 0;
    bottom: 255px;
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 100;
    pointer-events: none;
    transition: opacity 0.35s ease;
}

#briefing-stage.hidden {
    display: none;
    opacity: 0;
}

@keyframes heroCardAppear {
    0% {
        opacity: 0;
        transform: scale(0.85) translateY(30px);
        filter: blur(8px);
    }
    100% {
        opacity: 1;
        transform: scale(1) translateY(0);
        filter: blur(0);
    }
}

@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 10px 40px rgba(0, 0, 0, 0.85), 0 0 25px rgba(0, 255, 255, 0.28); }
    50% { box-shadow: 0 10px 45px rgba(0, 0, 0, 0.9), 0 0 40px rgba(0, 255, 255, 0.45); }
}

.briefing-card-hero {
    width: 480px;
    max-width: 92vw;
    max-height: calc(100vh - 300px);
    overflow-y: auto;
    overflow-x: hidden;
    background: linear-gradient(160deg, rgba(10, 26, 42, 0.84) 0%, rgba(4, 12, 22, 0.90) 100%);
    border: 1px solid rgba(0, 255, 255, 0.55);
    border-radius: 14px;
    padding: 16px;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.85), 0 0 25px rgba(0, 255, 255, 0.3);
    pointer-events: auto;
    user-select: text;
    animation: heroCardAppear 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards, pulseGlow 4s infinite ease-in-out;
    display: flex;
    flex-direction: column;
    gap: 14px;
    position: relative;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 255, 255, 0.3) transparent;
}

.briefing-card-hero.expanded-reading {
    width: 580px;
    max-height: calc(100vh - 280px);
}

.briefing-card-hero.expanded-reading .card-scrollable-body {
    max-height: 320px;
}

.card-scrollable-body {
    max-height: 240px;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 8px;
    user-select: text;
    cursor: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 255, 255, 0.4) transparent;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.card-scrollable-body::-webkit-scrollbar {
    width: 5px;
}
.card-scrollable-body::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.25);
    border-radius: 4px;
}
.card-scrollable-body::-webkit-scrollbar-thumb {
    background: rgba(0, 255, 255, 0.35);
    border-radius: 4px;
}
.card-scrollable-body::-webkit-scrollbar-thumb:hover {
    background: var(--cyan);
    box-shadow: 0 0 8px var(--cyan);
}

.card-scrollable-body p {
    font-size: 13px;
    color: rgba(220, 240, 255, 0.9);
    line-height: 1.6;
    margin: 0;
    user-select: text;
}

.card-footer-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.btn-card-action {
    background: rgba(0, 255, 255, 0.08);
    border: 1px solid rgba(0, 255, 255, 0.35);
    color: var(--cyan);
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 0.8px;
    font-weight: 700;
    padding: 5px 11px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.22s ease;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    user-select: none;
}

.btn-card-action:hover {
    background: rgba(0, 255, 255, 0.22);
    border-color: var(--cyan);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.45);
    transform: translateY(-1px);
}

.btn-card-action.btn-card-link {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.85);
}

.btn-card-action.btn-card-link:hover {
    background: rgba(0, 255, 255, 0.16);
    border-color: var(--cyan);
    color: #ffffff;
}

/* Borda holográfica Stark nos cantos */
.briefing-card-hero::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
}

.card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.card-cat-badge {
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 1.5px;
    font-weight: 700;
    color: var(--cyan);
    background: rgba(0, 255, 255, 0.12);
    border: 1px solid rgba(0, 255, 255, 0.4);
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
}

.card-counter-badge {
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 1px;
    color: rgba(0, 255, 255, 0.6);
}

.card-img-wrapper {
    width: 100%;
    height: 165px;
    flex-shrink: 0;
    border-radius: 10px;
    overflow: hidden;
    position: relative;
    border: 1px solid rgba(0, 255, 255, 0.25);
    background: #020509;
}

.card-img-wrapper img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.4s ease;
}

.card-img-wrapper:hover img {
    transform: scale(1.03);
}

.card-img-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(0deg, rgba(6, 16, 28, 0.95) 0%, transparent 100%);
    pointer-events: none;
}

.card-title-text {
    font-family: var(--font-display);
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.35;
    text-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
}

.card-body-text {
    font-size: 13px;
    color: rgba(220, 240, 255, 0.85);
    line-height: 1.5;
}

.card-footer-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 6px;
    border-top: 1px solid rgba(0, 255, 255, 0.12);
    font-size: 11px;
}

.card-source-tag {
    color: rgba(0, 255, 255, 0.7);
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.card-live-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--green-active);
    box-shadow: 0 0 8px var(--green-active);
    margin-right: 5px;
}

/* ── LAYOUT ESPECIAL CLIMA ── */
.weather-hero-block {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: rgba(0, 255, 255, 0.05);
    border: 1px solid rgba(0, 255, 255, 0.25);
    border-radius: 10px;
}

.weather-main-temp {
    font-family: var(--font-display);
    font-size: 38px;
    font-weight: 800;
    color: #00ffff;
    text-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
    line-height: 1;
}

.weather-condition-text {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.9);
    margin-top: 4px;
}

.weather-stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 4px;
}

.weather-stat-box {
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(0, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.weather-stat-label {
    font-size: 10px;
    color: rgba(0, 255, 255, 0.6);
    font-family: var(--font-display);
    letter-spacing: 1px;
}

.weather-stat-val {
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}

/* ── LAYOUT ESPECIAL MERCADO ── */
.market-tickers-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.market-ticker-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(0, 255, 255, 0.15);
    border-radius: 8px;
    transition: border-color 0.2s ease;
}

.market-ticker-row:hover {
    border-color: rgba(0, 255, 255, 0.4);
}

.ticker-name-box {
    display: flex;
    flex-direction: column;
}

.ticker-name {
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
}

.ticker-symbol {
    font-size: 10px;
    color: rgba(0, 255, 255, 0.5);
    font-family: var(--font-display);
}

.ticker-val-box {
    display: flex;
    align-items: center;
    gap: 10px;
}

.ticker-price {
    font-family: var(--font-display);
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}

.ticker-var-badge {
    font-family: var(--font-display);
    font-size: 10px;
    font-weight: 700;
    padding: 3px 6px;
    border-radius: 4px;
    letter-spacing: 0.5px;
}

.ticker-var-badge.alta {
    background: rgba(0, 255, 136, 0.15);
    color: var(--green-active);
    border: 1px solid rgba(0, 255, 136, 0.4);
}

.ticker-var-badge.baixa {
    background: rgba(255, 0, 85, 0.15);
    color: var(--red-alert);
    border: 1px solid rgba(255, 0, 85, 0.4);
}

/* ── LAYOUT ESPECIAL AGENDA ── */
.agenda-items-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.agenda-item-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: rgba(0, 0, 0, 0.45);
    border: 1px solid rgba(0, 255, 255, 0.18);
    border-radius: 8px;
}

.agenda-time-pill {
    font-family: var(--font-display);
    font-size: 10px;
    font-weight: 700;
    color: var(--cyan);
    background: rgba(0, 255, 255, 0.12);
    border: 1px solid rgba(0, 255, 255, 0.35);
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 1px;
}

.agenda-text-desc {
    font-size: 13px;
    color: #ffffff;
    flex: 1;
}

/* ── CARD DE TELEMETRIA MATINAL (FASE 1) ── */
.telemetry-card-content {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.telemetry-header-title {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 800;
    color: #00ffff;
    letter-spacing: 2px;
    text-shadow: 0 0 15px rgba(0, 255, 255, 0.6);
}

.telemetry-radar-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 6px;
}

.radar-pill {
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 1.2px;
    padding: 5px 10px;
    border-radius: 20px;
    background: rgba(0, 255, 255, 0.08);
    border: 1px solid rgba(0, 255, 255, 0.25);
    color: rgba(220, 245, 255, 0.7);
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.3s ease;
}

.radar-pill .pill-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: rgba(0, 255, 255, 0.4);
}

.radar-pill.active {
    background: rgba(0, 255, 255, 0.25);
    border-color: #00ffff;
    color: #ffffff;
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.4);
}

.radar-pill.active .pill-dot {
    background: var(--cyan);
    box-shadow: 0 0 8px var(--cyan);
}

/* ── DOCK INFERIOR DE CARDS ARQUIVADOS (SEM CAIXA: CARDS DE VIDRO FLUTUANTES) ── */
#briefing-dock {
    position: fixed;
    bottom: 82px;
    left: 24px;
    right: 24px;
    z-index: 120;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    padding: 0;
    pointer-events: none;
}

#briefing-dock.hidden {
    display: none;
}

@keyframes dockFadeIn {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Botão discreto "Limpar Tela" flutuando à direita da fileira */
.briefing-clear-btn {
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.06), rgba(0, 255, 255, 0.03));
    backdrop-filter: blur(14px) saturate(150%);
    -webkit-backdrop-filter: blur(14px) saturate(150%);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: rgba(220, 245, 255, 0.65);
    font-family: var(--font-display);
    font-size: 9px;
    letter-spacing: 1.2px;
    cursor: pointer;
    transition: all 0.25s ease;
}

.briefing-clear-btn:hover {
    color: #ffffff;
    border-color: rgba(255, 0, 85, 0.6);
    background: rgba(255, 0, 85, 0.14);
    box-shadow: 0 0 14px rgba(255, 0, 85, 0.3);
}

#briefing-dock-row {
    display: flex;
    justify-content: center;
    align-items: flex-end;
    gap: 14px;
    overflow-x: auto;
    overflow-y: visible;
    padding: 8px 4px 4px 4px;
    margin: 0 120px;
    pointer-events: auto;
    scrollbar-width: thin;
}

/* Centraliza quando cabe e permite rolagem sem cortar o 1º card quando não cabe */
#briefing-dock-row > .briefing-card-mini:first-child { margin-left: auto; }
#briefing-dock-row > .briefing-card-mini:last-child  { margin-right: auto; }

.briefing-card-mini {
    width: 200px;
    min-width: 200px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.07) 0%, rgba(0, 255, 255, 0.03) 100%);
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-top: 1px solid rgba(0, 255, 255, 0.38);
    border-radius: 14px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
    padding: 10px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.25s ease, box-shadow 0.35s ease, opacity 0.3s ease;
    position: relative;
    overflow: hidden;
}

/* Reflexo de vidro no topo do card */
.briefing-card-mini::before {
    content: "";
    position: absolute;
    top: 0;
    left: 12%;
    right: 12%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.7), transparent);
    pointer-events: none;
}

.briefing-card-mini.mini-arrived {
    animation: miniDockPulse 0.6s ease-out;
}

@keyframes miniDockPulse {
    0%   { box-shadow: 0 0 0 rgba(0, 255, 255, 0), 0 8px 32px rgba(0, 0, 0, 0.45); }
    40%  { box-shadow: 0 0 22px rgba(0, 255, 255, 0.55), 0 8px 32px rgba(0, 0, 0, 0.45); }
    100% { box-shadow: 0 0 0 rgba(0, 255, 255, 0), 0 8px 32px rgba(0, 0, 0, 0.45); }
}

.briefing-card-mini:hover {
    border-color: rgba(255, 255, 255, 0.25);
    border-top-color: #00ffff;
    transform: translateY(-4px);
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.55), 0 0 18px rgba(0, 255, 255, 0.28);
}

.briefing-card-mini.mini-ativo {
    border-top-color: #00ffff;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 14px rgba(0, 255, 255, 0.35);
}

/* Fantasma usado na animação FLIP (hero -> dock) */
.hero-ghost {
    position: fixed !important;
    margin: 0 !important;
    z-index: 400 !important;
    pointer-events: none !important;
    animation: none !important;
    transform-origin: top left;
    overflow: hidden !important;
}

.mini-cat-label {
    font-family: var(--font-display);
    font-size: 8px;
    letter-spacing: 1px;
    color: var(--cyan);
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.mini-img-thumb,
.mini-data-thumb {
    width: 100%;
    height: 70px;
    border-radius: 8px;
    overflow: hidden;
    flex-shrink: 0;
}

.mini-img-thumb {
    background: #020509;
}

.mini-data-thumb {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 2px;
    background: rgba(0, 255, 255, 0.06);
    border: 1px solid rgba(0, 255, 255, 0.16);
    text-align: center;
}

.mini-data-main {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 800;
    color: var(--cyan);
    text-shadow: 0 0 10px rgba(0, 255, 255, 0.45);
}

.mini-data-sub {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.7);
}

.mini-img-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

/* Botão fechar no cabeçalho do card hero */
.hero-close-btn {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.55);
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-size: 10px;
    cursor: pointer;
    margin-left: 8px;
    transition: all 0.2s ease;
}

.hero-close-btn:hover {
    color: #ffffff;
    border-color: var(--red-alert);
    background: rgba(255, 0, 85, 0.15);
}

.mini-title {
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.mini-footer {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: rgba(0, 255, 255, 0.5);
    margin-top: 2px;
}

/* ── MODAL E GAVETA DE LEMBRETES ── */
.reminders-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 220px;
    overflow-y: auto;
}

.reminder-empty {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.4);
    font-style: italic;
    padding: 8px 0;
}

.reminder-item {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(0, 255, 255, 0.15);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 11px;
    transition: all 0.2s ease;
}

.reminder-item:hover {
    border-color: rgba(0, 255, 255, 0.35);
}

.reminder-item.concluido {
    opacity: 0.5;
    text-decoration: line-through;
}

.reminder-check {
    cursor: pointer;
    color: var(--cyan);
    font-weight: 800;
    font-size: 12px;
}

.reminder-texto {
    flex: 1;
    color: #ffffff;
    word-break: break-word;
}

.reminder-horario {
    font-family: var(--font-display);
    font-size: 9px;
    color: rgba(0, 255, 255, 0.7);
    background: rgba(0, 255, 255, 0.08);
    padding: 2px 5px;
    border-radius: 4px;
}

.reminder-del-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.3);
    cursor: pointer;
    font-size: 11px;
    transition: color 0.2s ease;
}

.reminder-del-btn:hover {
    color: var(--red-alert);
}

.add-rem-btn {
    background: rgba(0, 255, 255, 0.1);
    border: 1px solid rgba(0, 255, 255, 0.35);
    color: var(--cyan);
    font-family: var(--font-display);
    font-size: 9px;
    padding: 2px 7px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.add-rem-btn:hover {
    background: rgba(0, 255, 255, 0.25);
    box-shadow: 0 0 8px rgba(0, 255, 255, 0.35);
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    z-index: 3000;
    display: flex;
    justify-content: center;
    align-items: center;
}

.modal-overlay.hidden {
    display: none;
}

.modal-card {
    width: 360px;
    max-width: 90vw;
    background: rgba(8, 20, 32, 0.95);
    border: 1px solid var(--cyan);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-title {
    font-family: var(--font-display);
    font-size: 12px;
    color: var(--cyan);
    letter-spacing: 1.5px;
    font-weight: 700;
}

.modal-input {
    width: 100%;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(0, 255, 255, 0.25);
    border-radius: 6px;
    color: #ffffff;
    padding: 10px 12px;
    font-family: var(--font-ui);
    font-size: 13px;
    outline: none;
    margin-bottom: 8px;
}

.modal-input:focus {
    border-color: var(--cyan);
    box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
}

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}

.modal-btn {
    padding: 8px 16px;
    border-radius: 6px;
    font-family: var(--font-display);
    font-size: 10px;
    letter-spacing: 1px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s ease;
}

.modal-btn.primary {
    background: rgba(0, 255, 255, 0.2);
    border: 1px solid var(--cyan);
    color: #ffffff;
}

.modal-btn.primary:hover {
    background: var(--cyan);
    color: #000000;
    box-shadow: 0 0 12px var(--cyan);
}

.modal-btn.secondary {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.7);
}

.modal-btn.secondary:hover {
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.5);
}

/* ── RESPONSIVO: DOCK FLUTUANTE EM TELAS ESTREITAS ── */
@media (max-width: 900px) {
    #briefing-dock-row {
        margin: 0;
    }
    .briefing-clear-btn {
        top: -34px;
        transform: none;
    }
    #canvas-container.canvas-mini-corner {
        transform: translate(-36vw, -30vh) scale(0.32);
    }
}


```


==================================================
 ARQUIVO: .\MODULOS\__init__.py
==================================================

```python
# Arquivo de inicialização do pacote MODULOS

```


==================================================
 ARQUIVO: .\MODULOS\brain\airllm_module.py
==================================================

```python
"""
airllm_module.py
────────────────
Fornece uma interface lazy-loaded para modelos grandes via AirLLM,
possibilitando rodar LLMs imensos (como 70B ou 72B) e repassando o gargalo
da VRAM para o I/O de disco.
"""

import sys
import os

# Flag global para manter a instância do modelo aquecida e não instanciar mais de uma vez
_airllm_instance = None
# Guarda o nome do último modelo carregado pra evitar recarregar se for o mesmo
_loaded_model_id = None

def _inicializar_airllm(model_id: str):
    """Inicializa o AirLLM Llama/Qwen de forma preguiçosa (apenas quando solicitado)."""
    global _airllm_instance, _loaded_model_id
    
    # Se já temos um modelo carregado mas é DIFERENTE do que o solicitado agora,
    # precisamos deletar o antigo para liberar a VRAM/RAM (Híbrido SSD/HD)
    if _airllm_instance is not None and _loaded_model_id != model_id:
        print(f"[AIRLLM] Trocando modelo: {_loaded_model_id} -> {model_id}. Limpando memória...")
        del _airllm_instance
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        _airllm_instance = None

    # Se o modelo já está carregado e é o mesmo solicitado, retorna a instância existente
    if _airllm_instance is not None and _loaded_model_id == model_id:
        return _airllm_instance
        
    # --- ESTRATÉGIA DE PERFORMANCE MÁXIMA (HÍBRIDA) ---
    # Original (64GB+) fica no HD para não lotar o PC.
    # Fatias Shards (20GB) ficam no SSD para a IA falar RÁPIDO.
    from MODULOS.system.config import carregar_configuracao
    cfg = carregar_configuracao()
    hd_path = cfg.get("hd_path", "D:\\ModelosIA") if cfg else "D:\\ModelosIA"
    ssd_path = cfg.get("ssd_path", os.path.expanduser("~/.cache/huggingface")) if cfg else os.path.expanduser("~/.cache/huggingface")

    # Sempre buscamos o modelo original no HD para economizar SSD
    os.environ["HF_HOME"] = hd_path
    
    if "72B" in model_id:
        print(f"[AIRLLM] Modo 72B: Tudo no HD ({hd_path}) devido ao tamanho extremo.")
        shards_path = None # Fica tudo no HD
    else:
        # Para o modelo de Código (32B), queremos velocidade SSD nas fatias!
        print(f"[AIRLLM] Modo Performance: Lendo original do HD ({hd_path}) e usando fatias no SSD ({ssd_path})")
        shards_path = os.path.join(ssd_path, "jarvis_shards_32b")
        if not os.path.exists(shards_path):
            os.makedirs(shards_path, exist_ok=True)

    print(f"\n[AIRLLM] Inicializando AirLLM pela primeira vez...")
    print(f"[AIRLLM] Carregando camadas do modelo: {model_id}")
    print(f"[AIRLLM] Isso pode demorar bastante e usar muito espaço em disco (cache HuggingFace).")
    
    try:
        from airllm import AutoModel
        
        # Inicializa com quantização 4-bit para poupar RAM e disco
        # prefetching=True acelera o processo sobrepondo cópia pro disco e cálculo
        _airllm_instance = AutoModel.from_pretrained(
            model_id,
            compression='4bit', 
            profiling_mode=False,
            max_seq_len=2048, # Aumentado de 512 para 2048 para suportar codigos longos
            layer_shards_saving_path=shards_path # Salva o processamento pesado no HD
        )
        _loaded_model_id = model_id
        
        print("[AIRLLM] Modelo carregado com sucesso.\n")
        return _airllm_instance
        
    except ImportError:
        print("[AIRLLM ERRO] airllm não está instalado. Use: pip install airllm bitsandbytes")
        return None
    except Exception as e:
        print(f"[AIRLLM ERRO] Falha crítica ao inicializar modelo: {e}")
        return None


def gerar_resposta_airllm(model_id: str, prompt: str, system_prompt: str = "") -> str:
    """
    Função exposta síncrona para ser chamada com asyncio.to_thread(...).
    Ao rodar, ele acorda o AirLLM (se ainda não estiver acordado).
    """
    modelo = _inicializar_airllm(model_id)
    if modelo is None:
        return "[ERRO INTERNO] Não foi possível carregar o assistente avançado de disco."
        
    try:
        texto_final = system_prompt + "\n\n" + prompt if system_prompt else prompt
        
        # O AirLLM usa a API parecida com a do transformers
        input_tokens = modelo.tokenizer(
            [texto_final],
            return_tensors="pt",
            return_attention_mask=True,
            truncation=True,
            max_length=2048, # Contexto máximo (ajuste se precisar de mais para programação)
            padding=False
        )
        
        # Rodando na GPU
        print("[AIRLLM] Gerando reposta (Lendo camadas do disco)...")
        generation_output = modelo.generate(
            input_tokens['input_ids'].cuda(),
            attention_mask=input_tokens['attention_mask'].cuda(),
            max_new_tokens=1000, # Quantidade maxima de tokens de resposta
            use_cache=True,
            return_dict_in_generate=True
        )
        
        # O resultado é uma lista seq
        output_ids = generation_output.sequences[0]
        
        # Remover os tokens do prompt inicial do output gerado para não ser um eco
        input_length = input_tokens['input_ids'].shape[1]
        resposta_tokens = output_ids[input_length:]
        
        # Decodificar texto final 
        resposta_texto = modelo.tokenizer.decode(resposta_tokens, skip_special_tokens=True)
        return resposta_texto.strip()
        
    except Exception as e:
        print(f"[AIRLLM EXECUCTION ERROR] {e}")
        return f"[ERRO AirLLM Geração] {e}"

```


==================================================
 ARQUIVO: .\MODULOS\brain\nlp_processor.py
==================================================

```python
try:
    from rapidfuzz import utils
    _limpar_texto = utils.default_process
except ImportError:
    _limpar_texto = lambda s: s.lower().strip()

# Dicionário focado em corrigir o que o Whisper ouve errado
DICIONARIO_CORRECAO = {
    "aprei": "abrir", "abri": "abrir", "abre": "abrir", "apear": "abrir",
    "painel amd": "radeonsofiwre", "adrenalina": "radeonsofiwre",
    "fúzeo": "fusion", "ópera": "opera", "fogo no fox": "firefox",
    "cepeu": "cpu", "gepeu": "gpu", "code": "qual", "quanto": "qual",
    "rano": "ram", "pirâmide": "hardware"
}

def normalizar_fonetica(comando_voz: str) -> str:
    """Aplica correção fonética para termos que o Whisper frequentemente transcreve errado."""
    if not comando_voz:
        return ""
    palavras = comando_voz.lower().split()
    for i, p in enumerate(palavras):
        if p in DICIONARIO_CORRECAO: 
            palavras[i] = DICIONARIO_CORRECAO[p]
    return " ".join(palavras)

def processar_intencao(comando_voz):
    # 1. Normalização e Correção Fonética
    texto = normalizar_fonetica(comando_voz)

    # --- FILTRO DE SEGURANÇA: MEMÓRIA DE FATO ---
    # Se o senhor estiver mandando "guardar", "lembrar" ou "esquecer", 
    # forçamos a rota de CONVERSA para o main.py tratar como SQL.
    gatilhos_sql = ["guarde", "salve", "anote", "lembre", "grave", "recorde"]
    if any(x in texto for x in gatilhos_sql):
        return "CONVERSA", texto

    # 2. Gatilhos de HARDWARE (Melhorado para não ser "guloso")
    palavras_hw_diretas = ["temperatura", "status", "hardware", "cpu", "gpu", "vram", "processador"]
    
    # Ele só entra em Hardware pela palavra "memória" se houver contexto de monitoramento
    contexto_monitor = ["uso", "quanto", "status", "porcentagem", "tá", "esta"]
    pediu_hardware = any(x in texto for x in palavras_hw_diretas)
    pediu_ram = "ram" in texto or ("memória" in texto and any(m in texto for m in contexto_monitor))

    if pediu_hardware or pediu_ram:
        foco = "tudo"
        if "cpu" in texto or "processador" in texto: foco = "cpu"
        elif "gpu" in texto or "placa" in texto: foco = "gpu"
        elif "ram" in texto or "memória" in texto: foco = "ram"
        return "HARDWARE", foco

    # 3. Gatilhos de ABRIR_APP
    gatilhos_abrir = ["abrir", "iniciar", "executar", "lançar", "abre", "start"]
    if any(x in texto for x in gatilhos_abrir):
        alvo = _limpar_texto(texto)
        termos_limpeza = gatilhos_abrir + ["o ", "a ", "por favor", "meu", "minha"]
        for v in termos_limpeza:
            alvo = alvo.replace(v, "")
        return "ABRIR_APP", alvo.strip()

    # 4. Gatilhos de VISÃO
    palavras_visao = ["olha", "vê", "tela", "mostra", "analisa"]
    if any(x in texto for x in palavras_visao):
        return "VISAO", texto

    # 5. CONVERSA (Padrão)
    return "CONVERSA", texto

```


==================================================
 ARQUIVO: .\MODULOS\brain\task_manager.py
==================================================

```python

```


==================================================
 ARQUIVO: .\MODULOS\brain\__init__.py
==================================================

```python
import asyncio
from MODULOS.skills import actions_module
from MODULOS.skills import hardware_module
from MODULOS.skills import vision_module
from MODULOS.skills import fii_monitor
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.system.logger import log

from MODULOS.brain.core.router import rotear_intencao
from MODULOS.brain.memory.handler import _processar_memoria
from MODULOS.brain.core.conversation import gerar_resposta_conversa
from MODULOS.brain.core.executor import _executar_em_background

async def processar_comando(texto_bruto: str):
    if not texto_bruto or not texto_bruto.strip():
        return "#00ffff", "conversa", None

    decisao   = await rotear_intencao(texto_bruto)
    categoria = decisao.get("categoria", "CONVERSA")
    alvo      = decisao.get("alvo")

    log.info(f"Roteador - Categoria: {categoria} | Alvo: {alvo}")

    if categoria == "HARDWARE":
        cor      = "#ffff00"
        padrao   = "hardware"
        resposta = await hardware_module.obter_status_hardware(foco=alvo)

    elif categoria == "ABRIR_APP":
        cor      = "#00ff00"
        padrao   = "app"
        resposta = actions_module.executar_comando(alvo)

    elif categoria == "MEMORIA":
        cor      = "#ff8800"
        padrao   = "memoria"
        resposta = await _processar_memoria(texto_bruto)
        
    elif categoria == "VISAO":
        cor      = "#9400D3"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Analisando tela...", padrao=padrao)
        loop = asyncio.get_running_loop()
        resposta = await loop.run_in_executor(
            None,
            vision_module.analisar_tela,
            texto_bruto
        )

    elif categoria == "TAREFA_LONGA":
        cor      = "#ff00ff"
        padrao   = "tarefa"
        resposta = f"Entendido, senhor. Iniciando tarefa complexa em segundo plano: '{alvo}'."
        asyncio.create_task(_executar_em_background(alvo))

    elif categoria == "CODIGO":
        cor      = "#3366ff"
        padrao   = "codigo"
        resposta = await gerar_resposta_conversa(texto_bruto, especialidade="CODIGO")

    elif categoria == "FINANCE":
        cor      = "#00ffcc"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Consultando mercado...", padrao=padrao)
        loop = asyncio.get_running_loop()
        resposta = await loop.run_in_executor(None, fii_monitor.obter_resumo_fiis)

    elif categoria == "BRIEFING":
        cor      = "#00e5ff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Iniciando Briefing Matinal...", padrao=padrao)
        from MODULOS.skills import briefing_module
        asyncio.create_task(briefing_module.executar_briefing_coreografado())
        resposta = None

    elif categoria == "BRIEFING_FOLLOWUP":
        cor      = "#00ffff"
        padrao   = "conversa"
        await atualizar_jarvis(cor_hex=cor, texto="Aprofundando detalhes...", padrao="tarefa")
        from MODULOS.skills import briefing_module
        resposta = await briefing_module.responder_followup_briefing(texto_bruto)

    elif categoria == "LEMBRETES":
        cor      = "#ffaa00"
        padrao   = "conversa"
        from MODULOS.skills import reminders_module
        resposta = reminders_module.processar_comando_voz(texto_bruto)

    elif categoria == "WEB_MCP":
        cor      = "#0088ff"
        padrao   = "tarefa"
        await atualizar_jarvis(cor_hex=cor, texto="Conectando à rede / MCP...", padrao=padrao)
        from MODULOS.skills import mcp_client
        resposta = await mcp_client.executar_comandos_mcp_ou_web(texto_bruto)

    else:
        cor      = "#00ffff"
        padrao   = "conversa"
        resposta = await gerar_resposta_conversa(texto_bruto, especialidade="CONVERSA")

    return cor, padrao, resposta

```


==================================================
 ARQUIVO: .\MODULOS\brain\core\conversation.py
==================================================

```python
import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_short
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log

SYSTEM_PROMPT_BASE = (
    "Você é o Jarvis, um assistente de inteligência artificial de elite, leal, eficiente, inteligente e elegante.\n"
    "Responda ao senhor com respeito, objetividade, clareza e elegância em português do Brasil.\n"
    "Suas respostas serão sintetizadas por voz, portanto evite formatações markdown excessivas, emojis exagerados ou tabelas complexas, mantendo fluidez natural."
)

async def gerar_resposta_conversa(texto: str, especialidade: str = "CONVERSA") -> str:
    """
    Gera resposta inteligente usando LLM local (Ollama) ou AirLLM,
    enriquecendo o prompt com memória de longo prazo e contexto de curto prazo.
    """
    try:
        # 1. Busca contexto semântico de longo prazo
        contexto_longo = memory_long.montar_contexto_longo(texto)
        system_prompt = SYSTEM_PROMPT_BASE
        if contexto_longo:
            system_prompt += f"\n\nContexto e memórias relevantes sobre o senhor:\n{contexto_longo}"

        if especialidade == "CODIGO":
            system_prompt += "\nVocê está atuando como especialista em programação e engenharia de software. Seja preciso e direto ao ponto."

        # 2. Monta mensagens com histórico curto
        mensagens = memory_short.obter_contexto(system_prompt=system_prompt)
        mensagens.append({"role": "user", "content": texto})

        # 3. Escolhe o melhor modelo para a especialidade
        modelo, tipo = brain_selector.escolher_melhor_modelo(especialidade)
        log.info(f"[CONVERSA] Especialidade: {especialidade} | Modelo: {modelo} ({tipo})")

        # 4. Executa modelo
        if tipo == "airllm":
            resposta = await asyncio.to_thread(airllm_module.gerar_resposta_airllm, modelo, texto, system_prompt)
        else:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(model=modelo, messages=mensagens)
            )
            resposta = response['message']['content'].strip()

        # 5. Atualiza memória de curto prazo
        memory_short.adicionar_mensagem("user", texto)
        memory_short.adicionar_mensagem("assistant", resposta)

        return resposta
    except Exception as e:
        log.error(f"[CONVERSA] Erro ao gerar resposta: {e}")
        return "Perdoe-me, senhor. Ocorreu uma oscilação temporária em meus circuitos neurais ao processar sua solicitação."

```


==================================================
 ARQUIVO: .\MODULOS\brain\core\executor.py
==================================================

```python
import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice import voice_manager

async def _executar_em_background(tarefa: str):
    log.info(f"[BACKGROUND] Iniciando tarefa: {tarefa}")
    try:
        modelo, tipo = brain_selector.escolher_melhor_modelo("TAREFA_LONGA")
        prompt = (
            "Você é um especialista em planejamento. "
            f"Crie um plano detalhado, passo a passo, para a seguinte tarefa: '{tarefa}'.\n"
            "Seja criativo e minucioso."
        )
        
        if tipo == "airllm":
            resultado = await asyncio.to_thread(airllm_module.gerar_resposta_airllm, modelo, prompt, "")
        else:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(model=modelo, messages=[{'role': 'user', 'content': prompt}])
            )
            resultado = response['message']['content'].strip()
            
        log.info(f"[BACKGROUND] Tarefa '{tarefa}' concluída.")
        
        memory_long.salvar_memoria(f"resultado da tarefa {tarefa}", resultado)
        
        await atualizar_jarvis(cor_hex="#00ff00", texto="Tarefa Concluída!", padrao="tarefa")
        await voice_manager.falar("Jarvis", f"Senhor, finalizei a tarefa sobre '{tarefa}'. O resultado foi salvo na memória.", prioridade=1)

    except Exception as e:
        log.error(f"[BACKGROUND] Erro ao executar tarefa '{tarefa}': {e}")
        await voice_manager.falar("Jarvis", "Tive um problema ao processar a tarefa em segundo plano.", prioridade=1)

```


==================================================
 ARQUIVO: .\MODULOS\brain\core\router.py
==================================================

```python
import json
import re
import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.system.logger import log

def carregar_descricoes_especialistas():
    try:
        with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)
            especialistas = dados.get("especialistas", {})
            if especialistas:
                return "\n".join([f"- {k}: {v.get('descricao', '')}" for k, v in especialistas.items()])
    except Exception:
        pass
    try:
        from MODULOS.brain.models.profiles import _DESCRICOES
        return "\n".join([f"- {k}: {v}" for k, v in _DESCRICOES.items()])
    except Exception:
        return "HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA, WEB_MCP, TAREFA_LONGA, FINANCE, VISAO"

def _extrair_json(texto: str) -> dict | None:
    if not texto or not texto.strip():
        return None
    try:
        return json.loads(texto.strip())
    except Exception:
        pass
    sem_markdown = re.sub(r"```(?:json)?\s*", "", texto).replace("```", "")
    match = re.search(r"\{[^{}]+\}", sem_markdown, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    inicio = texto.find("{")
    fim = texto.rfind("}") + 1
    if inicio >= 0 and fim > inicio:
        try:
            return json.loads(texto[inicio:fim])
        except Exception:
            pass
    return None

def _rota_por_keywords(texto: str) -> dict | None:
    t = texto.lower()

    gatilhos_app = ["abrir", "abre", "iniciar", "executar", "lançar", "start", "abra"]
    gatilhos_hw  = ["temperatura", "cpu", "gpu", "ram", "vram", "verra", "vera", "hardware", "processador", "status", "placa de vídeo", "placa de video", "memória de vídeo", "usando a vram", "usando vram", "processamento", "uso do"]
    gatilhos_cod = ["código", "codigo", "script", "função", "funcao", "bug", "erro no código", "programa em python", "escreva um código", "crie uma função"]
    gatilhos_fii = ["fii", "investimento", "bolsa", "ação", "cotacao", "cotação", "fundo", "oportunidade de compra", "ganhar dinheiro", "mxrf11", "xpml11", "vghf11", "btlg11"]
    
    gatilhos_web = [
        "pesquise na internet", "pesquise na web", "pesquisa na internet", "pesquisa na web",
        "pesquise", "pesquisa", "busque na web", "busque na internet", "busca na internet",
        "busca na web", "busque", "notícias sobre", "noticias sobre", "notícia", "noticia",
        "previsão do tempo", "previsao do tempo", "clima em", "clima hoje", "tempo em",
        "temperatura em", "o que aconteceu hoje", "qual o preço atual", "preço atual de",
        "preco atual de", "cotação do dólar", "cotacao do dolar", "preço do bitcoin",
        "preco do bitcoin", "pesquisar na internet", "procure na web", "procure na internet"
    ]

    gatilhos_salvar = ["guarda", "salva", "anota", "grava", "recorda",
                       "não esqueça", "memoriza", "sabe que"]
    gatilhos_buscar_mem = ["qual é meu", "qual meu", "qual a minha", "qual o meu",
                           "você sabe meu", "lembra meu", "lembra qual", "me diz meu",
                           "quem sou", "como me chamo"]
    gatilhos_esquecer_mem = ["esquece", "apaga", "deleta"]

    gatilhos_briefing = [
        "bom dia", "resumo do dia", "notícias de hoje", "noticias de hoje",
        "briefing matinal", "briefing", "telemetria matinal", "giro do dia",
        "panorama do dia", "iniciar briefing"
    ]
    if any(g in t for g in gatilhos_briefing):
        return {"categoria": "BRIEFING", "alvo": texto}

    gatilhos_followup_briefing = [
        "me fale mais sobre", "fale mais sobre", "me fala mais sobre", "fala mais sobre",
        "explique melhor a notícia", "explique melhor a noticia",
        "explique melhor essa notícia", "explique melhor essa noticia",
        "explique a notícia", "explique a noticia", "explique melhor",
        "sobre esse assunto", "sobre este assunto", "sobre essa notícia", "sobre essa noticia",
        "sobre essa materia", "sobre essa matéria", "sobre essa manchete",
        "detalhe a notícia", "detalhe a noticia", "detalhe essa notícia", "detalhe essa noticia",
        "detalhe a matéria", "detalhe a materia", "detalhe mais", "detalhes sobre",
        "me conte mais sobre", "conte mais sobre", "me conta mais sobre", "conta mais sobre",
        "qual é a notícia", "qual e a noticia", "qual é essa notícia", "qual e essa noticia",
        "fale mais dessa notícia", "fale mais dessa noticia",
        "mais detalhes sobre", "mais detalhes da notícia", "mais detalhes dessa notícia"
    ]
    if any(g in t for g in gatilhos_followup_briefing):
        return {"categoria": "BRIEFING_FOLLOWUP", "alvo": texto}

    gatilhos_lembretes = [
        "me lembre de", "me lembre", "lembrar de", "adicionar lembrete",
        "criar lembrete", "novo lembrete", "minha agenda", "meus lembretes",
        "quais são meus lembretes", "quais sao meus lembretes", "listar lembretes",
        "concluir lembrete", "marcar lembrete", "agenda de hoje"
    ]
    if any(g in t for g in gatilhos_lembretes):
        return {"categoria": "LEMBRETES", "alvo": texto}

    # 1. Abertura de apps
    for g in gatilhos_app:
        if g in t:
            alvo = t
            for term in gatilhos_app + ["o ", "a ", "por favor", "meu", "minha"]:
                alvo = alvo.replace(term, "")
            return {"categoria": "ABRIR_APP", "alvo": alvo.strip()}

    # 2. Hardware
    if any(g in t for g in gatilhos_hw):
        foco = None
        if "cpu" in t or "processador" in t:          foco = "CPU"
        elif "gpu" in t or "placa" in t:              foco = "GPU"
        elif "vram" in t or "memória de vídeo" in t or "memoria de video" in t: foco = "VRAM"
        elif "ram" in t or "memória" in t:            foco = "RAM"
        return {"categoria": "HARDWARE", "alvo": foco}

    # 3. Web & Ferramentas Online (MCP)
    if any(g in t for g in gatilhos_web):
        return {"categoria": "WEB_MCP", "alvo": texto}

    # 4. Memória
    if any(g in t for g in gatilhos_salvar + gatilhos_buscar_mem + gatilhos_esquecer_mem):
        return {"categoria": "MEMORIA", "alvo": texto}

    # 5. Código
    if any(g in t for g in gatilhos_cod):
        return {"categoria": "CODIGO", "alvo": texto}

    # 6. Mercado Financeiro
    if any(g in t for g in gatilhos_fii):
        return {"categoria": "FINANCE", "alvo": texto}

    # 7. Visão / Análise de Tela
    gatilhos_visao = [
        "modo de visão", "modo de visao", "modo visão", "modo visao",
        "sua visão", "sua visao", "olha a tela", "olhe a tela",
        "vê na tela", "ve na tela", "o que está na tela", "o que esta na tela",
        "analise a tela", "analisar tela", "tira um print", "tire um print",
        "o que você vê", "o que voce ve", "descreva a tela", "descrever a tela",
        "olhe para a tela", "olha pra tela", "olhe pra tela"
    ]
    if any(g in t for g in gatilhos_visao):
        return {"categoria": "VISAO", "alvo": texto}

    return None

async def rotear_intencao(comando: str) -> dict:
    from MODULOS.brain.nlp_processor import normalizar_fonetica
    comando_normalizado = normalizar_fonetica(comando)

    # 1. Fast-Path por palavras-chave
    rota_rapida = _rota_por_keywords(comando_normalizado)
    if rota_rapida is not None:
        return rota_rapida

    # 2. Roteamento via LLM Roteador para dúvidas ou comandos genéricos
    try:
        modelo_roteador = "qwen2.5:1.5b"
        try:
            with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
                dados = json.load(f)
                modelo_roteador = dados.get("modelo_roteador", "qwen2.5:1.5b")
        except Exception:
            pass

        descricoes = carregar_descricoes_especialistas()
        prompt_sistema = (
            "Você é o roteador neural do Jarvis.\n"
            "Analise a intenção do usuário e classifique-a em uma destas categorias:\n"
            f"{descricoes}\n\n"
            "Categorias válidas: HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA, WEB_MCP, TAREFA_LONGA, FINANCE, VISAO.\n"
            "Retorne estritamente um JSON no formato:\n"
            '{"categoria": "NOME_CATEGORIA", "alvo": "detalhes_ou_texto"}\n'
            "Responda apenas com o JSON."
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo_roteador,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": comando_normalizado}
                ],
                options={"temperature": 0.0}
            )
        )
        conteudo = response['message']['content']
        decisao = _extrair_json(conteudo)
        if decisao and "categoria" in decisao:
            cat = str(decisao["categoria"]).upper()
            return {"categoria": cat, "alvo": decisao.get("alvo", comando)}
    except Exception as e:
        log.warning(f"[ROTEADOR] Consulta ao modelo roteador falhou: {e}. Usando rota padrão.")

    return {"categoria": "CONVERSA", "alvo": None}

```


==================================================
 ARQUIVO: .\MODULOS\brain\memory\handler.py
==================================================

```python
import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_long
from MODULOS.brain.core.router import _extrair_json
from MODULOS.system.logger import log

async def _processar_memoria(texto: str) -> str:
    t = texto.lower().strip()

    prompt_sistema = (
        "Você é o assistente de memória do Jarvis.\n"
        "O usuário enviou uma frase. Você deve classificar a intenção dele em uma das três ações:\n"
        "1) BUSCAR: quando o usuário pergunta por uma informação.\n"
        "2) SALVAR: quando o usuário quer que você guarde uma nova informação.\n"
        "3) APAGAR: quando o usuário quer que você esqueça algo.\n\n"
        "Sua resposta deve ser estritamente em formato JSON com chaves 'acao', 'chave', e 'valor'.\n"
        "Responda apenas com o JSON."
    )

    try:
        modelo_memoria, tipo = brain_selector.escolher_melhor_modelo("MEMORIA")
        
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo_memoria,
                messages=[
                    {'role': 'system', 'content': prompt_sistema},
                    {'role': 'user', 'content': f"Usuário: '{texto}'"}
                ],
                options={"temperature": 0}
            )
        )
        conteudo = response['message']['content']
        resultado = _extrair_json(conteudo)
    except Exception as e:
        log.error(f"LLM MEMORIA: {e}")
        resultado = None

    if not resultado or "acao" not in resultado:
        memory_long.salvar_memoria("nota", texto)
        return f"Anotei: '{texto}', senhor."
    
    acao = resultado.get("acao", "").upper()
    chave = resultado.get("chave", "")
    valor = resultado.get("valor", "")

    if acao == "APAGAR":
        return memory_long.apagar_memoria(chave)
    elif acao == "BUSCAR":
        resultado_busca = memory_long.buscar_memoria(chave)
        return resultado_busca if resultado_busca else f"Não tenho nenhuma memória sobre '{chave}', senhor."
    elif acao == "SALVAR":
        return memory_long.salvar_memoria(chave, valor)
    else:
        memory_long.salvar_memoria("nota", texto)
        return f"Anotei: '{texto}', senhor."

```


==================================================
 ARQUIVO: .\MODULOS\brain\models\identity_module.py
==================================================

```python
import platform
import psutil
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pynvml
except ImportError:
    pynvml = None
import json
import os
import subprocess

IDENTITY_FILE = "DADOS/jarvis_identity.json"

def capturar_cpu_autonomo():
    """Tenta 3 métodos diferentes para pegar o nome real da CPU sem intervenção humana."""
    # Método 1: Registro do Windows (Geralmente o mais preciso)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Hardware\Description\System\CentralProcessor\0")
        nome, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        winreg.CloseKey(key)
        return nome.strip()
    except:
        pass

    # Método 2: WMI (Fallback para o sistema)
    try:
        comando = "wmic cpu get name"
        saida = subprocess.check_output(comando, shell=True).decode().strip().split('\n')
        if len(saida) > 1:
            return saida[1].strip()
    except:
        pass

    # Método 3: Platform (O que estava vindo genérico)
    return platform.processor()

def mapear_sistema_completo():
    print("[AUTO-DETECÇÃO] Analisando hardware desconhecido...")
    
    # Detecção dinâmica de OS
    versao_os = f"{platform.system()} {platform.release()}"
    if platform.system() == "Windows" and platform.release() == "10":
        # Ajuste para detectar Windows 11 que se reporta como 10
        import sys
        if sys.getwindowsversion().build >= 22000:
            versao_os = "Windows 11"

    # Detecção dinâmica de CPU
    cpu_real = capturar_cpu_autonomo()
    
    # Detecção dinâmica de GPU
    gpu_nome = "GPU Genérica / Integrada"
    vram_total = 0.0
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_nome = pynvml.nvmlDeviceGetName(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total = round(mem_info.total / (1024**3), 2)
    except:
        # Se não houver NVIDIA, tentamos listar via WMIC
        try:
            cmd_gpu = "wmic path win32_VideoController get name"
            gpu_nome = subprocess.check_output(cmd_gpu, shell=True).decode().strip().split('\n')[1].strip()
        except:
            pass

    identidade = {
        "cpu_modelo": cpu_real,
        "cpu_cores": f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count(logical=True)} threads",
        "gpu_modelo": gpu_nome,
        "vram_total_gb": vram_total,
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "os_versao": versao_os,
        "mapeado_em": platform.node()
    }

    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identidade, f, indent=4, ensure_ascii=False)
    
    print(f"[SISTEMA] Identidade Gerada: {identidade['cpu_modelo']} no {identidade['os_versao']}")
    return identidade

def carregar_identidade():
    if os.path.exists(IDENTITY_FILE):
        with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return mapear_sistema_completo()

```


==================================================
 ARQUIVO: .\MODULOS\brain\models\profiles.py
==================================================

```python
PERFIS = {
    "CPU_ONLY": {
        "descricao": "Sem GPU dedicada ou VRAM < 4GB — modelos mínimos na CPU/GPU.",
        "modelos": {
            "ROTEADOR": ["qwen2.5:1.5b"],
            "CONVERSA": ["phi3:mini", "gemma3:1b"],
            "CODIGO": ["qwen2.5-coder:1.5b"],
            "VISAO": ["moondream2"],
            "TAREFA_LONGA": ["qwen2.5:3b"]
        }
    },
    "LOW": {
        "descricao": "VRAM 4-6 GB — Modelos balanceados com quantização leve e AirLLM.",
        "modelos": {
            "ROTEADOR": ["qwen3:1.7b", "qwen2.5:1.5b"],
            "CONVERSA": ["llama3.2:3b", "gemma3:4b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["moondream"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "MEDIUM": {
        "descricao": "VRAM 6-8 GB — Modelos de tamanho médio e grandes offline.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b", "qwen2.5:3b"],
            "CONVERSA": ["qwen2.5:7b", "llama3.2:3b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llava:7b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "HIGH": {
        "descricao": "VRAM 8-12 GB — Modelos maiores para alta precisão.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["llama3.3:8b", "qwen2.5:14b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:11b", "llava:13b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "ULTRA": {
        "descricao": "VRAM 12-16 GB — Modelos muito grandes, quase sem quantização.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["qwen3:14b", "mixtral:8x7b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["qwen2.5vl:7b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "MONSTER": {
        "descricao": "VRAM >= 24 GB — Modelos de ponta, sem compromissos.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["llama3.3:70b-q4", "qwen3:32b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:11b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "SERVER": {
        "descricao": "Hardware de servidor — Múltiplas GPUs, alta performance.",
        "modelos": {
            "ROTEADOR": ["qwen3:8b"],
            "CONVERSA": ["llama3.3:70b", "deepseek-v3"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:90b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "DATACENTER": {
        "descricao": "Datacenter — Máxima performance, modelos de ponta.",
        "modelos": {
            "ROTEADOR": ["qwen3:32b"],
            "CONVERSA": ["deepseek-v3", "llama3.3:70b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:90b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    }
}

_DESCRICOES = {
    "HARDWARE":     "Monitoramento de CPU, GPU, RAM e temperaturas.",
    "ABRIR_APP":    "Execução de programas e comandos do Windows.",
    "CONVERSA":     "Interações sociais, perguntas e dúvidas gerais.",
    "CODIGO":       "Criação de scripts, depuração e lógica de programação.",
    "VISAO":        "Análise de tela e imagens.",
    "TAREFA_LONGA": "Raciocínio complexo, planejamento e tarefas que exigem múltiplos passos.",
    "MEMORIA":      "Guardar, lembrar ou esquecer informações e fatos pessoais. Ativado por palavras como: guarda, salva, lembra, anota, grava, esquece, sabe que.",
    "WEB_MCP":      "Pesquisas na internet, notícias em tempo real, previsão do tempo, cotações e ferramentas online via protocolo MCP.",
}

```


==================================================
 ARQUIVO: .\MODULOS\brain\selector\detector.py
==================================================

```python
import json
import os

def _ler_identidade() -> dict:
    path = "DADOS/jarvis_identity.json"
    if not os.path.exists(path):
        try:
            from MODULOS.brain.models.identity_module import carregar_identidade
            return carregar_identidade()
        except Exception:
            path = os.path.join("teste", "jarvis_identity.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _detectar_vram_psutil() -> float:
    try:
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning)
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(info.total / (1024 ** 3), 2)
    except Exception:
        return 0.0

def detectar_hardware() -> dict:
    identidade = _ler_identidade()

    vram_gb = identidade.get("vram_total_gb", 0.0)
    if vram_gb == 0.0:
        vram_gb = _detectar_vram_psutil()

    ram_gb = identidade.get("ram_total_gb", 0.0)
    if ram_gb == 0.0:
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            ram_gb = 8.0 

    cores_str = identidade.get("cpu_cores", "")
    try:
        cpu_cores = int(cores_str.split("cores")[0].strip())
    except Exception:
        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=False) or 4
        except Exception:
            cpu_cores = 4

    return {
        "vram_gb":    vram_gb,
        "ram_gb":     ram_gb,
        "cpu_cores":  cpu_cores,
        "cpu_modelo": identidade.get("cpu_modelo", "Desconhecido"),
        "gpu_modelo": identidade.get("gpu_modelo", "Desconhecido"),
    }

```


==================================================
 ARQUIVO: .\MODULOS\brain\selector\selector.py
==================================================

```python
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

```


==================================================
 ARQUIVO: .\MODULOS\ear\farewell.py
==================================================

```python
import ollama
from MODULOS.system.logger import log

def _e_despedida(texto: str) -> bool:
    if not texto or not texto.strip():
        return False
    try:
        prompt = (
            "Você decide se o usuário está EXPLICITAMENTE se despedindo do assistente.\n"
            "Só responda SIM se houver palavras claras de despedida como: tchau, até logo, pode dormir, encerrar, desligar, obrigado pode ir, até mais.\n"
            "Instruções, perguntas, pedidos ou comentários são NAO.\n"
            "Responda APENAS: SIM ou NAO.\n\n"
            f"Frase: \"{texto}\"\n"
            "É uma despedida explícita?"
        )
        resp = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}
        )
        resposta = resp["message"]["content"].strip().upper()
        return resposta.startswith("SIM")
    except Exception as e:
        log.debug(f"Erro LLM despedida: {e}")
        despedidas = ["tchau", "até logo", "pode dormir", "encerrar", "desligar"]
        texto_lower = texto.lower()
        if any(d in texto_lower for d in despedidas):
            return True
        return False

def verificar_despedida(texto: str) -> bool:
    return _e_despedida(texto)

```


==================================================
 ARQUIVO: .\MODULOS\ear\models.py
==================================================

```python
from faster_whisper import WhisperModel
import threading
from MODULOS.system.logger import log

whisper_model     = None
whisper_tiny      = None    
_whisper_backend  = None    

def inicializar_whisper_tiny():
    global whisper_tiny
    log.info("Carregando Whisper tiny na CPU (wake word)...")
    whisper_tiny = WhisperModel("tiny", device="cpu", compute_type="int8")
    log.info("Whisper tiny pronto. Small será carregado ao ativar.")

def carregar_whisper_small():
    global whisper_model, _whisper_backend
    if whisper_model is None:
        try:
            import torch
            if torch.cuda.is_available():
                device, compute = "cuda", "float16"
                log.info(f"Carregando Whisper small no {device.upper()} (faster-whisper)...")
                whisper_model = WhisperModel("small", device=device, compute_type=compute)
                _whisper_backend = "faster_whisper"
                log.info("Whisper small pronto.")
                return
        except Exception:
            pass

        try:
            import torch_directml
            if torch_directml.is_available():
                import whisper as openai_whisper
                dml = torch_directml.device()
                log.info("DirectML detectado. Carregando Whisper small no DML (PyTorch)...")
                model = openai_whisper.load_model("small")
                model.to(dml)
                whisper_model = model
                _whisper_backend = "openai_whisper_dml"
                log.info("Whisper small pronto (DirectML).")
                return
        except Exception as e:
            log.warning(f"Backend DirectML indisponível, usando fallback CPU. Motivo: {e}")

        device, compute = "cpu", "int8"
        log.info(f"Carregando Whisper small no {device.upper()} (faster-whisper)...")
        whisper_model = WhisperModel("small", device=device, compute_type=compute)
        _whisper_backend = "faster_whisper"
        log.info("Whisper small pronto.")

def descarregar_whisper_small():
    global whisper_model, _whisper_backend
    if whisper_model is not None:
        log.info("Descarregando Whisper small...")
        del whisper_model
        whisper_model = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass

        if _whisper_backend == "faster_whisper":
            try:
                import torch
                if getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        _whisper_backend = None
        log.info("Recursos liberados.")

```


==================================================
 ARQUIVO: .\MODULOS\ear\recorder.py
==================================================

```python
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from collections import deque
import queue
import threading
import time
import os
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

FS               = 16000
CHUNK_SIZE       = 1024
THRESHOLD_BARULHO = 0.0025
DEVICE_ID        = None
TIMEOUT_ATIVO    = 60
MAX_DURACAO_FALA = 15.0

# Stream persistente com Pré-Buffer contínuo de 1.5s
_audio_queue = queue.Queue(maxsize=300)
_pre_buffer = deque(maxlen=int(FS / CHUNK_SIZE * 1.5))
_stream = None
_stream_lock = threading.Lock()

def _audio_callback(indata, frames, time_info, status):
    if status:
        pass
    chunk = indata.copy()
    _pre_buffer.append(chunk)
    try:
        _audio_queue.put_nowait(chunk)
    except queue.Full:
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            pass
        _audio_queue.put_nowait(chunk)

def selecionar_microfone():
    global DEVICE_ID
    try:
        devices = sd.query_devices()
        candidato = None
        # Prioriza driver DirectSound (hostapi 1 no Windows) que tem 10x mais ganho e menor latência que MME
        for idx, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                name = d['name'].lower()
                if 'steam' in name or 'mixagem' in name:
                    continue
                if d.get('hostapi') == 1 and ('realtek' in name or 'microf' in name):
                    candidato = idx
                    break

        if candidato is not None:
            DEVICE_ID = candidato
            log.info(f"[EAR] Microfone de alta precisão selecionado (DirectSound): [{DEVICE_ID}] {devices[DEVICE_ID]['name']}")
            return DEVICE_ID

        # Fallback para dispositivo padrão
        info = sd.query_devices(kind='input')
        DEVICE_ID = info.get('index', None)
        log.info(f"[EAR] Microfone padrão: [{DEVICE_ID}] {info.get('name')}")
    except Exception as e:
        DEVICE_ID = None
        log.warning(f"[EAR] Usando dispositivo padrão do sistema ({e})")
    return DEVICE_ID

def garantir_stream():
    """Garante que o stream contínuo do microfone esteja ativo (latência zero)."""
    global _stream, DEVICE_ID
    with _stream_lock:
        if _stream is not None and _stream.active:
            return _stream

        if _stream is not None:
            try:
                _stream.stop()
                _stream.close()
            except Exception:
                pass
            _stream = None

        if DEVICE_ID is None:
            selecionar_microfone()

        try:
            _stream = sd.InputStream(
                samplerate=FS,
                channels=1,
                blocksize=CHUNK_SIZE,
                device=DEVICE_ID,
                callback=_audio_callback
            )
            _stream.start()
            log.info("[EAR] Stream contínuo do microfone ativado com DirectSound (latência zero).")
        except Exception as e:
            log.error(f"[EAR] Falha ao iniciar stream contínuo do microfone: {e}")
            _stream = None
        return _stream

def limpar_pre_buffer():
    global _pre_buffer
    _pre_buffer.clear()

def calibrar_ruido(duracao=2):
    global THRESHOLD_BARULHO
    garantir_stream()
    log.info("[EAR] Calibrando microfone... Fique em silêncio por 2 segundos.")
    
    # Esvazia fila acumulada
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break

    num_chunks = int(duracao * FS / CHUNK_SIZE)
    chunks = []
    fim = time.time() + duracao + 1.0

    while len(chunks) < num_chunks and time.time() < fim:
        try:
            chunk = _audio_queue.get(timeout=0.2)
            chunks.append(chunk)
        except queue.Empty:
            pass

    if chunks:
        dados = np.concatenate(chunks, axis=0)
        rms = float(np.sqrt(np.mean(dados**2)))
        
        # Limiar adaptativo: 2.2x o ruído ambiente, mínimo 0.0008 e máximo 0.012
        novo_threshold = max(0.0008, min(0.012, rms * 2.2))
        THRESHOLD_BARULHO = novo_threshold

        log.info(f"[EAR] Ruído ambiente médio (RMS): {rms:.5f} | Limiar de ativação definido em: {THRESHOLD_BARULHO:.5f}")
    else:
        THRESHOLD_BARULHO = 0.0015

def gravar_fala(max_silencio_frames=16, arquivo="TEMP_AUDIO/input.wav", callback_feedback=None) -> bool:
    global _pre_buffer
    stream = garantir_stream()
    if stream is None or not stream.active:
        return False

    flag_stop = "DADOS/mic_stop.flag"
    flag_cmd = "DADOS/comando_manual.txt"
    if os.path.exists(flag_stop):
        try:
            os.remove(flag_stop)
        except Exception:
            pass

    # 1. Esvazia fila acumulada para ler áudio ao vivo
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break

    audio_buffer = []
    falando = False
    silencio_frames = 0
    chunks_sem_fala = 0
    max_chunks_sem_fala = int(6.0 * FS / CHUNK_SIZE)  # Aguarda até 6s pelo início da fala

    # Limiares adaptativos calibrados
    limiar_ativacao = max(0.0010, THRESHOLD_BARULHO)
    limiar_sustentacao = max(0.0012, THRESHOLD_BARULHO * 0.85)
    MAX_DURACAO_FALA = 15.0  # Teto de segurança: máximo 15 segundos gravando

    while True:
        if os.path.exists("DADOS/mic_muted.flag"):
            while not _audio_queue.empty():
                try:
                    _audio_queue.get_nowait()
                except queue.Empty:
                    break
            _pre_buffer.clear()
            time.sleep(0.2)
            return False

        if voice_manager.STATUS_FALANDO:
            time.sleep(0.05)
            return False

        # Se houver comando manual de texto enviado pela interface, aborta escuta imediatamente
        if os.path.exists(flag_cmd):
            return False

        # Se o usuário clicou no botão "PARAR E ENVIAR" na interface
        if os.path.exists(flag_stop):
            try:
                os.remove(flag_stop)
            except Exception:
                pass
            log.info("[EAR] Parada manual de áudio solicitada via interface. Finalizando captura...")
            if not falando and len(_pre_buffer) > 0:
                audio_buffer.extend(list(_pre_buffer))
            falando = True
            break

        try:
            data = _audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        volume = float(np.linalg.norm(data) / np.sqrt(len(data)))

        if not falando:
            if volume > limiar_ativacao:
                falando = True
                audio_buffer.extend(list(_pre_buffer))
                audio_buffer.append(data.copy())
                silencio_frames = 0
                if callback_feedback:
                    callback_feedback(True, volume, len(audio_buffer) * CHUNK_SIZE / FS)
            else:
                chunks_sem_fala += 1
                if callback_feedback:
                    callback_feedback(False, volume, 0.0)
                if chunks_sem_fala > max_chunks_sem_fala:
                    return False
        else:
            audio_buffer.append(data.copy())
            duracao_atual = len(audio_buffer) * CHUNK_SIZE / FS
            if callback_feedback:
                callback_feedback(True, volume, duracao_atual)

            # Teto de segurança: impede gravação infinita
            if duracao_atual >= MAX_DURACAO_FALA:
                log.info(f"[EAR] Limite de {MAX_DURACAO_FALA}s atingido ({duracao_atual:.1f}s). Processando áudio...")
                break

            limiar_corte_silencio = max(limiar_sustentacao, limiar_ativacao * 0.90)
            if volume > limiar_corte_silencio:
                silencio_frames = 0
            else:
                silencio_frames += 1
                if silencio_frames > max_silencio_frames:
                    break

    if audio_buffer and falando:
        audio_final = np.concatenate(audio_buffer, axis=0)

        # Se tiver pelo menos 0.45s de áudio, salva e processa (evita cliques de mouse/teclado)
        duracao_segundos = len(audio_final) / FS
        if duracao_segundos < 0.45:
            return False

        # Normalização de ganho (AGC)
        max_val = np.max(np.abs(audio_final))
        if max_val > 0.001:
            audio_final = (audio_final / max_val) * 0.85

        dir_saida = os.path.dirname(os.path.abspath(arquivo))
        if dir_saida:
            os.makedirs(dir_saida, exist_ok=True)

        write(arquivo, FS, audio_final.astype(np.float32))
        return True

    return False

```


==================================================
 ARQUIVO: .\MODULOS\ear\states.py
==================================================

```python
import time
import threading

class Estado:
    DORMINDO = "DORMINDO"
    ATIVO    = "ATIVO"

_estado          = Estado.DORMINDO
_ultimo_comando  = time.time()
_lock_estado     = threading.Lock()

def get_estado() -> str:
    return _estado

def _set_estado(novo: str, carregar_cb=None, descarregar_cb=None):
    global _estado
    with _lock_estado:
        anterior = _estado
        _estado = novo
    if anterior != novo:
        if novo == Estado.ATIVO and carregar_cb:
            threading.Thread(target=carregar_cb, daemon=True).start()
        elif novo == Estado.DORMINDO and descarregar_cb:
            threading.Thread(target=descarregar_cb, daemon=True).start()

def set_estado(novo_estado: str, carregar_cb=None, descarregar_cb=None):
    if novo_estado in [Estado.ATIVO, Estado.DORMINDO]:
        _set_estado(novo_estado, carregar_cb, descarregar_cb)

def verificar_timeout(timeout) -> bool:
    return (time.time() - _ultimo_comando) > timeout

def resetar_timeout():
    global _ultimo_comando
    _ultimo_comando = time.time()

```


==================================================
 ARQUIVO: .\MODULOS\ear\transcriber.py
==================================================

```python
from MODULOS.ear import models
from MODULOS.system.logger import log

def transcrever_audio(arquivo: str = "TEMP_AUDIO/input.wav") -> str:
    try:
        if models.whisper_model is None:
            models.carregar_whisper_small()

        if models.whisper_model is None:
            log.error("[EAR] Não foi possível carregar o modelo Whisper.")
            return ""

        PROMPT_INICIAL = "Jarvis, comando de voz."

        if models._whisper_backend == "openai_whisper_dml":
            import whisper as openai_whisper
            result = openai_whisper.transcribe(
                models.whisper_model,
                arquivo,
                language="pt",
                initial_prompt=PROMPT_INICIAL,
                fp16=False,
                beam_size=5,
                condition_on_previous_text=False,
            )
            texto = (result.get("text") or "").strip()
            if texto == PROMPT_INICIAL or texto.rstrip('.').strip().lower() == PROMPT_INICIAL.rstrip('.').strip().lower():
                return ""
            return texto

        segments, _ = models.whisper_model.transcribe(
            arquivo,
            language="pt",
            initial_prompt=PROMPT_INICIAL,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
            beam_size=5,
            condition_on_previous_text=False
        )
        texto = " ".join([s.text for s in segments]).strip()
        if texto == PROMPT_INICIAL or texto.rstrip('.').strip().lower() == PROMPT_INICIAL.rstrip('.').strip().lower():
            return ""
        return texto
    except Exception as e:
        log.error(f"Erro na transcrição completa: {e}")
        return ""

```


==================================================
 ARQUIVO: .\MODULOS\ear\wake_word.py
==================================================

```python
import re
try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None
from MODULOS.voice import voice_manager
from MODULOS.system.logger import log
from MODULOS.ear.recorder import gravar_fala
from MODULOS.ear.models import whisper_tiny

WAKE_WORDS = [
    "jarvis", "jarbas", "javes", "travis", "garvis", "service", 
    "yaves", "lajardis", "jardis", "jarves", "jarvys", "ia"
]

def _contem_wake_word(texto: str) -> bool:
    if not texto:
        return False
    texto_limpo = re.sub(r'[^\w\s]', ' ', texto.lower())
    palavras = texto_limpo.split()
    
    # 1. Checagem direta por palavra ou similaridade fuzzy
    for palavra in palavras:
        for wake in WAKE_WORDS:
            if palavra == wake:
                return True
            if fuzz and fuzz.ratio(palavra, wake) >= 70:
                return True
            elif wake in palavra:
                return True
                
    # 2. Checagem na frase completa
    for wake in WAKE_WORDS:
        if wake in texto_limpo:
            return True
            
    return False

def _transcrever_tiny(arquivo="TEMP_AUDIO/wake.wav") -> str:
    try:
        segments, _ = whisper_tiny.transcribe(
            arquivo,
            language="pt",
            vad_filter=True,
            condition_on_previous_text=False
        )
        return " ".join([s.text for s in segments]).strip().lower()
    except Exception as e:
        log.debug(f"[WAKE] Erro transcrição tiny: {e}")
        return ""

def escutar_wake_word() -> bool:
    if voice_manager.STATUS_FALANDO:
        return False

    if gravar_fala(max_silencio_frames=15, arquivo="TEMP_AUDIO/wake.wav"):
        texto = _transcrever_tiny("TEMP_AUDIO/wake.wav")
        if texto:
            log.info(f"[WAKE] Ouvi: '{texto}'")
            if _contem_wake_word(texto):
                log.info(f"[WAKE] Palavra-chave reconhecida! ('{texto}')")
                return True
    return False

```


==================================================
 ARQUIVO: .\MODULOS\ear\__init__.py
==================================================

```python
from MODULOS.system.logger import log
from MODULOS.ear.states import Estado, get_estado, set_estado, verificar_timeout, resetar_timeout
from MODULOS.ear.models import inicializar_whisper_tiny, carregar_whisper_small, descarregar_whisper_small
from MODULOS.ear.recorder import calibrar_ruido, selecionar_microfone, gravar_fala
from MODULOS.ear.wake_word import escutar_wake_word
from MODULOS.ear.farewell import verificar_despedida
from MODULOS.ear.transcriber import transcrever_audio
from MODULOS.voice import voice_manager

from MODULOS.ear import states

# Wrapper para set_estado exportado para manter compatibilidade com código antigo
def set_estado(novo_estado: str):
    states.set_estado(novo_estado, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

def inicializar_whisper():
    carregar_whisper_small()

def capturar_comando_dinamico() -> tuple[bool, str]:
    # ── MODO WAKE WORD COMENTADO TEMPORARIAMENTE A PEDIDO DO USUÁRIO ──
    # estado_atual = get_estado()
    # if estado_atual == Estado.DORMINDO:
    #     if escutar_wake_word():
    #         set_estado(Estado.ATIVO)
    #         resetar_timeout()
    #         return False, Estado.ATIVO
    #     return False, Estado.DORMINDO

    # MODO ESCUTA DIRETA (SEMPRE ATIVO):
    if get_estado() != Estado.ATIVO:
        set_estado(Estado.ATIVO)

    if voice_manager.STATUS_FALANDO:
        return False, Estado.ATIVO

    if gravar_fala(max_silencio_frames=18, arquivo="TEMP_AUDIO/input.wav"):
        resetar_timeout()
        return True, Estado.ATIVO

    return False, Estado.ATIVO

```


==================================================
 ARQUIVO: .\MODULOS\memory\memory_long.py
==================================================

```python
"""
memory_long.py
──────────────
Memória de longo prazo do Jarvis usando ChromaDB.

Dois bancos vetoriais separados:
  chroma_fatos/     → fatos permanentes chave/valor (nome, preferências, etc.)
  chroma_historico/ → histórico de conversas passadas

Busca semântica: "como me chamo" encontra "nome = Felipe" sem precisar
da palavra exata — o ChromaDB entende o significado.
"""

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    chromadb = None
    embedding_functions = None
from datetime import datetime
import uuid

# ─────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────

# Embedding local via sentence-transformers (roda na CPU, sem internet)
_EMB = None

_client_fatos     = None
_client_historico = None
_col_fatos        = None
_col_historico    = None


def inicializar_banco():
    """Cria/abre os dois bancos ChromaDB. Chame uma vez no boot."""
    global _client_fatos, _client_historico, _col_fatos, _col_historico, _EMB, chromadb, embedding_functions

    if chromadb is None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            print("[MEMÓRIA] ChromaDB não está instalado. Memória de longo prazo indisponível.")
            return

    if _EMB is None:
        _EMB = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    # Banco de fatos permanentes
    _client_fatos = chromadb.PersistentClient(path="DADOS/chroma_fatos")
    _col_fatos = _client_fatos.get_or_create_collection(
        name="fatos",
        embedding_function=_EMB,
        metadata={"hnsw:space": "cosine"}
    )

    # Banco de histórico de conversas
    _client_historico = chromadb.PersistentClient(path="DADOS/chroma_historico")
    _col_historico = _client_historico.get_or_create_collection(
        name="historico",
        embedding_function=_EMB,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"[MEMORIA] Fatos: {_col_fatos.count()} entradas | "
          f"Histórico: {_col_historico.count()} entradas")


def _garantir_init():
    """Inicializa automaticamente se ainda não foi feito."""
    if _col_fatos is None or _col_historico is None:
        inicializar_banco()


# ─────────────────────────────────────────
#  FATOS — memória semântica permanente
# ─────────────────────────────────────────

def salvar_memoria(chave: str, valor: str) -> str:
    """
    Salva ou atualiza um fato.
    O documento indexado é "chave: valor" para busca semântica rica.
    """
    _garantir_init()
    if _col_fatos is None:
        return "Banco de memória vetorial indisponível no momento."
    chave = chave.strip().lower()
    valor = valor.strip()

    # ChromaDB usa upsert por ID — usa a chave como ID para permitir update
    doc_id = f"fato_{chave.replace(' ', '_')}"
    documento = f"{chave}: {valor}"

    _col_fatos.upsert(
        ids=[doc_id],
        documents=[documento],
        metadatas=[{
            "chave": chave,
            "valor": valor,
            "atualizado": datetime.now().isoformat()
        }]
    )
    return f"Entendido, senhor. Gravei que '{chave}' é '{valor}'."


def buscar_memoria(consulta: str, n=3) -> str | None:
    """
    Busca semântica — retorna os fatos mais relevantes para a consulta.
    Funciona mesmo com palavras diferentes (ex: 'nome' encontra 'como me chamo').
    """
    _garantir_init()
    if _col_fatos is None or _col_fatos.count() == 0:
        return None

    resultados = _col_fatos.query(
        query_texts=[consulta],
        n_results=min(n, _col_fatos.count())
    )

    docs = resultados.get("documents", [[]])[0]
    metas = resultados.get("metadatas", [[]])[0]

    if not docs:
        return None

    # Formata os resultados encontrados
    linhas = [f"- {m['chave']}: {m['valor']}" for m in metas]
    return "\n".join(linhas)


def apagar_memoria(chave: str) -> str:
    """Remove um fato pelo nome da chave."""
    _garantir_init()
    if _col_fatos is None:
        return f"Não foi possível apagar '{chave}'."
    doc_id = f"fato_{chave.strip().lower().replace(' ', '_')}"
    try:
        _col_fatos.delete(ids=[doc_id])
        return f"Memória sobre '{chave}' apagada, senhor."
    except Exception as e:
        return f"Não encontrei nada sobre '{chave}' para apagar."


def listar_fatos(n=20) -> list[dict]:
    """Retorna os N fatos mais recentes (para debug ou interface)."""
    _garantir_init()
    if _col_fatos is None or _col_fatos.count() == 0:
        return []
    resultado = _col_fatos.get(limit=n, include=["metadatas"])
    return resultado.get("metadatas", [])


# ─────────────────────────────────────────
#  HISTÓRICO — conversas passadas
# ─────────────────────────────────────────

# Histórico ilimitado — o ChromaDB gerencia o armazenamento de forma eficiente


def registrar_conversa_global(papel: str, mensagem: str):
    """Salva uma mensagem no histórico vetorial (sem limite de entradas)."""
    _garantir_init()
    if _col_historico is None:
        return
    if not mensagem or not mensagem.strip():
        return

    doc_id = str(uuid.uuid4())
    _col_historico.add(
        ids=[doc_id],
        documents=[mensagem],
        metadatas=[{
            "papel": papel,
            "timestamp": datetime.now().isoformat(),
            "ts_unix": int(datetime.now().timestamp())
        }]
    )


def buscar_historico_relevante(consulta: str, n=3, max_meses=24) -> list[dict]:
    """
    Busca em cascata mensal:
      1. Tenta achar resultados no mês atual.
      2. Se não achar nada, recua um mês e tenta de novo.
      3. Continua recuando até 'max_meses' meses no passado.
    Assim o Jarvis sempre prioriza contexto recente, mas nunca perde
    conversas antigas sobre assuntos que não aparecem todo mês.
    """
    _garantir_init()
    if _col_historico is None or _col_historico.count() == 0:
        return []

    agora = datetime.now()

    for meses_atras in range(max_meses):
        # Calcula o início e fim do mês-alvo
        mes_alvo = agora.month - meses_atras
        ano_alvo = agora.year
        while mes_alvo <= 0:
            mes_alvo += 12
            ano_alvo -= 1

        # Calcula o início e fim do mês-alvo em Unix epoch (int)
        inicio_unix = int(datetime(ano_alvo, mes_alvo, 1).timestamp())
        if mes_alvo == 12:
            fim_unix = int(datetime(ano_alvo + 1, 1, 1).timestamp())
        else:
            fim_unix = int(datetime(ano_alvo, mes_alvo + 1, 1).timestamp())

        try:
            resultado = _col_historico.query(
                query_texts=[consulta],
                n_results=min(n, _col_historico.count()),
                where={"$and": [
                    {"ts_unix": {"$gte": inicio_unix}},
                    {"ts_unix": {"$lt": fim_unix}}
                ]}
            )

            docs  = resultado.get("documents",  [[]])[0]
            metas = resultado.get("metadatas",  [[]])[0]

            if docs:
                from MODULOS.system.logger import log
                label = "mês atual" if meses_atras == 0 else f"{meses_atras} mês(es) atrás"
                log.debug(f"[MEMÓRIA] Histórico encontrado em: {label} ({ano_alvo}/{mes_alvo:02d})")
                return [
                    {"papel": m["papel"], "mensagem": d, "timestamp": m["timestamp"]}
                    for d, m in zip(docs, metas)
                ]
        except Exception:
            # ChromaDB não suporta filtro por where sem entradas no período — ignora e continua
            continue

    return []  # Não achou nada em nenhum mês


def montar_contexto_longo(consulta: str) -> str:
    """
    Monta o bloco de contexto para injetar no system prompt.
    Combina fatos relevantes + histórico relevante.
    Retorna string vazia se não houver nada relevante.
    """
    _garantir_init()
    if _col_fatos is None and _col_historico is None:
        return ""
    partes = []

    fatos = buscar_memoria(consulta, n=4)
    if fatos:
        partes.append(f"O que você sabe sobre o senhor:\n{fatos}")

    historico = buscar_historico_relevante(consulta, n=3)
    if historico:
        linhas = [f"  [{h['papel']}]: {h['mensagem']}" for h in historico]
        partes.append("Conversas anteriores relevantes:\n" + "\n".join(linhas))

    return "\n\n".join(partes)

```


==================================================
 ARQUIVO: .\MODULOS\memory\memory_short.py
==================================================

```python
# memory_short.py
from collections import deque

# Mantém as últimas 10 interações
MAX_MENSAGENS = 10 
contexto_atual = deque(maxlen=MAX_MENSAGENS)

def adicionar_mensagem(role, content):
    """Adiciona uma mensagem ao histórico."""
    contexto_atual.append({'role': role, 'content': content})

def obter_contexto(system_prompt="Você é o Jarvis. Responda de forma técnica e curta."):
    """Retorna a lista de mensagens para o Ollama."""
    mensagens = [{'role': 'system', 'content': system_prompt}]
    mensagens.extend(list(contexto_atual))
    return mensagens

```


==================================================
 ARQUIVO: .\MODULOS\skills\actions_module.py
==================================================

```python
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
```


==================================================
 ARQUIVO: .\MODULOS\skills\briefing_module.py
==================================================

```python
"""
briefing_module.py
──────────────────
Motor do Briefing Matinal Coreografado com Cards Visuais e Imagens para o Jarvis.
Executa a telemetria matinal, coleta clima, agenda/lembretes, cotações de mercado e
notícias reais multi-fontes com imagens, coordenando a fala do TTS com a exibição
e movimentação de cards holográficos na interface HUD.
"""

import os
import json
import asyncio
import re
import urllib.parse
import xml.etree.ElementTree as ET
import httpx
from datetime import datetime

from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import atualizar_jarvis, enviar_evento_interface
from MODULOS.voice import voice_manager
from MODULOS.skills import reminders_module

BRIEFING_EM_ANDAMENTO = False
ULTIMO_BRIEFING_CARDS: list[dict] = []

IMAGENS_FALLBACK = {
    "mundo": "https://images.unsplash.com/photo-1526778548025-fa2f459cd5c1?w=800&q=80",
    "economia": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
    "tecnologia": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "brasil": "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?w=800&q=80"
}

def carregar_cidade_config() -> str:
    caminho = "DADOS/news_config.json"
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados.get("cidade", "Passo Fundo")
        except Exception:
            pass
    return "Passo Fundo"

# ──────────────────────────────────────────────────────────
# 1. CARD DE CLIMA & METEOROLOGIA
# ──────────────────────────────────────────────────────────

async def obter_card_clima(cidade: str = None) -> dict:
    if not cidade:
        cidade = carregar_cidade_config()

    cidade_url = urllib.parse.quote_plus(cidade)
    url = f"https://wttr.in/{cidade_url}?format=j1"
    
    temp = "22"
    sensacao = "22"
    min_t = "16"
    max_t = "26"
    umidade = "65"
    vento = "12"
    condicao = "Tempo estável"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        async with httpx.AsyncClient(headers=headers, timeout=4.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                atual = data.get("current_condition", [{}])[0]
                temp = atual.get("temp_C", temp)
                sensacao = atual.get("FeelsLikeC", temp)
                umidade = atual.get("humidity", umidade)
                vento = atual.get("windspeedKmph", vento)
                
                # Descrição em português
                if "lang_pt" in atual and atual["lang_pt"]:
                    condicao = atual["lang_pt"][0].get("value", condicao)
                elif "weatherDesc" in atual and atual["weatherDesc"]:
                    condicao = atual["weatherDesc"][0].get("value", condicao)

                weather_days = data.get("weather", [])
                if weather_days:
                    min_t = weather_days[0].get("mintempC", min_t)
                    max_t = weather_days[0].get("maxtempC", max_t)
    except Exception as e:
        log.warning(f"[BRIEFING] Erro ao obter dados do clima: {e}")

    fala = (
        f"Em {cidade}, a temperatura atual é de {temp} graus com sensação térmica de {sensacao} graus. "
        f"A previsão para hoje indica mínima de {min_t} e máxima de {max_t} graus, "
        f"com umidade do ar em {umidade} por cento e ventos de {vento} quilômetros por hora. Condições de {condicao}."
    )

    return {
        "id": "card_clima",
        "tipo": "clima",
        "categoria": "METEOROLOGIA & SENSORES",
        "titulo": f"Previsão do Tempo // {cidade}",
        "cidade": cidade,
        "temp_atual": f"{temp}°C",
        "sensacao": f"{sensacao}°C",
        "min_max": f"Mín {min_t}°C / Máx {max_t}°C",
        "umidade": f"{umidade}%",
        "vento": f"{vento} km/h",
        "condicao": condicao,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 2. CARD DE AGENDA & LEMBRETES
# ──────────────────────────────────────────────────────────

async def obter_card_agenda() -> dict:
    pendentes = reminders_module.listar_lembretes_pendentes()
    itens = []
    for p in pendentes[:4]:
        itens.append({
            "id": p.get("id"),
            "texto": p.get("texto"),
            "horario": p.get("horario") or "--:--"
        })

    if itens:
        descricoes = []
        for it in itens:
            if it["horario"] and it["horario"] != "--:--":
                descricoes.append(f"{it['texto']} às {it['horario']}")
            else:
                descricoes.append(f"{it['texto']}")
        
        qtd = len(itens)
        if qtd == 1:
            fala = f"Na sua agenda de hoje, o senhor possui 1 compromisso pendente registrado: {descricoes[0]}."
        else:
            fala = f"Na sua agenda de hoje, o senhor possui {qtd} compromissos pendentes: " + "; ".join(descricoes) + "."
    else:
        fala = "Sua agenda está livre no momento, senhor. Não constam lembretes ou compromissos pendentes registrados para hoje."

    return {
        "id": "card_agenda",
        "tipo": "agenda",
        "categoria": "AGENDA & COMPROMISSOS",
        "titulo": "Lembretes & Tarefas do Dia",
        "itens": itens,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 3. CARD DE MERCADO FINANCEIRO & COTAÇÕES
# ──────────────────────────────────────────────────────────

async def obter_card_mercado() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    
    dolar_val, dolar_pct = "5.06", 0.15
    euro_val, euro_pct = "5.67", 0.41
    btc_val, btc_pct = "81050", -0.76
    ibov_pts, ibov_pct = "206500", -0.18
    sp_pts, sp_pct = "5860", 0.25

    try:
        async with httpx.AsyncClient(headers=headers, timeout=3.0) as client:
            res_cambio, res_ibov, res_sp = await asyncio.gather(
                client.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval=1d&range=1d"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=1d"),
                return_exceptions=True
            )

            if isinstance(res_cambio, httpx.Response) and res_cambio.status_code == 200:
                dados = res_cambio.json()
                if "USDBRL" in dados:
                    dolar_val = f"{float(dados['USDBRL']['bid']):.2f}"
                    dolar_pct = float(dados['USDBRL']['pctChange'])
                if "EURBRL" in dados:
                    euro_val = f"{float(dados['EURBRL']['bid']):.2f}"
                    euro_pct = float(dados['EURBRL']['pctChange'])
                if "BTCUSD" in dados:
                    btc_val = f"{float(dados['BTCUSD']['bid']):,.0f}"
                    btc_pct = float(dados['BTCUSD']['pctChange'])

            if isinstance(res_ibov, httpx.Response) and res_ibov.status_code == 200:
                try:
                    meta = res_ibov.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    p = meta.get("regularMarketPrice")
                    pr = meta.get("chartPreviousClose")
                    if p and pr:
                        ibov_pts = f"{p:,.0f}"
                        ibov_pct = ((p - pr) / pr) * 100
                except Exception:
                    pass

            if isinstance(res_sp, httpx.Response) and res_sp.status_code == 200:
                try:
                    meta = res_sp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    p = meta.get("regularMarketPrice")
                    pr = meta.get("chartPreviousClose")
                    if p and pr:
                        sp_pts = f"{p:,.0f}"
                        sp_pct = ((p - pr) / pr) * 100
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"[BRIEFING] Erro ao obter dados do mercado financeiro: {e}")

    cotacoes = [
        {"nome": "Dólar Comercial", "simbolo": "USD/BRL", "valor": f"R$ {dolar_val}", "var": f"{dolar_pct:+.2f}%", "alta": dolar_pct >= 0},
        {"nome": "Euro Comercial", "simbolo": "EUR/BRL", "valor": f"R$ {euro_val}", "var": f"{euro_pct:+.2f}%", "alta": euro_pct >= 0},
        {"nome": "Bitcoin", "simbolo": "BTC/USD", "valor": f"US$ {btc_val}", "var": f"{btc_pct:+.2f}%", "alta": btc_pct >= 0},
        {"nome": "Ibovespa (B3)", "simbolo": "IBOV", "valor": f"{ibov_pts} pts", "var": f"{ibov_pct:+.2f}%", "alta": ibov_pct >= 0},
        {"nome": "S&P 500 (Wall St)", "simbolo": "S&P 500", "valor": f"{sp_pts} pts", "var": f"{sp_pct:+.2f}%", "alta": sp_pct >= 0}
    ]

    tendencia_dolar = "alta" if dolar_pct >= 0 else "queda"
    tendencia_ibov = "alta" if ibov_pct >= 0 else "queda"

    fala = (
        f"No mercado financeiro hoje, o dólar comercial opera em {tendencia_dolar} cotado a {dolar_val.replace('.', ',')} reais, "
        f"enquanto o euro está cotado a {euro_val.replace('.', ',')} reais. O bitcoin é negociado na faixa de {btc_val} dólares. "
        f"Na renda variável, o Ibovespa opera aos {ibov_pts} pontos e o índice americano S&P 500 aos {sp_pts} pontos."
    )

    return {
        "id": "card_mercado",
        "tipo": "mercado",
        "categoria": "MERCADO FINANCEIRO",
        "titulo": "Indicadores & Cotações Globais",
        "cotacoes": cotacoes,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 4. CARDS DE NOTÍCIAS ABRANGENTES COM IMAGEM REAL & NARRATIVA FLUIDA
# ──────────────────────────────────────────────────────────

def _imagem_eh_valida(url: str) -> bool:
    """Valida se a URL é de uma imagem real e não logos, favicons ou placeholders do Google News."""
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower().strip()
    termos_invalidos = [
        'googleusercontent.com', 'google.com', 'gstatic.com',
        'logo', 'favicon', 'icon', 'avatar', '1x1', 'pixel'
    ]
    if any(termo in url_lower for termo in termos_invalidos):
        return False
    return url_lower.startswith('http://') or url_lower.startswith('https://')

def _limpar_titulo_noticia(titulo: str) -> str:
    t = re.sub(r'\s+-\s+[^-]+$', '', titulo.strip())
    t = re.sub(r'\s*\|\s*[^|]+$', '', t.strip())
    return t.strip()

def _extrair_fonte(titulo: str, padrao: str = "Agência de Notícias") -> str:
    partes = titulo.strip().split(" - ")
    if len(partes) > 1 and len(partes[-1]) < 30:
        return partes[-1].strip()
    partes_pipe = titulo.strip().split(" | ")
    if len(partes_pipe) > 1 and len(partes_pipe[-1]) < 30:
        return partes_pipe[-1].strip()
    return padrao

def _limpar_html_resumo(texto: str) -> str:
    """Remove tags HTML, scripts, estilos e decodifica entidades para um resumo limpo de 2 linhas."""
    if not texto:
        return ""
    import html
    sem_scripts = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', texto, flags=re.DOTALL | re.IGNORECASE)
    sem_tags = re.sub(r'<[^>]+>', ' ', sem_scripts)
    texto_decod = html.unescape(sem_tags)
    limpo = re.sub(r'\s+', ' ', texto_decod).strip()
    limpo = re.sub(r'(Leia mais|Saiba mais|Confira|Veja mais).*$', '', limpo, flags=re.IGNORECASE).strip()
    return limpo

def _extrair_imagem_xml(item, desc_raw: str = "", content_raw: str = "") -> str | None:
    """Extrai a URL da foto real no XML buscando em media:content, media:thumbnail, enclosure e img src."""
    # 1. media:content (com e sem namespace)
    for tag in ('{http://search.yahoo.com/mrss/}content', 'media:content', 'content'):
        for el in item.findall(tag):
            u = el.attrib.get('url')
            if u and _imagem_eh_valida(u):
                return u

    # 2. media:thumbnail
    for tag in ('{http://search.yahoo.com/mrss/}thumbnail', 'media:thumbnail', 'thumbnail'):
        for el in item.findall(tag):
            u = el.attrib.get('url')
            if u and _imagem_eh_valida(u):
                return u

    # 3. enclosure
    for el in item.findall('enclosure'):
        u = el.attrib.get('url')
        if u and _imagem_eh_valida(u):
            return u

    # 4. tag <img> dentro do description ou content
    texto_html = f"{desc_raw} {content_raw}"
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', texto_html, re.IGNORECASE)
    for u in imgs:
        if _imagem_eh_valida(u):
            return u

    return None

async def _extrair_artigo_completo(client: httpx.AsyncClient, url: str) -> tuple[str | None, str]:
    """
    Baixa o HTML do link_artigo (timeout 3.5s) usando BeautifulSoup:
    - Extrai a og:image real da página (se disponível e válida).
    - Extrai todos os parágrafos <p> reais do corpo da matéria (filtrando parágrafos
      com mais de 45 caracteres e ignorando avisos de cookies/rodapé/redes sociais),
      juntando de 6 a 10 parágrafos em um conteudo_completo (separados por \n\n).
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None, ""

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        resp = await client.get(url, headers=headers, timeout=3.5, follow_redirects=True)
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Extração de og:image real
            og_img = None
            meta_og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if meta_og and meta_og.get("content"):
                c = meta_og.get("content").strip()
                if _imagem_eh_valida(c):
                    og_img = c

            # 2. Remoção de ruídos de navegação, rodapé e anúncios
            for tag in soup(["script", "style", "nav", "footer", "aside", "noscript", "header", "form"]):
                tag.decompose()

            # 3. Extração dos parágrafos do corpo da matéria
            termos_ignorar = [
                "cookie", "privacidade", "termos de uso", "direitos reservados",
                "todos os direitos", "inscreva-se", "newsletter", "compartilhe",
                "whatsapp", "telegram", "siga o", "redes sociais", "leia também",
                "veja também", "foto:", "crédito:", "publicidade", "assine"
            ]

            paragrafos = []
            for p in soup.find_all("p"):
                texto_p = p.get_text(separator=" ", strip=True)
                texto_p = re.sub(r'\s+', ' ', texto_p).strip()
                if len(texto_p) > 45:
                    p_lower = texto_p.lower()
                    if not any(termo in p_lower for termo in termos_ignorar):
                        paragrafos.append(texto_p)
                        if len(paragrafos) >= 10:
                            break

            conteudo_completo = "\n\n".join(paragrafos)
            return og_img, conteudo_completo
    except Exception as e:
        log.debug(f"[BRIEFING] Erro ao extrair artigo completo de {url}: {e}")

    return None, ""

async def _buscar_imagem_pagina(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=2.5, follow_redirects=True)
        if resp.status_code == 200:
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match:
                img = match.group(1).strip()
                if _imagem_eh_valida(img):
                    return img
            match2 = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text, re.IGNORECASE)
            if match2:
                img = match2.group(1).strip()
                if _imagem_eh_valida(img):
                    return img
    except Exception:
        pass
    return None

async def _buscar_imagem_fallback(client: httpx.AsyncClient, titulo: str, link: str = None) -> str | None:
    """Busca imagem alternativa no og:image da página da matéria ou via DuckDuckGo Imagens."""
    if link:
        img_og = await _buscar_imagem_pagina(client, link)
        if img_og and _imagem_eh_valida(img_og):
            return img_og

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(keywords=titulo, region="br-pt", max_results=2))
            for r in results:
                img_u = r.get("image")
                if img_u and _imagem_eh_valida(img_u):
                    return img_u
    except Exception as e:
        log.debug(f"[BRIEFING] Erro no fallback de imagem DDGS: {e}")
    return None

async def _obter_noticia_categoria(client: httpx.AsyncClient, cat: str, feeds_url: list[str], rotulo: str, fonte_padrao: str, prefixo_fala: str) -> dict:
    fallback_img = IMAGENS_FALLBACK.get(cat, IMAGENS_FALLBACK["mundo"])

    for feed_url in feeds_url:
        try:
            resp = await client.get(feed_url, timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                items = root.findall('.//item')
                if items:
                    item = items[0]
                    tit_raw = item.find('title').text if item.find('title') is not None else ""
                    desc_raw = item.find('description').text if item.find('description') is not None else ""
                    link_artigo = item.find('link').text if item.find('link') is not None else ""

                    tit_limpo = _limpar_titulo_noticia(tit_raw)
                    fonte = _extrair_fonte(tit_raw, fonte_padrao)
                    resumo_rss = _limpar_html_resumo(desc_raw)

                    # 1. Extração profunda do artigo completo e imagem da página original
                    og_img_artigo, conteudo_completo = await _extrair_artigo_completo(client, link_artigo)

                    # 2. Imagem real: XML > og:image do artigo > busca DuckDuckGo > fallback temático
                    img = _extrair_imagem_xml(item, desc_raw)
                    if not img or not _imagem_eh_valida(img):
                        if og_img_artigo and _imagem_eh_valida(og_img_artigo):
                            img = og_img_artigo
                        else:
                            img = await _buscar_imagem_fallback(client, tit_limpo, link_artigo)

                    if not img or not _imagem_eh_valida(img):
                        img = fallback_img

                    # 3. Monta resumo completo e informativo de 2 a 3 frases (~280 a 350 caracteres)
                    base_texto = conteudo_completo if (conteudo_completo and len(conteudo_completo) > len(resumo_rss)) else resumo_rss
                    if not base_texto or len(base_texto) < 30:
                        base_texto = f"{tit_limpo}. As movimentações e apurações sobre o tema continuam em andamento em tempo real."

                    frases = [f.strip() for f in re.split(r'(?<=[.!?])\s+', base_texto) if len(f.strip()) > 15]
                    resumo_card = " ".join(frases[:3]).strip()
                    if len(resumo_card) > 360:
                        resumo_card = resumo_card[:350].rsplit(' ', 1)[0] + "..."
                    elif len(resumo_card) < 200 and len(frases) > 3:
                        resumo_card = " ".join(frases[:4]).strip()
                        if len(resumo_card) > 360:
                            resumo_card = resumo_card[:350].rsplit(' ', 1)[0] + "..."

                    # Se conteudo_completo não foi extraído da URL, garante ao menos o resumo
                    if not conteudo_completo:
                        conteudo_completo = resumo_card

                    # 4. Narrativa de fala jornalística fluida (2 a 3 frases completas, até ~320 caracteres)
                    frases_fala = []
                    for f in frases:
                        # Evita repetir o título na frase informativa
                        if f.lower() not in tit_limpo.lower() and len(f) > 20:
                            frases_fala.append(f)
                        if len(frases_fala) >= 2:
                            break

                    if frases_fala:
                        fala_base = f"{prefixo_fala}, {tit_limpo}. " + " ".join(frases_fala)
                    else:
                        fala_base = f"{prefixo_fala}, {tit_limpo}. As movimentações recentes trazem desdobramentos estratégicos que seguem sob acompanhamento contínuo."

                    if len(fala_base) > 330:
                        fala = fala_base[:320].rsplit(' ', 1)[0]
                        if not fala.endswith(('.', '!', '?')):
                            fala += '.'
                    else:
                        fala = fala_base
                        if not fala.endswith(('.', '!', '?')):
                            fala += '.'

                    return {
                        "id": f"card_noticia_{cat}",
                        "tipo": "noticia",
                        "categoria": rotulo,
                        "titulo": tit_limpo,
                        "resumo": resumo_card,
                        "conteudo_completo": conteudo_completo,
                        "link": link_artigo,
                        "fonte": fonte,
                        "imagem": img,
                        "fala": fala
                    }
        except Exception as e_feed:
            log.debug(f"[BRIEFING] Tentando próximo feed da categoria {cat}: {e_feed}")

    # Fallback estático de emergência caso nenhum feed responda
    return {
        "id": f"card_noticia_{cat}",
        "tipo": "noticia",
        "categoria": rotulo,
        "titulo": f"Atualizações em {cat.title()}",
        "resumo": "Sistemas de inteligência continuam monitorando as principais movimentações em tempo real com apuração estratégica dos fatos.",
        "conteudo_completo": "Os canais oficiais e agências internacionais continuam transmitindo atualizações em tempo real. Os sistemas neurais do Jarvis mantêm vigilância ativa sobre os desdobramentos deste setor.",
        "link": feeds_url[0] if feeds_url else "",
        "fonte": fonte_padrao,
        "imagem": fallback_img,
        "fala": f"{prefixo_fala}, os sistemas continuam monitorando as movimentações estratégicas em {cat.title()} para o senhor."
    }

async def obter_cards_noticias() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    
    # Feeds diretos de portais que entregam imagens reais no XML e páginas abertas
    feeds_config = [
        (
            "mundo",
            ["https://feeds.bbci.co.uk/portuguese/rss.xml", "https://g1.globo.com/rss/g1/mundo/"],
            "RADAR // INTERNACIONAL & EUA",
            "BBC News Brasil",
            "No cenário global"
        ),
        (
            "economia",
            ["https://g1.globo.com/rss/g1/economia/", "https://www.infomoney.com.br/feed/"],
            "RADAR // ECONOMIA & MERCADOS",
            "G1 Economia",
            "No front econômico"
        ),
        (
            "tecnologia",
            ["https://g1.globo.com/rss/g1/tecnologia/", "https://rss.tecmundo.com.br/feed"],
            "RADAR // TECNOLOGIA & IA",
            "G1 Tecnologia",
            "No setor tecnológico"
        ),
        (
            "brasil",
            ["https://g1.globo.com/rss/g1/politica/", "https://feeds.bbci.co.uk/portuguese/rss.xml"],
            "RADAR // POLÍTICA & BRASIL",
            "G1 Política",
            "No panorama nacional"
        )
    ]

    async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
        tarefas = [
            _obter_noticia_categoria(client, cat, urls, rotulo, fonte, pref)
            for cat, urls, rotulo, fonte, pref in feeds_config
        ]
        cards = await asyncio.gather(*tarefas)
        return list(cards)

# ──────────────────────────────────────────────────────────
# 5. COREOGRAFIA SINCRONIZADA DO BRIEFING
# ──────────────────────────────────────────────────────────

async def executar_briefing_coreografado():
    """
    Executa a sequência completa de Briefing Matinal:
    Fase 1: Radar / Telemetria inicial com card central e fala introdutória.
    Fase 2: Desfile de cards (Clima, Agenda, Mercado, Notícias), sincronizando
            a fala de cada card com o foco central e posterior ancoragem no dock inferior.
    Fase 3: Encerramento elegante com encerramento de todos os cards no dock.
    """
    global BRIEFING_EM_ANDAMENTO
    if BRIEFING_EM_ANDAMENTO:
        log.warning("[BRIEFING] Briefing já está em andamento. Ignorando nova requisição.")
        return

    BRIEFING_EM_ANDAMENTO = True
    log.info("[BRIEFING] Iniciando coreografia do Briefing Matinal holográfico...")

    try:
        # Notifica início da coleta de dados
        await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.2, texto="Compilando telemetria matinal...", padrao="tarefa")

        # Coleta de todos os dados e cards em paralelo para velocidade máxima
        card_clima, card_agenda, card_mercado, cards_noticias = await asyncio.gather(
            obter_card_clima(),
            obter_card_agenda(),
            obter_card_mercado(),
            obter_cards_noticias()
        )

        cards_briefing = [card_clima, card_agenda, card_mercado] + cards_noticias
        global ULTIMO_BRIEFING_CARDS
        ULTIMO_BRIEFING_CARDS = list(cards_briefing)

        # Monta resumo textual estruturado de todos os 7 cards e salva IMEDIATAMENTE na memória
        data_hora_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
        linhas_resumo = [
            f"[BRIEFING MATINAL CONSOLIDADO - {data_hora_str}]",
            f"1. CLIMA ({card_clima.get('cidade')}): {card_clima.get('fala')}",
            f"2. AGENDA: {card_agenda.get('fala')}",
            f"3. MERCADO FINANCEIRO: {card_mercado.get('fala')}"
        ]
        for idx, nc in enumerate(cards_noticias, start=4):
            cat_label = nc.get('categoria', 'NOTÍCIA').replace('RADAR // ', '')
            link_txt = f" | Link: {nc.get('link')}" if nc.get('link') else ""
            linhas_resumo.append(
                f"{idx}. {cat_label}: {nc.get('titulo')}{link_txt}\n"
                f"   Fonte: {nc.get('fonte')}\n"
                f"   Resumo: {nc.get('resumo')}\n"
                f"   Artigo: {nc.get('conteudo_completo', '')[:700]}"
            )

        resumo_completo_briefing = "\n\n".join(linhas_resumo)

        try:
            from MODULOS.memory import memory_short, memory_long
            memory_short.adicionar_mensagem("assistant", resumo_completo_briefing)
            memory_long.registrar_conversa_global("assistant", resumo_completo_briefing)
            log.info("[BRIEFING] Resumo consolidado do briefing registrado com sucesso no memory_short e memory_long!")
        except Exception as e_mem:
            log.error(f"[BRIEFING] Erro ao gravar briefing na memória: {e_mem}")

        etapas_radar = ["CLIMA", "AGENDA", "MERCADO", "MUNDO & EUA", "ECONOMIA", "TECNOLOGIA", "BRASIL"]

        # ── FASE 1: RADAR / TELEMETRIA INICIAL ──
        await enviar_evento_interface({
            "type": "briefing_start",
            "etapas": etapas_radar,
            "hora": datetime.now().strftime("%H:%M")
        })

        fala_intro = "Bom dia, senhor. Iniciando a telemetria matinal e consolidando os dados essenciais do seu dia."
        await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=fala_intro, padrao="falando")
        await voice_manager.falar("Jarvis", fala_intro, prioridade=1)

        await asyncio.sleep(0.3)
        while voice_manager.STATUS_FALANDO:
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.5)

        # ── FASE 2: DESFILE DE CARDS EM FOCO CENTRAL ──
        for idx, card in enumerate(cards_briefing):
            log.info(f"[BRIEFING] Exibindo card {idx + 1}/{len(cards_briefing)}: {card.get('titulo')}")

            # 1. Envia evento para a interface focar esse card no centro da esfera
            await enviar_evento_interface({
                "type": "briefing_card_focus",
                "card": card,
                "indice": idx,
                "total": len(cards_briefing)
            })

            # 2. Fala o conteúdo específico desse card
            fala_card = card.get("fala", "")
            if fala_card:
                await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=card.get("titulo", ""), padrao="falando")
                await voice_manager.falar("Jarvis", fala_card, prioridade=1)

                await asyncio.sleep(0.3)
                while voice_manager.STATUS_FALANDO:
                    await asyncio.sleep(0.1)

            # Pausa de transição suave para apreciação visual do card antes do próximo
            await asyncio.sleep(0.6)

        # ── FASE 3: ENCERRAMENTO E ESTACIONAMENTO DOS CARDS ──
        await enviar_evento_interface({
            "type": "briefing_end",
            "total_cards": len(cards_briefing)
        })

        fala_fim = "Esse é o panorama consolidado do momento, senhor. Hoje, mantenha o foco no essencial."
        await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.6, texto=fala_fim, padrao="conversa")
        await voice_manager.falar("Jarvis", fala_fim, prioridade=1)

        await asyncio.sleep(0.3)
        while voice_manager.STATUS_FALANDO:
            await asyncio.sleep(0.1)

        log.info("[BRIEFING] Briefing Matinal concluído com sucesso.")

    except Exception as e:
        log.error(f"[BRIEFING] Erro durante o briefing coreografado: {e}")
        await atualizar_jarvis(cor_hex="#ff0055", intensidade=0.2, texto="Erro no briefing", padrao="alerta")
    finally:
        BRIEFING_EM_ANDAMENTO = False


async def responder_followup_briefing(pergunta: str) -> str:
    """
    Responde perguntas de aprofundamento do usuário sobre o Briefing Matinal.
    Identifica o card correspondente em ULTIMO_BRIEFING_CARDS, busca aprofundamento
    via conteúdo completo ou URL (usando obter_conteudo_url do mcp_client) e gera
    uma resposta profunda, precisa e elegante com o LLM.
    """
    global ULTIMO_BRIEFING_CARDS
    from MODULOS.skills import mcp_client
    from MODULOS.brain.selector import selector as brain_selector
    from MODULOS.memory import memory_short, memory_long
    import ollama

    pergunta_lower = pergunta.lower()

    # Se não temos cards gravados do briefing, recorre ao MCP/Web
    if not ULTIMO_BRIEFING_CARDS:
        log.info("[BRIEFING/FOLLOWUP] Nenhum card de briefing em cache. Delegando para WEB_MCP...")
        return await mcp_client.executar_comandos_mcp_ou_web(pergunta)

    # 1. Tenta identificar qual card o usuário está perguntando
    palavras_query = set(re.findall(r'\b\w{3,}\b', pergunta_lower))
    stopwords = {
        "jarvis", "fale", "mais", "sobre", "esse", "essa", "este", "esta", "assunto",
        "noticia", "notícia", "explique", "melhor", "detalhe", "conte", "qual",
        "quem", "como", "onde", "quando", "porque", "para", "com", "uma", "uns",
        "umas", "pelo", "pela", "pelas", "pelos", "voce", "você", "falou", "hoje",
        "governo", "disse", "bom", "dia", "favor"
    }
    termos_relevantes = [p for p in palavras_query if p not in stopwords]

    melhor_card = None
    melhor_score = 0

    for card in ULTIMO_BRIEFING_CARDS:
        card_texto = (
            f"{card.get('titulo', '')} {card.get('resumo', '')} "
            f"{card.get('categoria', '')} {card.get('tipo', '')} "
            f"{card.get('conteudo_completo', '')}"
        ).lower()

        score = 0
        for termo in termos_relevantes:
            if termo in card_texto:
                score += 2
        for termo in termos_relevantes:
            if termo in card.get('titulo', '').lower():
                score += 3

        if score > melhor_score:
            melhor_score = score
            melhor_card = card

    # Se a query menciona governo ou brasil ou economia e nenhum score bateu
    if not melhor_card or melhor_score == 0:
        if "governo" in pergunta_lower or "brasil" in pergunta_lower or "lei" in pergunta_lower:
            for card in ULTIMO_BRIEFING_CARDS:
                if card.get("id") in ("card_noticia_brasil", "card_noticia_economia"):
                    melhor_card = card
                    break

    # Se ainda não encontrou card específico, verifica lista de notícias
    noticias = [c for c in ULTIMO_BRIEFING_CARDS if c.get("tipo") == "noticia"]
    if not melhor_card and noticias:
        if any(k in pergunta_lower for k in ["quais", "todas", "qual é a notícia", "qual e a noticia", "quais as"]):
            titulos_noticias = [f"• {c.get('categoria', 'Radar')}: {c.get('titulo')}" for c in noticias]
            return (
                "Senhor, no Briefing Matinal de hoje destacamos as seguintes notícias:\n"
                + "\n".join(titulos_noticias) +
                "\n\nSobre qual destes temas o senhor gostaria que eu me aprofundasse?"
            )
        melhor_card = noticias[0]

    if not melhor_card:
        return await mcp_client.executar_comandos_mcp_ou_web(pergunta)

    # 2. Contexto do card selecionado
    titulo_card = melhor_card.get("titulo", "")
    fonte_card = melhor_card.get("fonte", "")
    link_card = melhor_card.get("link", "")
    artigo_texto = melhor_card.get("conteudo_completo") or melhor_card.get("resumo") or ""

    # Se o texto for curto e houver link original, faz fetch da URL para profundidade total
    if len(artigo_texto) < 250 and link_card:
        try:
            conteudo_extra = await mcp_client.obter_conteudo_url(link_card)
            if conteudo_extra and len(conteudo_extra) > 100:
                artigo_texto = conteudo_extra
        except Exception as e_fetch:
            log.debug(f"[BRIEFING/FOLLOWUP] Erro no fetch da URL {link_card}: {e_fetch}")

    # 3. Síntese neural profunda com LLM
    modelo, _ = brain_selector.escolher_melhor_modelo("CONVERSA")
    prompt_sistema = (
        "Você é o assistente Jarvis.\n"
        "O senhor solicitou um aprofundamento e detalhes adicionais sobre o seguinte tópico do Briefing Matinal:\n"
        f"Assunto/Título: {titulo_card}\n"
        f"Fonte: {fonte_card}\n"
        f"Link de referência: {link_card}\n"
        f"Informações completas e parágrafos do artigo:\n{artigo_texto}\n\n"
        "Instruções:\n"
        "1. Explique detalhadamente ao senhor o que está acontecendo, os motivos, números e desdobramentos.\n"
        "2. Seja claro, objetivo, seguro e elegante em português do Brasil.\n"
        "3. Sua resposta será falada em voz alta pelo TTS: não utilize listas com asteriscos (*), emojis exagerados ou markdown complexo, mantendo parágrafos fluidos e naturais."
    )

    mensagens = [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": pergunta}
    ]

    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: ollama.chat(model=modelo, messages=mensagens)
        )
        resposta = res.get("message", {}).get("content", "").strip()
        if resposta:
            # Registra no histórico de conversa
            memory_short.adicionar_mensagem("user", pergunta)
            memory_short.adicionar_mensagem("assistant", resposta)
            memory_long.registrar_conversa_global("assistant", resposta)
            return resposta
    except Exception as e:
        log.error(f"[BRIEFING/FOLLOWUP] Erro no LLM ao responder followup: {e}")

    # Resposta de fallback
    return f"Senhor, sobre '{titulo_card}': {artigo_texto[:350]}..."

```


==================================================
 ARQUIVO: .\MODULOS\skills\fii_monitor.py
==================================================

```python
import time
import re
import requests
try:
    import yfinance as yf
except ImportError:
    yf = None
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class FIIMonitor:
    def __init__(self, tickers: List[str]):
        """
        Módulo de Monitoramento de FIIs integrado.
        :param tickers: Lista contendo os códigos dos ativos. Ex: ["MXRF11", "XPML11"]
        """
        self.tickers = tickers
        # Headers forjados para simular um browser real e evitar HTTP 403 Forbidden 
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }

    def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, float]]:
        """
        Realiza o scraping no Fundamentus para extrair P/VP e Dividend Yield de forma estática (rápido).
        """
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
        try:
            response = requests.get(url, headers=self.session_headers, timeout=8)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extração agressiva baseada em regex para evitar quebra caso o site sofra leves mutações no layout
            pvp_span = soup.find('span', string=re.compile(r'P/VP', re.IGNORECASE))
            pvp_value = 0.0
            if pvp_span:
                # O valor fica no próximo <td> referente ao <span> da label
                pvp_str = pvp_span.find_parent('td').find_next_sibling('td').text.strip()
                pvp_value = float(pvp_str.replace(',', '.'))

            dy_span = soup.find('span', string=re.compile(r'Div\. Yield', re.IGNORECASE))
            dy_value = 0.0
            if dy_span:
                dy_str = dy_span.find_parent('td').find_next_sibling('td').text.strip()
                dy_value = float(dy_str.replace('%', '').replace(',', '.'))

            return {'P/VP': pvp_value, 'DY': dy_value}
            
        except requests.exceptions.Timeout:
            print(f"[Aviso Jarvis] Timeout ao buscar fundamentos de {ticker}.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[Aviso Jarvis] Falha de HTTP no scraping de {ticker}: {e}")
            return None
        except Exception as e:
            print(f"[Aviso Jarvis] Falha no parsing HTML de {ticker}: {e}")
            return None

    def _fetch_current_price(self, ticker: str) -> Optional[float]:
        """
        Realiza consulta do preço em base D0 operando via Yahoo Finance.
        """
        try:
            yf_ticker = yf.Ticker(f"{ticker}.SA")
            # Usa 'history' em vez de 'info' por ser muito menos sujeito a falhas em atualizações do yfinance.
            data = yf_ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                return round(float(data['Close'].iloc[-1]), 2)
                
            # Fallback para o endpoint rápido do yfinance se a bolsa ainda não tiver volumes pro "history" atômico
            return round(float(yf_ticker.fast_info['lastPrice']), 2)
            
        except Exception as e:
            print(f"[Aviso Jarvis] Erro na requisição yfinance para {ticker}: {e}")
            return None

    def get_market_report(self) -> str:
        """
        Processa ativamente todos os indicadores em cache temporário.
        Processamento serial otimizado para o loop principal do TTS do LLM.
        """
        linhas_relatorio = ["Relatório de fundos imobiliários, senhor:"]
        
        for ticker in self.tickers:
            price = self._fetch_current_price(ticker)
            fundamentals = self._fetch_fundamentals(ticker)
            
            # Se algum falhou na rede, pula a iteração para não enviar "None" pro gerador de texto
            if price is None or fundamentals is None:
                print(f"[Aviso Jarvis] Pulando {ticker} devido a falha na coleta de dados.")
                continue

            pvp = fundamentals['P/VP']
            dy = fundamentals['DY']
            
            # Application Logic Requirement: OPORTUNIDADE ou AGUARDAR
            status = "oportunidade" if (pvp <= 1.05 and dy > 9.6) else "aguardar"
            
            # Formatação localizada e limpa para leitura por modelo de voz (Phonetic friendly)
            preco_str = f"{price:.2f}".replace('.', ',')
            pvp_str = f"{pvp:.2f}".replace('.', ',')
            dy_str = f"{dy:.1f}".replace('.', ',')
            
            linhas_relatorio.append(
                f"O fundo {ticker} está cotado em {preco_str} reais, "
                f"com preço sobre valor patrimonial de {pvp_str} e rendimento de {dy_str} por cento ao ano. "
                f"No momento, o status é de {status}."
            )
            
            # Delay de 1s pra não engatilhar blocos no server side da fundamentus
            time.sleep(1)

        if len(linhas_relatorio) == 1:
            return "Senhor, tive dificuldade em acessar os dados financeiros no momento. Por favor, tente novamente em instantes."

        return " ".join(linhas_relatorio)

# Ponto de acesso modular -> Chamar no arquivo de skills principal do seu assistente
def obter_resumo_fiis() -> str:
    ativos = ["MXRF11", "XPML11", "VGHF11", "BTLG11"]
    monitor = FIIMonitor(tickers=ativos)
    return monitor.get_market_report()

# Teste local da pipeline (Não roda se importado em outro arquivo)
if __name__ == "__main__":
    print("[Jarvis Debug Engine] Buscando métricas...\n")
    relatorio_para_tts = obter_resumo_fiis()
    print(relatorio_para_tts)

```


==================================================
 ARQUIVO: .\MODULOS\skills\hardware_module.py
==================================================

```python
import psutil
import aiohttp
import asyncio
import subprocess
import re

from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice import voice_manager

try:
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    import pynvml
    pynvml.nvmlInit()
    gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _NVIDIA_OK = True
except Exception:
    pynvml = None
    gpu_handle = None
    _NVIDIA_OK = False

def garantir_monitor_aberto():
    try:
        check = subprocess.check_output('tasklist', shell=True).decode('latin-1')
        if "LibreHardwareMonitor.exe" not in check:
            print("[SISTEMA] Iniciando Monitor de Hardware silenciosamente (Via Tarefa)...")
            subprocess.Popen('schtasks /run /tn "LibreHardwareMonitorTask"', shell=True)
        else:
            print("[HARDWARE_MODULE] Monitor já está em execução.")
    except Exception as e:
        print(f"[ERRO AO ABRIR MONITOR]: {e}")

async def _buscar_lhm() -> dict:
    """Busca o JSON completo do LibreHardwareMonitor. Retorna {} se indisponível."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8085/data.json", timeout=2) as r:
                if r.status == 200:
                    return await r.json()
    except Exception:
        pass
    return {}

async def ler_temperatura_cpu_lhm():
    palavras_cpu = ['Ryzen', 'Core', 'Intel', 'AMD', 'CPU']
    dados = await _buscar_lhm()
    try:
        for hardware in dados['Children'][0]['Children']:
            if any(p in hardware['Text'] for p in palavras_cpu):
                for sensor_group in hardware['Children']:
                    if sensor_group['Text'] == 'Temperatures':
                        for sensor in sensor_group['Children']:
                            if 'Core' in sensor['Text'] or 'Tctl' in sensor['Text'] or 'Package' in sensor['Text']:
                                val = sensor['Value'].replace(',', '.').replace(' °C', '')
                                return float(val)
    except Exception:
        pass
    return "N/A"

async def _ler_gpu_lhm() -> dict:
    """Lê dados da GPU via LHM — funciona com AMD e NVIDIA."""
    resultado = {"gpu_load": 0, "gpu_temp": "N/A", "vram_used_gb": "N/A", "gpu_power": "N/A"}
    if _NVIDIA_OK and gpu_handle:
        try:
            rates = pynvml.nvmlDeviceGetUtilizationRates(gpu_handle)
            resultado['gpu_load'] = round(float(rates.gpu), 1)
            resultado['gpu_temp'] = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            resultado['gpu_power'] = round(pynvml.nvmlDeviceGetPowerUsage(gpu_handle) / 1000.0, 1)
            meminfo = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
            resultado['vram_used_gb'] = round(meminfo.used / (1024 ** 3), 2)
            return resultado
        except Exception:
            pass

    dados = await _buscar_lhm()
    palavras_gpu = ['GPU', 'Radeon', 'GeForce', 'RX ', 'RTX', 'GTX']
    try:
        for hardware in dados.get('Children', [{}])[0].get('Children', []):
            if any(p in hardware['Text'] for p in palavras_gpu):
                for sensor_group in hardware.get('Children', []):
                    if sensor_group['Text'] == 'Temperatures':
                        for s in sensor_group.get('Children', []):
                            if 'GPU' in s['Text'] or 'Core' in s['Text']:
                                resultado['gpu_temp'] = float(s['Value'].replace(',', '.').replace(' °C', ''))
                    elif sensor_group['Text'] == 'Load':
                        for s in sensor_group.get('Children', []):
                            if 'GPU Core' in s['Text'] or s['Text'] == 'GPU Core':
                                val = s['Value'].replace(',', '.').replace(' %', '')
                                try:
                                    resultado['gpu_load'] = round(float(val), 1)
                                except Exception:
                                    pass
                    elif sensor_group['Text'] == 'Data':
                        for s in sensor_group.get('Children', []):
                            if 'Memory Used' in s['Text']:
                                val = s['Value'].replace(',', '.').replace(' MB', '').replace(' GB', '')
                                try:
                                    resultado['vram_used_gb'] = round(float(val) / 1024, 2) if 'MB' in s['Value'] else round(float(val), 2)
                                except Exception:
                                    pass
                    elif sensor_group['Text'] == 'Powers':
                        for s in sensor_group.get('Children', []):
                            if 'GPU' in s['Text']:
                                resultado['gpu_power'] = round(float(s['Value'].replace(',', '.').replace(' W', '')), 1)
    except Exception:
        pass
    return resultado

def listar_processos_vram() -> str:
    """Lista processos usando VRAM. NVIDIA via pynvml, AMD via psutil (aproximado)."""
    if _NVIDIA_OK:
        try:
            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(gpu_handle)
            procs += pynvml.nvmlDeviceGetGraphicsRunningProcesses(gpu_handle)
            if not procs:
                return "Nenhum processo usando VRAM no momento."
            linhas = []
            vistos = set()
            for p in procs:
                if p.pid in vistos:
                    continue
                vistos.add(p.pid)
                try:
                    nome = psutil.Process(p.pid).name()
                except Exception:
                    nome = f"PID {p.pid}"
                mb = round(p.usedGpuMemory / (1024 ** 2), 1) if p.usedGpuMemory else 0
                linhas.append(f"{nome}: {mb}MB")
            return ", ".join(linhas)
        except Exception as e:
            return f"Erro ao listar processos: {e}"
    else:
        try:
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if p.info['memory_info'].rss > 50 * 1024 * 1024:
                        procs.append((p.info['name'], round(p.info['memory_info'].rss / (1024**2), 1)))
                except Exception:
                    pass
            procs.sort(key=lambda x: x[1], reverse=True)
            top = procs[:5]
            return "(estimativa RAM) " + ", ".join(f"{n}: {m}MB" for n, m in top)
        except Exception:
            return "Não foi possível listar processos."

async def obter_status_hardware(foco=None):
    status = {}

    if _NVIDIA_OK and gpu_handle:
        try:
            status["gpu_temp"]     = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            status["gpu_power"]    = round(pynvml.nvmlDeviceGetPowerUsage(gpu_handle) / 1000.0, 1)
            meminfo                = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
            status["vram_used_gb"] = round(meminfo.used / (1024 ** 3), 2)
        except Exception:
            status["gpu_temp"] = status["gpu_power"] = status["vram_used_gb"] = "N/A"
    else:
        gpu_lhm = await _ler_gpu_lhm()
        status["gpu_temp"]     = gpu_lhm["gpu_temp"]
        status["gpu_power"]    = gpu_lhm["gpu_power"]
        status["vram_used_gb"] = gpu_lhm["vram_used_gb"]

    status["ram_used_percent"]  = psutil.virtual_memory().percent
    status["cpu_usage_percent"] = psutil.cpu_percent(interval=None)
    status["cpu_temp"]          = await ler_temperatura_cpu_lhm()

    if foco == "GPU":
        return f"A GPU está em {status['gpu_temp']} graus, consumindo {status['gpu_power']}W."
    elif foco == "CPU":
        return f"A CPU está com {status['cpu_usage_percent']}% de uso e {status['cpu_temp']} graus."
    elif foco == "VRAM":
        processos = listar_processos_vram()
        return f"VRAM em uso: {status['vram_used_gb']}GB. Processos: {processos}"
    elif foco == "RAM":
        return f"A RAM está com {status['ram_used_percent']}% de uso."

    return (
        f"Sensores: CPU {status['cpu_temp']}°C ({status['cpu_usage_percent']}%). "
        f"RAM {status['ram_used_percent']}%. "
        f"GPU {status['gpu_temp']}°C (VRAM: {status['vram_used_gb']}GB, Energia: {status['gpu_power']}W)."
    )

async def sentinela_hardware():
    while True:
        try:
            temps_alerta = []
            if _NVIDIA_OK and gpu_handle:
                try:
                    gpu_t = pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                    if isinstance(gpu_t, (int, float)) and gpu_t > 85.0:
                        temps_alerta.append(("GPU", gpu_t))
                except Exception:
                    pass
            
            cpu_t = await ler_temperatura_cpu_lhm()
            if isinstance(cpu_t, (int, float)) and cpu_t > 85.0:
                temps_alerta.append(("CPU", cpu_t))

            if temps_alerta:
                comp, val = max(temps_alerta, key=lambda x: x[1])
                msg_alerta = f"ALERTA TÉRMICO: {comp} atingiu {val:.0f}°C!"
                await atualizar_jarvis(cor_hex="#ff0000", texto=msg_alerta, padrao="alerta")
                await voice_manager.falar("Sentinela", msg_alerta, prioridade=0)
                await asyncio.sleep(6)
                await atualizar_jarvis(cor_hex="#00ffff", texto="Sistemas normalizados", padrao="conversa")
        except asyncio.CancelledError:
            break
        except Exception as e:
            pass
        await asyncio.sleep(30)

```


==================================================
 ARQUIVO: .\MODULOS\skills\mcp_client.py
==================================================

```python
"""
mcp_client.py
─────────────
Cliente e Gerenciador de Ferramentas MCP (Model Context Protocol) para o Jarvis.
Permite integração com ferramentas externas, servidores MCP oficiais e provedores
de busca na web em tempo real (DuckDuckGo, extração web, clima/tempo), com fallback nativo.
"""

import os
import json
import asyncio
import re
import httpx
import urllib.parse
from typing import Any
from MODULOS.system.logger import log
from MODULOS.brain.selector import selector as brain_selector

MCP_CONFIG_FILE = "DADOS/mcp_servers.json"
NEWS_CONFIG_FILE = "DADOS/news_config.json"

FEEDS_RSS_BRIEFING = {
    "mundo": {
        "rotulo": "🌍 CENÁRIO INTERNACIONAL / EUA & GEOPOLÍTICA",
        "url": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 3
    },
    "economia": {
        "rotulo": "📈 ECONOMIA, MERCADOS & EMPRESAS",
        "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 3
    },
    "brasil": {
        "rotulo": "🇧🇷 BRASIL & POLÍTICA NACIONAL",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 2
    },
    "tecnologia": {
        "rotulo": "💻 TECNOLOGIA, CIÊNCIA & IA",
        "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 2
    }
}

def carregar_config_noticias() -> dict:
    if os.path.exists(NEWS_CONFIG_FILE):
        try:
            with open(NEWS_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[MCP/NEWS] Erro ao carregar config notícias: {e}")
    return {
        "categorias": ["mundo", "economia", "brasil", "tecnologia"],
        "incluir_cotacoes": True,
        "detalhamento": "completo"
    }

def salvar_config_noticias(cfg: dict) -> dict:
    os.makedirs(os.path.dirname(NEWS_CONFIG_FILE), exist_ok=True)
    try:
        with open(NEWS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"[MCP/NEWS] Erro ao salvar config notícias: {e}")
    return cfg

def _limpar_titulo_noticia(titulo: str) -> str:
    """Remove o sufixo ' - Veículo' e espaços extras."""
    t = re.sub(r'\s+-\s+[^-]+$', '', titulo.strip())
    return t.strip()

async def obter_panorama_mercado() -> str:
    """
    Busca em ~1 segundo cotações globais e variação percentual de hoje:
    Dólar, Euro, Bitcoin (AwesomeAPI) e Ibovespa, S&P 500 (Yahoo Finance).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    linhas = []
    try:
        async with httpx.AsyncClient(headers=headers, timeout=2.5) as client:
            res_cambio, res_ibov, res_sp = await asyncio.gather(
                client.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval=1d&range=1d"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=1d"),
                return_exceptions=True
            )

            if isinstance(res_cambio, httpx.Response) and res_cambio.status_code == 200:
                dados = res_cambio.json()
                if "USDBRL" in dados:
                    d = dados["USDBRL"]
                    linhas.append(f"• Dólar Comercial: R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}%)")
                if "EURBRL" in dados:
                    d = dados["EURBRL"]
                    linhas.append(f"• Euro Comercial: R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}%)")
                if "BTCUSD" in dados:
                    d = dados["BTCUSD"]
                    linhas.append(f"• Bitcoin: US$ {float(d['bid']):,.0f} ({float(d['pctChange']):+.2f}%)")

            if isinstance(res_ibov, httpx.Response) and res_ibov.status_code == 200:
                try:
                    meta = res_ibov.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")
                    if price and prev:
                        var = ((price - prev) / prev) * 100
                        linhas.append(f"• Ibovespa (B3 Brasil): {price:,.0f} pts ({var:+.2f}%)")
                except Exception:
                    pass

            if isinstance(res_sp, httpx.Response) and res_sp.status_code == 200:
                try:
                    meta = res_sp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")
                    if price and prev:
                        var = ((price - prev) / prev) * 100
                        linhas.append(f"• S&P 500 (Wall St EUA): {price:,.0f} pts ({var:+.2f}%)")
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"[MCP/NEWS] Falha ao coletar panorama de mercado: {e}")

    if linhas:
        return "📊 COTAÇÕES GLOBAIS E MERCADO FINANCEIRO HOJE:\n" + "\n".join(linhas)
    return ""

async def _buscar_feed_categoria(client: httpx.AsyncClient, cat_id: str, titulos_vistos: set) -> tuple[str, list[str]]:
    info = FEEDS_RSS_BRIEFING.get(cat_id)
    if not info:
        return "", []
    rotulo = info["rotulo"]
    url = info["url"]
    limite = info["limite"]

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            items = root.findall('.//item')
            noticias = []
            for it in items:
                title_el = it.find('title')
                if title_el is not None and title_el.text:
                    tit_limpo = _limpar_titulo_noticia(title_el.text)
                    chave = re.sub(r'[^a-zA-Z0-9]', '', tit_limpo.lower())[:35]
                    if chave in titulos_vistos:
                        continue
                    titulos_vistos.add(chave)
                    noticias.append(f"• {tit_limpo}")
                    if len(noticias) >= limite:
                        break
            return rotulo, noticias
    except Exception as e:
        log.warning(f"[MCP/NEWS] Erro ao buscar feed '{cat_id}': {e}")
    return rotulo, []

async def buscar_briefing_executivo_global() -> str:
    """
    Executa o Briefing Executivo Global Multi-Fontes:
    Busca em paralelo no Google News RSS (Mundo, Economia, Brasil, Tecnologia)
    e anexa o panorama de cotações financeiras em tempo real no topo.
    """
    config = carregar_config_noticias()
    cats_ativas = config.get("categorias", ["mundo", "economia", "brasil", "tecnologia"])
    incluir_cotacoes = config.get("incluir_cotacoes", True)

    blocos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}

    log.info(f"[MCP/NEWS] Compilando Briefing Executivo Global Multi-Fontes (Categorias: {cats_ativas})...")

    titulos_vistos = set()
    async with httpx.AsyncClient(headers=headers, timeout=5.0, follow_redirects=True) as client:
        tarefas = []
        if incluir_cotacoes:
            tarefas.append(obter_panorama_mercado())

        for cat in cats_ativas:
            if cat in FEEDS_RSS_BRIEFING:
                tarefas.append(_buscar_feed_categoria(client, cat, titulos_vistos))

        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        idx = 0
        if incluir_cotacoes:
            res_cotacoes = resultados[0]
            idx += 1
            if isinstance(res_cotacoes, str) and res_cotacoes.strip():
                blocos.append(res_cotacoes.strip())

        for res in resultados[idx:]:
            if isinstance(res, tuple):
                rotulo, noticias = res
                if noticias:
                    blocos.append(f"{rotulo}:\n" + "\n".join(noticias))

    if blocos:
        return "[BRIEFING EXECUTIVO GLOBAL - DADOS EM TEMPO REAL DE HOJE]\n\n" + "\n\n".join(blocos)

    return await buscar_web("principais notícias hoje brasil mundo tecnologia economia", max_resultados=6)

# ──────────────────────────────────────────────────────────
#  FERRAMENTAS NATIVAS DE FALLBACK (OUT-OF-THE-BOX)
# ──────────────────────────────────────────────────────────

async def buscar_noticias_hoje(tema: str = "") -> str:
    """
    Consulta manchetes e notícias em tempo real via feeds RSS do Google News e Yahoo Finance.
    Se o tema for geral/vazio, compila o Briefing Executivo Global Multi-Fontes em paralelo.
    Se o tema for específico, realiza a busca focada.
    """
    tema_limpo = (tema or "").strip().lower()
    termos_genericos = [
        "", "mundo", "hoje", "principais", "notícias", "noticias", "geral",
        "brasil", "ultimas", "últimas", "notícia", "noticia", "dia", "acontecendo",
        "panorama", "briefing", "resumo", "giro", "manchetes", "manchete"
    ]

    if tema_limpo in termos_genericos or not tema_limpo:
        return await buscar_briefing_executivo_global()

    for stop in ["notícias de", "noticias de", "notícias sobre", "noticias sobre", "notícias", "noticias", "sobre"]:
        tema_limpo = tema_limpo.replace(stop, "").strip()

    if not tema_limpo:
        return await buscar_briefing_executivo_global()

    url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(tema_limpo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    log.info(f"[MCP/NEWS] Buscando notícias sobre '{tema_limpo}' via Google News RSS...")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                items = root.findall('.//item')
                if items:
                    noticias = []
                    titulos_vistos = set()
                    for it in items[:6]:
                        title_el = it.find('title')
                        pub_el = it.find('pubDate')
                        if title_el is not None and title_el.text:
                            tit = _limpar_titulo_noticia(title_el.text)
                            chave = re.sub(r'[^a-zA-Z0-9]', '', tit.lower())[:35]
                            if chave in titulos_vistos:
                                continue
                            titulos_vistos.add(chave)
                            pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                            if pub:
                                noticias.append(f"• {tit} ({pub})")
                            else:
                                noticias.append(f"• {tit}")
                    if noticias:
                        return f"Notícias em tempo real sobre '{tema_limpo}' obtidas hoje:\n" + "\n".join(noticias)
    except Exception as e:
        log.error(f"[MCP/NEWS] Erro ao buscar Google News RSS para '{tema_limpo}': {e}")

    return await buscar_web(f"noticias {tema_limpo}".strip(), max_resultados=5)


async def buscar_web(termo: str, max_resultados: int = 5) -> str:
    """Busca informações na web usando DuckDuckGo com múltiplos fallbacks."""
    termo = termo.strip()
    
    # Limpa termos conversacionais que atrapalham a busca na web
    termo_busca = termo
    for stop_word in [
        "me fale sobre", "me fale", "como está o", "como esta o", "como está a", "como esta a",
        "como está", "como esta", "tem alguma notícia relevante sobre", "tem alguma notícia sobre",
        "tem alguma noticia sobre", "o que você sabe sobre", "o que voce sabe sobre",
        "pesquise na internet sobre", "pesquise na web sobre", "pesquise sobre", "pesquise",
        "pesquisa sobre", "pesquisa", "busque sobre", "busque", "por favor", "me diga", "me conte"
    ]:
        if termo_busca.lower().startswith(stop_word):
            termo_busca = termo_busca[len(stop_word):].strip()
        else:
            termo_busca = re.sub(re.escape(stop_word), "", termo_busca, flags=re.IGNORECASE).strip()

    if not termo_busca:
        termo_busca = termo

    log.info(f"[MCP/WEB] Executando busca por: '{termo_busca}'")

    # 1. Tenta biblioteca oficial ddgs / duckduckgo_search silenciando warnings
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS

        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(termo_busca, max_results=max_resultados):
                titulo = r.get("title", "")
                link = r.get("href", "")
                snippet = r.get("body", "")
                resultados.append(f"• Título: {titulo}\n  Link: {link}\n  Resumo: {snippet}")
        if resultados:
            return "\n\n".join(resultados)
    except Exception as e:
        log.debug(f"[MCP/WEB] ddgs library indisponível ou falhou: {e}. Usando fallback HTTP.")

    # 2. Fallback HTTP direto via DuckDuckGo HTML
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(termo_busca)}", headers=headers)
            if resp.status_code == 200:
                texto_html = resp.text
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(texto_html, "html.parser")
                resultados = []
                for res in soup.find_all("div", class_="result", limit=max_resultados):
                    tit_tag = res.find("a", class_="result__a")
                    snip_tag = res.find("a", class_="result__snippet")
                    if tit_tag:
                        titulo = tit_tag.get_text(strip=True)
                        link = tit_tag.get("href", "")
                        snippet = snip_tag.get_text(strip=True) if snip_tag else ""
                        resultados.append(f"• Título: {titulo}\n  Link: {link}\n  Resumo: {snippet}")
                if resultados:
                    return "\n\n".join(resultados)
    except Exception as e:
        log.error(f"[MCP/WEB] Falha no fallback DuckDuckGo HTML: {e}")

    # 3. Fallback Wikipedia API em português
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            url_wiki = f"https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(termo_busca)}&utf8=&format=json"
            r = await client.get(url_wiki)
            if r.status_code == 200:
                dados = r.json()
                itens = dados.get("query", {}).get("search", [])[:max_resultados]
                if itens:
                    limpos = []
                    for item in itens:
                        tit = item.get("title", "")
                        snip = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                        limpos.append(f"• {tit}: {snip}")
                    return "\n".join(limpos)
    except Exception as e:
        log.error(f"[MCP/WEB] Falha no fallback Wikipedia: {e}")

    return f"Não foi possível obter dados online atualizados sobre '{termo}' no momento."


async def obter_previsao_tempo(cidade: str) -> str:
    """Consulta informações meteorológicas em tempo real para uma cidade."""
    log.info(f"[MCP/TEMPO] Buscando previsão para: {cidade}")
    cidade_limpa = cidade.strip().replace(" ", "+")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"https://wttr.in/{cidade_limpa}?format=j1")
            if resp.status_code == 200:
                dados = resp.json()
                atual = dados.get("current_condition", [{}])[0]
                temp = atual.get("temp_C", "N/A")
                sensacao = atual.get("FeelsLikeC", "N/A")
                umidade = atual.get("humidity", "N/A")
                vento = atual.get("windspeedKmph", "N/A")
                desc = atual.get("lang_pt", [{}])[0].get("value") if "lang_pt" in atual else atual.get("weatherDesc", [{}])[0].get("value", "Tempo estável")
                return (
                    f"Condições meteorológicas para {cidade}:\n"
                    f"- Condição: {desc}\n"
                    f"- Temperatura atual: {temp}°C (sensação de {sensacao}°C)\n"
                    f"- Umidade: {umidade}%\n"
                    f"- Velocidade do vento: {vento} km/h"
                )
    except Exception as e:
        log.error(f"[MCP/TEMPO] Erro ao obter previsão do tempo: {e}")

    return f"Não foi possível consultar a previsão meteorológica para '{cidade}' no momento."


async def obter_conteudo_url(url: str) -> str:
    """Baixa e extrai o texto principal de uma URL."""
    log.info(f"[MCP/FETCH] Lendo URL: {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for s in soup(["script", "style", "nav", "footer"]):
                    s.decompose()
                texto = soup.get_text(separator=" ", strip=True)
                return texto[:2500] + ("..." if len(texto) > 2500 else "")
    except Exception as e:
        log.error(f"[MCP/FETCH] Erro ao ler URL: {e}")
    return f"Falha ao carregar conteúdo da página {url}."


# Definição dos Schemas de ferramentas nativas no padrão Ollama
FERRAMENTAS_NATIVAS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "buscar_noticias_hoje",
            "description": "Obtém o Briefing Executivo Global de hoje em tempo real, cobrindo cotações financeiras, notícias internacionais/EUA, economia, Brasil e tecnologia. Use sempre que o usuário perguntar por notícias, manchetes, briefing diário ou o que está acontecendo no Brasil e no mundo hoje.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {
                        "type": "string",
                        "description": "Tema específico (ex: 'Petrobras', 'IA') ou deixe vazio para o Briefing Executivo completo de hoje."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_web",
            "description": "Busca informações atualizadas na internet sobre fatos, notícias, cotações, pessoas ou eventos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo ou frase chave para a pesquisa na web."
                    }
                },
                "required": ["termo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_previsao_tempo",
            "description": "Obtém a previsão do tempo atual e condições climáticas de uma cidade ou localidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {
                        "type": "string",
                        "description": "Nome da cidade (ex: São Paulo, Rio de Janeiro, Curitiba, Nova York)."
                    }
                },
                "required": ["cidade"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_conteudo_url",
            "description": "Lê e extrai o conteúdo em texto de um site ou página web a partir de sua URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "A URL completa da página a ser lida."
                    }
                },
                "required": ["url"]
            }
        }
    }
]


# ──────────────────────────────────────────────────────────
#  GERENCIADOR MCP CLIENT
# ──────────────────────────────────────────────────────────

def carregar_config_mcp() -> dict:
    if os.path.exists(MCP_CONFIG_FILE):
        try:
            with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[MCP] Erro ao ler {MCP_CONFIG_FILE}: {e}")
    return {"mcpServers": {}}


async def executar_ferramenta_local(nome: str, argumentos: dict) -> str:
    """Executa as ferramentas nativas de fallback."""
    if nome == "buscar_noticias_hoje":
        tema = argumentos.get("tema") or argumentos.get("query") or argumentos.get("termo") or ""
        return await buscar_noticias_hoje(str(tema))
    elif nome == "buscar_web":
        termo = argumentos.get("termo") or argumentos.get("query") or argumentos.get("q") or ""
        return await buscar_web(str(termo))
    elif nome == "obter_previsao_tempo":
        cidade = argumentos.get("cidade") or argumentos.get("location") or argumentos.get("city") or "São Paulo"
        return await obter_previsao_tempo(str(cidade))
    elif nome == "obter_conteudo_url":
        url = argumentos.get("url") or ""
        return await obter_conteudo_url(str(url))
    else:
        return f"Ferramenta desconhecida: {nome}"


async def coletar_ferramentas_mcp() -> tuple[list[dict], dict[str, Any]]:
    """
    Coleta ferramentas tanto de servidores MCP externos configurados (se houver e estiverem disponíveis)
    quanto das ferramentas nativas integradas.
    """
    ferramentas_ollama = list(FERRAMENTAS_NATIVAS_SCHEMA)
    mapa_executores = {
        "buscar_noticias_hoje": executar_ferramenta_local,
        "buscar_web": executar_ferramenta_local,
        "obter_previsao_tempo": executar_ferramenta_local,
        "obter_conteudo_url": executar_ferramenta_local,
    }

    # Tenta inspecionar servidores externos se o SDK mcp estiver instalado
    try:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession

        config = carregar_config_mcp()
        servidores = config.get("mcpServers", {})

        for srv_name, srv_conf in servidores.items():
            cmd = srv_conf.get("command")
            args = srv_conf.get("args", [])
            env = srv_conf.get("env")
            if not cmd or srv_name == "web-search":
                continue

            try:
                params = StdioServerParameters(command=cmd, args=args, env=env)
                # Tenta conexão rápida com timeout curto para não travar
                async with asyncio.timeout(2.0):
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_resp = await session.list_tools()
                            for t in tools_resp.tools:
                                schema_ollama = {
                                    "type": "function",
                                    "function": {
                                        "name": f"{srv_name}__{t.name}",
                                        "description": t.description or "",
                                        "parameters": t.inputSchema or {}
                                    }
                                }
                                ferramentas_ollama.append(schema_ollama)
            except Exception as e:
                log.debug(f"[MCP] Servidor MCP '{srv_name}' não está ativo no momento ({e}).")
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"[MCP] Inspecção de servidores MCP: {e}")

    return ferramentas_ollama, mapa_executores


async def executar_comandos_mcp_ou_web(pergunta: str) -> str:
    """
    Fluxo orquestrado de execução de ferramentas via MCP / Web:
    1. Envia a pergunta do usuário com a lista de tools para o modelo Ollama.
    2. Captura os tool_calls solicitados pelo modelo.
    3. Executa as ferramentas via MCP ou fallback nativo.
    4. Envia o resultado de volta para o LLM gerar a resposta elegante em português para o Jarvis falar.
    """
    import ollama

    # Escolhe o modelo mais apropriado para function calling e raciocínio
    modelo, _ = brain_selector.escolher_melhor_modelo("CONVERSA")

    tools_schema, mapa_exec = await coletar_ferramentas_mcp()

    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y")

    termos_noticia = [
        "notícia", "noticia", "notícias", "noticias", "acontecendo hoje",
        "mundo hoje", "manchetes", "manchete", "últimas notícias", "ultimas noticias",
        "o que aconteceu hoje", "acontecimentos de hoje", "novidades de hoje",
        "briefing", "resumo do dia", "giro de notícias", "giro do dia", "panorama",
        "mercado financeiro", "cotações", "cotacoes", "como está o mundo", "como esta o mundo"
    ]
    pergunta_lower = pergunta.lower()
    eh_noticia = any(k in pergunta_lower for k in termos_noticia)

    PROMPT_BRIEFING_EXECUTIVO = (
        "Você está apresentando o Briefing Executivo Diário para o senhor. "
        "Faça um panorama abrangente, elegante e fluido cobrindo TODAS as áreas fornecidas nos dados abaixo: "
        "comece pelo cenário Internacional/EUA e Geopolítica, passe pelo Mercado Financeiro (citando as cotações e bolsas), "
        "destaque o cenário no Brasil e finalize com Tecnologia. Cite pelo menos 5 a 6 fatos distintos de forma dinâmica, "
        "direta e sem usar asteriscos ou markdown, como um verdadeiro assistente executivo de alto nível."
    )

    if eh_noticia:
        system_prompt = (
            f"Hoje é dia {data_atual}.\n"
            "Você é o assistente executivo Jarvis apresentando o Briefing Executivo Diário em tempo real para o senhor.\n"
            "PROIBIDO inventar fatos ou notícias antigas de anos anteriores. Baseie-se estritamente nos dados em tempo real fornecidos abaixo.\n"
            f"{PROMPT_BRIEFING_EXECUTIVO}"
        )
    else:
        system_prompt = (
            f"Hoje é dia {data_atual}.\n"
            "Você é o assistente Jarvis com acesso a ferramentas em tempo real via internet e protocolo MCP.\n"
            "PROIBIDO inventar dados ou fatos antigos do seu treinamento.\n"
            "Baseie-se estritamente nas informações em tempo real obtidas pelas ferramentas.\n"
            "Formule uma resposta clara, natural, cortês e direta ao ponto em português para ser falada pela sua voz, sem usar asteriscos ou markdown."
        )

    mensagens = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": pergunta}
    ]

    try:
        loop = asyncio.get_running_loop()
        
        # 1. Primeira chamada com tools ativas
        resp = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo,
                messages=mensagens,
                tools=tools_schema
            )
        )

        msg = resp.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        # 2. Se o modelo não gerou tool_calls automaticamente mas a pergunta é nitidamente uma busca
        if not tool_calls:
            termos_clima = ["tempo em", "temperatura em", "previsão do tempo", "clima"]
            eh_clima = any(k in pergunta_lower for k in termos_clima)

            if eh_noticia:
                tema_noticia = pergunta_lower
                for c in ["quais são as", "quais as", "notícias de", "noticias de", "notícias sobre", "noticias sobre", "notícias", "noticias", "de hoje", "hoje", "acontecendo", "me fale sobre", "principais"]:
                    tema_noticia = tema_noticia.replace(c, "").strip()
                resultado_ferramenta = await buscar_noticias_hoje(tema_noticia)
                mensagens.append({"role": "assistant", "content": "Compilando o Briefing Executivo Diário..."})
                mensagens.append({
                    "role": "user",
                    "content": (
                        f"Com base nestes dados executivos e notícias em tempo real obtidos hoje ({data_atual}):\n\n"
                        f"{resultado_ferramenta}\n\n"
                        f"{PROMPT_BRIEFING_EXECUTIVO}"
                    )
                })
            elif eh_clima:
                cidade = pergunta_lower
                for c in ["qual a", "previsão do tempo em", "tempo em", "clima em", "temperatura em", "como está o", "como esta o", "por favor"]:
                    cidade = cidade.replace(c, "").strip()
                resultado_ferramenta = await obter_previsao_tempo(cidade)
                mensagens.append({"role": "assistant", "content": "Consultando o clima..."})
                mensagens.append({
                    "role": "user",
                    "content": f"Com base nestes dados meteorológicos obtidos em tempo real hoje ({data_atual}):\n\n{resultado_ferramenta}\n\nResponda com naturalidade ao senhor sobre: '{pergunta}'. Não use asteriscos ou formatação markdown."
                })
            else:
                resultado_ferramenta = await buscar_web(pergunta)
                mensagens.append({"role": "assistant", "content": "Consultando a rede mundial de computadores..."})
                mensagens.append({
                    "role": "user",
                    "content": f"Com base nestes dados obtidos na rede hoje ({data_atual}):\n\n{resultado_ferramenta}\n\nResponda com elegância ao senhor sobre sua pergunta inicial: '{pergunta}'. Não invente fatos antigos, use estritamente as informações fornecidas acima sem asteriscos ou markdown."
                })
        else:
            # 3. Executa cada ferramenta requisitada pelo modelo
            mensagens.append(msg)
            for call in tool_calls:
                func = call.get("function", {})
                nome_fn = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}

                if nome_fn == "buscar_noticias_hoje":
                    eh_noticia = True

                log.info(f"[MCP] Modelo solicitou ferramenta: {nome_fn}({args})")
                resultado_exec = await executar_ferramenta_local(nome_fn, args)

                mensagens.append({
                    "role": "tool",
                    "content": str(resultado_exec),
                })

            if eh_noticia:
                mensagens.append({
                    "role": "user",
                    "content": PROMPT_BRIEFING_EXECUTIVO
                })

        # 4. Segunda chamada para sintetizar a resposta final em voz
        resp_final = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo,
                messages=mensagens
            )
        )
        resposta_texto = resp_final.get("message", {}).get("content", "").strip()
        if resposta_texto:
            return resposta_texto

    except Exception as e:
        log.error(f"[MCP] Erro no fluxo MCP: {e}")
        # Fallback de emergência: busca simples direta
        try:
            dados_web = await buscar_web(pergunta)
            return f"Senhor, obtive as seguintes informações da rede:\n{dados_web}"
        except Exception:
            pass

    return "Senhor, encontrei dificuldades ao consultar as ferramentas online no momento."

```


==================================================
 ARQUIVO: .\MODULOS\skills\reminders_module.py
==================================================

```python
"""
reminders_module.py
───────────────────
Gerenciador de Lembretes, Tarefas e Agenda Pessoal do Jarvis.
Persiste os itens em DADOS/lembretes.json e integra com comandos de voz e interface HUD.
"""

import os
import json
import uuid
import re
from datetime import datetime
from MODULOS.system.logger import log

LEMBRETES_FILE = "DADOS/lembretes.json"

def carregar_lembretes() -> list[dict]:
    """Carrega todos os lembretes persistidos."""
    if os.path.exists(LEMBRETES_FILE):
        try:
            with open(LEMBRETES_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    return dados
        except Exception as e:
            log.error(f"[LEMBRETES] Erro ao carregar {LEMBRETES_FILE}: {e}")
    return []

def salvar_lembretes(lista: list[dict]):
    """Persiste a lista de lembretes em DADOS/lembretes.json."""
    os.makedirs(os.path.dirname(LEMBRETES_FILE), exist_ok=True)
    try:
        with open(LEMBRETES_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"[LEMBRETES] Erro ao salvar {LEMBRETES_FILE}: {e}")

def extrair_horario_de_texto(texto: str) -> tuple[str, str]:
    """
    Tenta detectar menções de horário no texto (ex: 'às 14:30', 'às 15h', 'para as 9 horas').
    Retorna (texto_limpo, horario_encontrado).
    """
    horario = ""
    # Padrão: 'às 14:30', 'as 15h', 'às 10 horas', 'as 18'
    match = re.search(r'\b(?:às|as|para\s+as|para\s+às)\s+(\d{1,2}(?::\d{2})?)\s*(?:h|hrs|horas)?\b', texto, re.IGNORECASE)
    if match:
        horario = match.group(1)
        if ":" not in horario:
            horario = f"{int(horario):02d}:00"
        # Remove a menção do horário do texto do lembrete
        texto_limpo = re.sub(re.escape(match.group(0)), '', texto, flags=re.IGNORECASE).strip()
    else:
        texto_limpo = texto.strip()

    return texto_limpo, horario

def adicionar_lembrete(texto: str, horario: str = "") -> dict:
    """Adiciona um novo lembrete à agenda."""
    lembretes = carregar_lembretes()
    
    texto_processado = texto.strip()
    for prefixo in ["me lembre de", "me lembre a", "me lembre", "lembrar de", "lembrete de", "adicionar lembrete de", "adicionar lembrete para", "adicionar lembrete", "criar lembrete de", "criar lembrete"]:
        if texto_processado.lower().startswith(prefixo):
            texto_processado = texto_processado[len(prefixo):].strip()
            break

    texto_limpo, horario_detectado = extrair_horario_de_texto(texto_processado)
    horario_final = horario or horario_detectado

    novo_lembrete = {
        "id": f"rem_{uuid.uuid4().hex[:8]}",
        "texto": texto_limpo or texto,
        "horario": horario_final or "",
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "concluido": False
    }

    lembretes.append(novo_lembrete)
    salvar_lembretes(lembretes)
    log.info(f"[LEMBRETES] Novo lembrete adicionado: {novo_lembrete['texto']} (Horário: {novo_lembrete['horario']})")
    return novo_lembrete

def listar_lembretes_pendentes() -> list[dict]:
    """Retorna apenas os lembretes ainda não concluídos."""
    return [l for l in carregar_lembretes() if not l.get("concluido", False)]

def listar_todos_lembretes() -> list[dict]:
    """Retorna todos os lembretes cadastrados."""
    return carregar_lembretes()

def concluir_lembrete(rem_id: str) -> bool:
    """Marca um lembrete como concluído."""
    lembretes = carregar_lembretes()
    alterado = False
    for l in lembretes:
        if l.get("id") == rem_id or rem_id in l.get("texto", "").lower():
            l["concluido"] = True
            alterado = True
            break
    if alterado:
        salvar_lembretes(lembretes)
        log.info(f"[LEMBRETES] Lembrete {rem_id} concluído.")
        return True
    return False

def alternar_lembrete(rem_id: str) -> bool:
    """Inverte o estado de concluído de um lembrete."""
    lembretes = carregar_lembretes()
    for l in lembretes:
        if l.get("id") == rem_id:
            l["concluido"] = not l.get("concluido", False)
            salvar_lembretes(lembretes)
            return True
    return False

def remover_lembrete(rem_id: str) -> bool:
    """Remove definitivamente um lembrete pelo ID."""
    lembretes = carregar_lembretes()
    novos = [l for l in lembretes if l.get("id") != rem_id]
    if len(novos) != len(lembretes):
        salvar_lembretes(novos)
        log.info(f"[LEMBRETES] Lembrete {rem_id} removido.")
        return True
    return False

def processar_comando_voz(texto: str) -> str:
    """
    Processa solicitações e comandos em linguagem natural referentes à agenda.
    """
    t_lower = texto.lower()

    # 1. Consulta / Listagem de lembretes
    gatilhos_listar = ["quais são meus lembretes", "quais sao meus lembretes", "quais meus lembretes", "meus lembretes", "minha agenda", "listar lembretes", "compromissos de hoje", "o que tenho hoje", "lembretes de hoje"]
    if any(g in t_lower for g in gatilhos_listar):
        pendentes = listar_lembretes_pendentes()
        if not pendentes:
            return "Sua agenda está livre no momento, senhor. Não constam lembretes ou compromissos pendentes registrados."
        
        itens_fala = []
        for idx, item in enumerate(pendentes, 1):
            if item.get("horario"):
                itens_fala.append(f"{item['texto']}, agendado para às {item['horario']}")
            else:
                itens_fala.append(f"{item['texto']}")
        
        total = len(pendentes)
        if total == 1:
            return f"O senhor possui 1 lembrete pendente na agenda: {itens_fala[0]}."
        else:
            return f"O senhor possui {total} lembretes pendentes: " + "; ".join(itens_fala) + "."

    # 2. Conclusão de lembrete
    if "concluir lembrete" in t_lower or "marcar lembrete" in t_lower or "finalizar lembrete" in t_lower:
        alvo = t_lower
        for stop in ["concluir lembrete de", "concluir lembrete", "marcar lembrete de", "marcar lembrete", "finalizar lembrete"]:
            alvo = alvo.replace(stop, "").strip()
        pendentes = listar_lembretes_pendentes()
        for p in pendentes:
            if alvo and alvo in p["texto"].lower():
                concluir_lembrete(p["id"])
                return f"Lembrete '{p['texto']}' marcado como concluído, senhor."
        if pendentes:
            concluir_lembrete(pendentes[0]["id"])
            return f"Primeiro lembrete pendente, '{pendentes[0]['texto']}', marcado como concluído."
        return "Não encontrei nenhum lembrete pendente para concluir, senhor."

    # 3. Adição de lembrete
    novo = adicionar_lembrete(texto)
    if novo.get("horario"):
        return f"Lembrete anotado na sua agenda para às {novo['horario']}: {novo['texto']}."
    return f"Lembrete anotado na sua agenda, senhor: {novo['texto']}."

```


==================================================
 ARQUIVO: .\MODULOS\skills\vision_module.py
==================================================

```python
import os
import pyautogui
import ollama
from PIL import Image
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

MODELO_VISAO = "moondream"
MODELO_TRADUTOR = "llama3.2:3b"

def _garantir_modelo_visao(modelo: str = MODELO_VISAO) -> bool:
    """Verifica se o modelo de visão está baixado no Ollama; se não, faz pull automático."""
    try:
        lista = ollama.list()
        modelos_existentes = []
        if hasattr(lista, 'models'):
            modelos_existentes = [m.model for m in lista.models]
        elif isinstance(lista, dict) and 'models' in lista:
            modelos_existentes = [m.get('name', m.get('model', '')) for m in lista['models']]
        
        if not any(modelo in m for m in modelos_existentes):
            log.info(f"[VISAO] Modelo '{modelo}' não encontrado localmente. Baixando via Ollama...")
            print(f"[VISAO] Baixando modelo de visão '{modelo}' no Ollama... Por favor, aguarde.")
            ollama.pull(modelo)
            log.info(f"[VISAO] Download do modelo '{modelo}' concluído com sucesso.")
        return True
    except Exception as e:
        log.warning(f"[VISAO] Erro ao verificar/baixar modelo no Ollama: {e}")
        return False

def _adaptar_para_jarvis_pt(resposta_visao: str) -> str:
    """
    Traduz e adapta a descrição da tela (muitas vezes em inglês pelo Moondream)
    para o português do Brasil no estilo elegante e conciso do Jarvis.
    """
    if not resposta_visao or not resposta_visao.strip():
        return "Não consegui identificar detalhes claros na sua tela no momento, senhor."

    prompt = (
        f"Traduza e adapte esta descrição da tela do usuário para o português do Brasil "
        f"no estilo elegante do Jarvis (máximo 2 frases): {resposta_visao.strip()}"
    )

    try:
        res = ollama.chat(
            model=MODELO_TRADUTOR,
            messages=[{'role': 'user', 'content': prompt}],
            options={"temperature": 0.3}
        )
        texto = res['message']['content'].strip()
        return texto.strip('\"\'')
    except Exception as e:
        log.warning(f"[VISAO] Falha ao adaptar resposta com {MODELO_TRADUTOR}: {e}")
        return resposta_visao

def _capturar_screenshot():
    """Tenta capturar o screenshot via pyautogui com fallback para Pillow."""
    try:
        return pyautogui.screenshot()
    except Exception as e:
        log.warning(f"[VISAO] Falha ao capturar tela (possível tela bloqueada): {e}")
        return None

def analisar_tela(pergunta_usuario: str) -> str:
    """
    Captura a tela, redimensiona para otimização de VRAM e inferência rápida,
    processa no modelo de visão do Ollama e retorna descrição elegante em português.
    """
    log.info("[VISAO] Capturando tela...")
    print("[VISAO] Jarvis abrindo os olhos... Tirando print da tela.")

    # Bloqueia a gravação do microfone durante a captura e inferência de visão
    voice_manager.STATUS_FALANDO = True

    image_path = "temp_screen.jpg"

    try:
        # 1. Garante que o modelo de visão esteja disponível
        _garantir_modelo_visao(MODELO_VISAO)

        # 2. Captura a tela e otimiza resolução com Pillow (5x mais rápido e leve em VRAM)
        screenshot = _capturar_screenshot()
        if screenshot is None:
            return "Senhor, a tela parece estar bloqueada ou inacessível para captura no momento."

        screenshot.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        if screenshot.mode in ("RGBA", "P"):
            screenshot = screenshot.convert("RGB")

        screenshot.save(image_path, "JPEG", quality=80, optimize=True)

        log.info("[VISAO] Processando imagem no modelo...")

        # 3. Executa a inferência de visão no Ollama
        prompt_visao = (
            f"Responda de forma curta e direta. "
            f"Com base na imagem da tela, descreva ou responda: {pergunta_usuario}"
        )
        res = ollama.chat(
            model=MODELO_VISAO,
            messages=[
                {
                    'role': 'user',
                    'content': prompt_visao,
                    'images': [image_path]
                }
            ]
        )
        resposta_bruta = res['message']['content'].strip()

        # 4. Traduz e adapta para estilo Jarvis
        resposta_final = _adaptar_para_jarvis_pt(resposta_bruta)
        return resposta_final

    except Exception as e:
        log.error(f"[VISAO] Erro ao analisar tela: {e}")
        return f"Senhor, tive uma falha ao processar a visão: {e}"

    finally:
        # Garante a remoção do arquivo temporário
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

```


==================================================
 ARQUIVO: .\MODULOS\system\comunicacao_visual.py
==================================================

```python
import httpx

_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=0.5)
    return _client

async def atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao=None):
    payload = {"cor": cor_hex, "intensidade": intensidade, "texto": texto}
    if padrao:
        payload["padrao"] = padrao
    try:
        client = _get_client()
        await client.post("http://localhost:8000/update", json=payload)
    except Exception:
        pass

async def enviar_evento_interface(dados: dict):
    try:
        client = _get_client()
        await client.post("http://localhost:8000/update", json=dados)
    except Exception:
        pass


```


==================================================
 ARQUIVO: .\MODULOS\system\config.py
==================================================

```python
import os
import json
from MODULOS.system.logger import log

CONFIG_FILE = "DADOS/config_paths.json"

def carregar_configuracao():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception as e:
                log.error(f"Erro ao ler configuração: {e}")
                return None
    return None

```


==================================================
 ARQUIVO: .\MODULOS\system\integrity.py
==================================================

```python
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

```


==================================================
 ARQUIVO: .\MODULOS\system\interface_server.py
==================================================

```python
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

```


==================================================
 ARQUIVO: .\MODULOS\system\logger.py
==================================================

```python
import os
import logging
try:
    import colorlog
except ImportError:
    colorlog = None
from datetime import datetime

# Garante que o diretório DADOS exista
LOG_DIR = "DADOS"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "jarvis.log")

def _setup_logger():
    logger = logging.getLogger("Jarvis")
    # Evita adicionar múltiplos handlers se a função for chamada novamente
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    # 1. Handler para Arquivo (Completo, sem cores)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | [%(module)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # 2. Handler para Console (Com cores se colorlog disponível, senão padrão)
    if colorlog:
        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(levelname)s]%(reset)s %(message)s",
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'white',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Instância global do logger
log = _setup_logger()

# Atalhos para uso fácil:
def debug(msg: str): log.debug(msg)
def info(msg: str): log.info(msg)
def warning(msg: str): log.warning(msg)
def error(msg: str): log.error(msg)
def critical(msg: str): log.critical(msg)
def exception(msg: str): log.exception(msg)

```


==================================================
 ARQUIVO: .\MODULOS\system\services.py
==================================================

```python
import psutil
import subprocess
import time
import ollama
import httpx
from MODULOS.system.logger import log

def liberar_porta_8000():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.net_connections(kind='inet'):
                if conn.laddr.port == 8000:
                    log.info(f"Liberando porta 8000 (Encerrando processo antigo {proc.pid})...")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue

def iniciar_ollama_se_necessario() -> bool:
    try:
        ollama.ps()
        log.info("Ollama já está em execução.")
        return True
    except Exception:
        log.info("Ollama não detectado. Iniciando servidor...")
        try:
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            for i in range(10):
                time.sleep(1)
                try:
                    ollama.ps()
                    log.info(f"Servidor Ollama conectado e pronto.")
                    return True
                except:
                    continue
        except Exception as e:
            log.error(f"Falha ao iniciar Ollama: {e}")
            return False
    return False

async def reportar_progresso(progresso, mensagem, model_id=None, progresso_total=0, lista_modelos=None, ativo=True):
    try:
        payload = {
            "progresso": progresso,
            "mensagem": mensagem,
            "ativo": ativo,
            "progresso_total": progresso_total
        }
        if model_id: payload["model_id"] = model_id
        if lista_modelos: payload["lista_modelos"] = lista_modelos
        
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/system/download_progress", json=payload)
    except Exception as e:
        log.debug(f"Falha ao reportar progresso GUI: {e}")

async def reportar_sharding(progresso, mensagem, ativo=True):
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/system/sharding_progress", json={
                "progresso": progresso,
                "mensagem": mensagem,
                "ativo": ativo
            })
    except Exception as e:
        log.debug(f"Falha ao reportar sharding GUI: {e}")

```


==================================================
 ARQUIVO: .\MODULOS\system\sync.py
==================================================

```python
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

```


==================================================
 ARQUIVO: .\MODULOS\voice\audio_effects.py
==================================================

```python
"""
audio_effects.py
────────────────
Processamento Digital de Sinais (DSP) para voz do assistente JARVIS.
Simula o efeito acústico autêntico de HUD holográfico / capacete de armadura (Mark suit).
"""

import numpy as np
import scipy.signal

def aplicar_efeito_jarvis_dsp(audio: np.ndarray, sr: int = 24000) -> np.ndarray:
    """
    Aplica processamento DSP para conferir a textura vocal característica da IA JARVIS:
    1. Filtro passa-alta suave em 110 Hz (remove sub-graves abafados) + boost de presença (1800-3500 Hz).
    2. Efeito Holográfico / Armadura: Chorus com atrasos curtos de 11ms (ganho 0.22) e 23ms (ganho 0.10).
    3. Saturação suave (np.tanh) e normalização de pico em 0.90 para corpo e presença constantes.
    """
    if audio is None or len(audio) == 0:
        return audio

    formato_original_2d = audio.ndim == 2
    sinal = audio.flatten().astype(np.float32)

    # 1. Filtro Passa-Alta em 110 Hz suave
    try:
        b_hp, a_hp = scipy.signal.butter(2, 110, btype='highpass', fs=sr)
        audio_hp = scipy.signal.lfilter(b_hp, a_hp, sinal)
    except Exception:
        audio_hp = sinal

    # Boost de Presença (1800 Hz a 3500 Hz) para definição da fala
    try:
        b_band, a_band = scipy.signal.butter(2, [1800, 3500], btype='bandpass', fs=sr)
        presenca = scipy.signal.lfilter(b_band, a_band, audio_hp)
        audio_eq = audio_hp + 0.35 * presenca
    except Exception:
        audio_eq = audio_hp

    # 2. Efeito Holográfico / Capacete (duplo short delay)
    d1 = int(0.011 * sr)  # 11 ms
    d2 = int(0.023 * sr)  # 23 ms

    copia_d1 = np.zeros_like(audio_eq)
    if d1 < len(audio_eq):
        copia_d1[d1:] = audio_eq[:-d1] * 0.22

    copia_d2 = np.zeros_like(audio_eq)
    if d2 < len(audio_eq):
        copia_d2[d2:] = audio_eq[:-d2] * 0.10

    audio_holo = audio_eq + copia_d1 + copia_d2

    # 3. Soft Clipping e Normalização de Pico em 0.90
    audio_tanh = np.tanh(audio_holo * 1.15)
    pico = np.max(np.abs(audio_tanh))
    if pico > 0:
        audio_final = (audio_tanh / pico) * 0.90
    else:
        audio_final = audio_tanh

    if formato_original_2d:
        return audio_final.reshape(-1, 1).astype(np.float32)

    return audio_final.astype(np.float32)

```


==================================================
 ARQUIVO: .\MODULOS\voice\kokoro_tts_module.py
==================================================

```python
"""
kokoro_tts_module.py
────────────────────
Motor de síntese de voz (TTS) ultraleve e de alta qualidade baseado no Kokoro TTS (KPipeline).
Opera 100% em CPU sem necessidade de binários externos pesados como SoX.
Configurado para Português do Brasil ('p') com vozes masculinas e femininas (ex: 'pm_alex', 'pf_dora').
"""

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import os
import re
import soundfile as sf
import numpy as np
from MODULOS.system.logger import log

_pipeline = None

def normalizar_pronuncia_pt(texto: str) -> str:
    """
    Normaliza siglas, expressões numéricas, moedas e abreviações
    para pronúncia clara, fluida e natural em Português pelo sintetizador TTS.
    """
    if not texto:
        return ""

    t = texto

    # 1. Expressões numéricas tipo 6x1 -> 6 por 1
    t = re.sub(r'(\d+)\s*[xX]\s*(\d+)', r'\1 por \2', t)

    # 2. Moeda R$ 100 -> 100 reais
    t = re.sub(r'R\$\s*(\d+(?:[.,]\d+)?)', r'\1 reais', t)

    # 3. Porcentagem e temperatura
    t = re.sub(r'(\d+)\s*%', r'\1 por cento', t)
    t = t.replace('%', ' por cento')
    t = re.sub(r'(\d+)\s*°\s*C\b', r'\1 graus Celsius', t)
    t = t.replace('°C', ' graus Celsius')

    # 4. Siglas e abreviações comuns do português
    expansoes = {
        "SP": "São Paulo",
        "RJ": "Rio de Janeiro",
        "RS": "Rio Grande do Sul",
        "MG": "Minas Gerais",
        "DF": "Distrito Federal",
        "EUA": "Estados Unidos",
        "PEC": "Péc",
        "MEI": "Mêi",
        "PIB": "Píbi",
        "PIX": "Píx",
        "IA": "I A",
        "CPU": "C P U",
        "GPU": "G P U",
        "RAM": "Rãm",
        "VRAM": "V Rãm",
        "SSD": "S S D",
        "HD": "H D",
    }

    def substituir_sigla(match):
        palavra = match.group(0)
        if palavra in expansoes:
            return expansoes[palavra]
        # Para outras siglas de 2 a 4 letras todas em maiúsculo (STF, TSE, OEA, ONU, CNPJ, FII)
        return " ".join(list(palavra))

    t = re.sub(r'\b[A-Z]{2,4}\b', substituir_sigla, t)

    return t

def limpar_texto_para_voz(texto: str) -> str:
    """
    Remove marcações de Markdown, URLs e caracteres visuais,
    aplicando normalização fonética para leitura limpa e fluida pelo sintetizador TTS.
    """
    if not texto or not texto.strip():
        return ""

    t = texto

    # 1. Substitui blocos de código
    t = re.sub(r'```[\s\S]*?```', ' código exibido na tela. ', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # 2. Links Markdown [texto](url) -> texto (deve vir ANTES de remover URLs)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)

    # 3. Remove URLs restantes
    t = re.sub(r'https?://\S+', '', t)

    # 4. Remove títulos (#)
    t = re.sub(r'^#{1,6}\s*', '', t, flags=re.MULTILINE)

    # 5. Remove marcadores de lista (*, -, +, 1.)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)

    # 6. Remove caracteres especiais de Markdown, delimitadores e acentos graves
    t = re.sub(r'[*_~>\[\]|\\#`]', ' ', t)

    # 7. Remove bullets unicode
    t = re.sub(r'[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25CF]', ' ', t)

    # 8. Trata parênteses vazios
    t = re.sub(r'\(\s*\)', ' ', t)

    # 9. Aplica normalização fonética de siglas, números e porcentagens
    t = normalizar_pronuncia_pt(t)

    # 10. Trata quebras de linha como pausas naturais
    linhas = [l.strip() for l in t.splitlines() if l.strip()]
    linhas_com_pausa = []
    for l in linhas:
        if not re.search(r'[.!?:]$', l):
            linhas_com_pausa.append(l + '.')
        else:
            linhas_com_pausa.append(l)

    t = ' '.join(linhas_com_pausa)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\s+([.,!?])', r'\1', t)
    t = re.sub(r'\.{2,}', '.', t)

    return t.strip()

def init_kokoro_tts():
    """
    Inicializa o pipeline do Kokoro TTS de forma preguiçosa (Lazy Loading).
    Utiliza lang_code='p' para Português (Brasil).
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        log.info("[KOKORO-TTS] Inicializando modelo Kokoro TTS na CPU (lang_code='p')...")
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', device='cpu')
        log.info("[KOKORO-TTS] Pipeline carregado com sucesso.")
        return _pipeline
    except ImportError:
        log.warning("[KOKORO-TTS] Pacote 'kokoro' não está instalado. Instale com: pip install kokoro soundfile")
        return None
    except Exception as e:
        log.error(f"[KOKORO-TTS] Falha ao inicializar KPipeline: {e}")
        return None


_cached_voices = {}

def obter_voz_kokoro(voz_id):
    """
    Retorna o tensor ou identificador da voz Kokoro.
    Suporta vozes nativas ('pm_alex', 'pf_dora', 'pm_santa') e
    a voz composta 'blend_jarvis' (70% pm_alex + 30% pm_santa).
    """
    global _pipeline, _cached_voices
    if not isinstance(voz_id, str):
        return voz_id
    if _pipeline is None:
        init_kokoro_tts()
    if _pipeline is None:
        return voz_id

    if voz_id in _cached_voices:
        return _cached_voices[voz_id]

    if voz_id == "blend_jarvis":
        try:
            v_santa = _pipeline.load_voice("pm_santa")
            v_alex = _pipeline.load_voice("pm_alex")
            v_george = _pipeline.load_voice("bm_george")
            blend = v_santa * 0.50 + v_alex * 0.30 + v_george * 0.20
            _cached_voices[voz_id] = blend
            return blend
        except Exception as e:
            log.warning(f"[KOKORO-TTS] Falha ao criar blend_jarvis: {e}. Usando pm_alex.")
            return "pm_alex"

    return voz_id

def gerar_audio_kokoro(texto: str, output_path: str, voz: str = "pm_alex", velocidade: float = 1.0, aplicar_dsp: bool = False) -> bool:
    """
    Gera arquivo de áudio WAV a partir de texto utilizando Kokoro TTS.
    
    Args:
        texto: Texto a ser sintetizado em voz.
        output_path: Caminho completo para salvar o arquivo .wav.
        voz: Identificador da voz (padrão 'pm_alex', 'pf_dora', 'pm_santa' ou 'blend_jarvis').
        velocidade: Fator de velocidade da fala (padrão 1.0 para velocidade natural).
        aplicar_dsp: Se True, aplica o processamento de áudio Stark HUD DSP.
        
    Returns:
        bool: True se o áudio foi gerado e salvo com sucesso, False caso contrário.
    """
    global _pipeline
    if not texto or not texto.strip():
        return False

    texto_limpo = limpar_texto_para_voz(texto)
    if not texto_limpo:
        texto_limpo = texto.strip()

    if _pipeline is None:
        init_kokoro_tts()

    if _pipeline is None:
        return False

    try:
        dir_saida = os.path.dirname(os.path.abspath(output_path))
        if dir_saida:
            os.makedirs(dir_saida, exist_ok=True)

        voz_obj = obter_voz_kokoro(voz)
        generator = _pipeline(texto_limpo, voice=voz_obj, speed=velocidade)
        audio_chunks = []

        for gs, ps, audio in generator:
            if audio is not None:
                # Converte tensor PyTorch para NumPy caso necessário
                if hasattr(audio, 'cpu') and hasattr(audio, 'numpy'):
                    audio_arr = audio.cpu().numpy()
                elif hasattr(audio, 'numpy'):
                    audio_arr = audio.numpy()
                else:
                    audio_arr = np.array(audio, dtype=np.float32)

                audio_chunks.append(np.array(audio_arr, dtype=np.float32))

        if not audio_chunks:
            log.warning(f"[KOKORO-TTS] Nenhum chunk de áudio foi retornado para o texto: '{texto[:40]}...'")
            return False

        # Concatena múltiplos trechos em um áudio contínuo
        audio_final = np.concatenate(audio_chunks)
        
        # Corte de silêncio nas pontas (Audio Trimming de 15ms para gapless playback)
        indices = np.where(np.abs(audio_final) > 0.008)[0]
        if len(indices) > 0:
            margem = int(0.015 * 24000)  # 15 ms
            start_idx = max(0, indices[0] - margem)
            end_idx = min(len(audio_final), indices[-1] + margem + 1)
            audio_final = audio_final[start_idx:end_idx]

        # Processamento Stark HUD DSP (automático no blend_jarvis ou se solicitado explicitamente)
        if aplicar_dsp or voz == "blend_jarvis":
            from MODULOS.voice.audio_effects import aplicar_efeito_jarvis_dsp
            audio_final = aplicar_efeito_jarvis_dsp(audio_final, 24000)

        # Salva o arquivo de saída com taxa de amostragem padrão de 24 kHz
        sf.write(output_path, audio_final, 24000)
        return True

    except Exception as e:
        log.error(f"[KOKORO-TTS] Erro durante a geração de áudio: {e}")
        return False

```


==================================================
 ARQUIVO: .\MODULOS\voice\qwen_tts_module.py
==================================================

```python
"""
qwen_tts_module.py
──────────────────
Módulo mantido para compatibilidade retroativa.
Redireciona chamadas legadas para o novo motor ultraleve kokoro_tts_module.py.
"""

from MODULOS.voice.kokoro_tts_module import (
    init_kokoro_tts as init_qwen_tts,
    gerar_audio_kokoro as gerar_audio_qwen,
)

```


==================================================
 ARQUIVO: .\MODULOS\voice\voice_manager.py
==================================================

```python
import asyncio
import edge_tts
try:
    import pygame
except ImportError:
    pygame = None
import os
import uuid
import random
import pyttsx3
from MODULOS.system.comunicacao_visual import atualizar_jarvis
STATUS_FALANDO = False
fila_fala = asyncio.PriorityQueue()

# Defer pygame init to avoid hanging on boot
_pygame_inited = False

def init_pygame_safe():
    global _pygame_inited
    if not _pygame_inited and pygame is not None:
        try:
            pygame.mixer.init()
            _pygame_inited = True
        except Exception as e:
            print(f"[VOZ] Erro ao inicializar mixer (hardware de som): {e}")

async def falar(bot_nome, texto, prioridade=1):
    if not texto: return
    global STATUS_FALANDO
    STATUS_FALANDO = True
    await fila_fala.put((prioridade, bot_nome, texto))

import re
import json
from MODULOS.voice.kokoro_tts_module import limpar_texto_para_voz, gerar_audio_kokoro, init_kokoro_tts

CONFIG_VOZ_PATH = "DADOS/voice_config.json"

VOZES_DISPONIVEIS = [
    {"id": "kokoro_blend", "motor": "kokoro", "voz": "blend_jarvis", "nome": "🎙️ Kokoro: Jarvis Blend (Stark DSP)"},
    {"id": "kokoro_santa", "motor": "kokoro", "voz": "pm_santa", "nome": "🎙️ Kokoro: Santa (Local CPU - Grave)"},
    {"id": "kokoro_alex", "motor": "kokoro", "voz": "pm_alex", "nome": "🎙️ Kokoro: Alex (Local CPU)"},
    {"id": "kokoro_dora", "motor": "kokoro", "voz": "pf_dora", "nome": "🎙️ Kokoro: Dora (Local CPU - Clara)"},
    {"id": "edge_antonio", "motor": "edge", "voz": "pt-BR-AntonioNeural", "nome": "⚡ Neural: Antonio (Zero CPU - Rápido)"},
    {"id": "edge_francisca", "motor": "edge", "voz": "pt-BR-FranciscaNeural", "nome": "⚡ Neural: Francisca (Zero CPU - Rápido)"},
]

def carregar_config_voz() -> dict:
    if os.path.exists(CONFIG_VOZ_PATH):
        try:
            with open(CONFIG_VOZ_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "motor": "edge",
        "voz": "pt-BR-AntonioNeural",
        "nome": "⚡ Neural: Antonio (Zero CPU - Rápido)",
        "efeito_jarvis": True
    }

def salvar_config_voz(motor: str, voz: str, nome: str = "", efeito_jarvis: bool = None) -> dict:
    os.makedirs(os.path.dirname(CONFIG_VOZ_PATH), exist_ok=True)
    cfg_atual = carregar_config_voz()
    if efeito_jarvis is None:
        if voz == "blend_jarvis":
            efeito_jarvis = True
        else:
            efeito_jarvis = cfg_atual.get("efeito_jarvis", False)

    if not nome:
        for opt in VOZES_DISPONIVEIS:
            if opt["motor"] == motor and opt["voz"] == voz:
                nome = opt["nome"]
                break
    cfg = {
        "motor": motor,
        "voz": voz,
        "nome": nome or f"{motor} - {voz}",
        "efeito_jarvis": bool(efeito_jarvis)
    }
    try:
        with open(CONFIG_VOZ_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[VOZ] Erro salvando config de voz: {e}")
    return cfg

KOKORO_VOICE = "pm_alex"
VOICE = "pt-BR-FranciscaNeural"

def dividir_em_sentencas(texto: str) -> list[str]:
    """
    Divide o texto em chunks inteligentes para streaming com latência zero:
    - O 1º chunk tem entre 40 e 100 caracteres para começar a falar em ~1 segundo.
    - Os chunks seguintes são agrupados entre 150 e 260 caracteres para fala coesa e fluida.
    """
    if not texto or not texto.strip():
        return []

    partes = re.split(r'(?<=[.!?:])\s+|\n+', texto.strip())
    chunks = []
    acumulado = ""
    primeiro_chunk = True

    for p in partes:
        p = p.strip()
        if not p:
            continue

        limite_min = 40 if primeiro_chunk else 150
        limite_max = 100 if primeiro_chunk else 260

        if not acumulado:
            acumulado = p
        else:
            acumulado += " " + p

        if len(acumulado) >= limite_min:
            chunks.append(acumulado)
            acumulado = ""
            primeiro_chunk = False

    if acumulado:
        if chunks and len(acumulado) < 35:
            chunks[-1] += " " + acumulado
        else:
            chunks.append(acumulado)

    return chunks or [texto.strip()]

def _gerar_audio_kokoro_sync(texto, arquivo_final, voz=None, aplicar_dsp=False):
    init_kokoro_tts()
    voz_usar = voz or KOKORO_VOICE
    return gerar_audio_kokoro(texto, arquivo_final, voz=voz_usar, velocidade=1.0, aplicar_dsp=aplicar_dsp)

def _gerar_fallback_pyttsx3(texto, arquivo_final):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        if 'brazil' in v.id.lower() or 'pt' in v.id.lower():
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(texto, arquivo_final)
    engine.runAndWait()

async def _sintetizar_chunk_audio(texto_chunk: str, fallback_voice: str = VOICE, motor: str = None, voz: str = None, efeito_jarvis: bool = None) -> str | None:
    """
    Sintetiza um único chunk de texto para arquivo de áudio
    respeitando o motor ativo ('edge' ou 'kokoro'), voz configurada e efeitos DSP.
    """
    if not texto_chunk or not texto_chunk.strip():
        return None

    os.makedirs("TEMP_AUDIO", exist_ok=True)
    arquivo_wav = f"TEMP_AUDIO/fala_{uuid.uuid4().hex}.wav"
    arquivo_mp3 = arquivo_wav.replace('.wav', '.mp3')

    cfg = carregar_config_voz()
    if motor is None:
        motor = cfg.get("motor", "edge")
    if voz is None:
        voz_ativa = cfg.get("voz", "pt-BR-AntonioNeural")
    else:
        voz_ativa = voz
    if efeito_jarvis is None:
        efeito_jarvis = cfg.get("efeito_jarvis", True)

    if motor == "edge":
        # 1. Tenta Edge-TTS primeiro (Zero CPU, instantâneo)
        voz_edge = voz_ativa if "Neural" in voz_ativa else "pt-BR-AntonioNeural"
        try:
            if "Antonio" in voz_edge:
                communicate = edge_tts.Communicate(texto_chunk, voz_edge, rate="+8%", pitch="-5Hz")
            else:
                communicate = edge_tts.Communicate(texto_chunk, voz_edge)
            await communicate.save(arquivo_mp3)

            if os.path.exists(arquivo_mp3):
                # Se o efeito Stark estiver ativo, aplica o DSP no sinal gerado
                if efeito_jarvis:
                    try:
                        import soundfile as sf
                        from MODULOS.voice.audio_effects import aplicar_efeito_jarvis_dsp
                        audio_data, sr = sf.read(arquivo_mp3)
                        audio_dsp = aplicar_efeito_jarvis_dsp(audio_data, sr)
                        sf.write(arquivo_wav, audio_dsp, sr)
                        try:
                            os.remove(arquivo_mp3)
                        except Exception:
                            pass
                        return arquivo_wav
                    except Exception as edsp:
                        print(f"[VOZ] Erro aplicando DSP no Edge-TTS: {edsp}")
                        return arquivo_mp3
                return arquivo_mp3
        except Exception as e:
            print(f"[VOZ] Edge-TTS falhou ({e}). Tentando Kokoro...")

        # 2. Fallback Kokoro
        try:
            sucesso = await asyncio.to_thread(_gerar_audio_kokoro_sync, texto_chunk, arquivo_wav, "blend_jarvis", efeito_jarvis)
            if sucesso and os.path.exists(arquivo_wav):
                return arquivo_wav
        except Exception as ek:
            print(f"[VOZ] Kokoro-TTS falhou no fallback: {ek}")

    else:
        # 1. Tenta Kokoro TTS primeiro (Local CPU com a voz configurada e Stark DSP)
        voz_kokoro = voz_ativa if not "Neural" in voz_ativa else "blend_jarvis"
        try:
            sucesso = await asyncio.to_thread(_gerar_audio_kokoro_sync, texto_chunk, arquivo_wav, voz_kokoro, efeito_jarvis)
            if sucesso and os.path.exists(arquivo_wav):
                return arquivo_wav
        except Exception as ek:
            print(f"[VOZ] Kokoro-TTS falhou no chunk: {ek}")

        # 2. Fallback Edge-TTS
        try:
            communicate = edge_tts.Communicate(texto_chunk, fallback_voice)
            await communicate.save(arquivo_mp3)
            if os.path.exists(arquivo_mp3):
                return arquivo_mp3
        except Exception as e:
            print(f"[VOZ] Edge-TTS falhou no chunk ({e}). Tentando pyttsx3...")

    # 3. Fallback pyttsx3 offline de emergência
    try:
        await asyncio.to_thread(_gerar_fallback_pyttsx3, texto_chunk, arquivo_wav)
        if os.path.exists(arquivo_wav):
            return arquivo_wav
    except Exception as e2:
        print(f"[VOZ] Fallback local falhou: {e2}")

    return None

async def processador_de_fala():
    global STATUS_FALANDO
    print("[SISTEMA] Processador de voz iniciado (Kokoro TTS com Streaming e Queue contínua).")

    while True:
        try:
            prioridade, bot_nome, texto = await fila_fala.get()
            STATUS_FALANDO = True

            # Sinaliza imediatamente a interface visual que estamos sintetizando áudio
            await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.2, texto="Sintetizando voz... 🔊", padrao="tarefa")

            texto_limpo = limpar_texto_para_voz(texto)
            if not texto_limpo:
                texto_limpo = texto

            chunks = dividir_em_sentencas(texto_limpo)
            if not chunks:
                chunks = [texto_limpo]

            init_pygame_safe()

            # Fila de áudios sintetizados pronta para reprodução imediata
            fila_reproducao = asyncio.Queue(maxsize=12)
            arquivos_para_limpar = []

            # Produtor em background: sintetiza continuamente todos os chunks sem travar a reprodução
            async def produtor_audio():
                for idx, chunk_text in enumerate(chunks):
                    try:
                        arq = await _sintetizar_chunk_audio(chunk_text, VOICE)
                        if arq and os.path.exists(arq):
                            arquivos_para_limpar.append(arq)
                            await fila_reproducao.put((idx, chunk_text, arq))
                        else:
                            await fila_reproducao.put((idx, chunk_text, None))
                    except Exception as e_prod:
                        print(f"[VOZ] Erro na síntese do chunk {idx}: {e_prod}")
                        await fila_reproducao.put((idx, chunk_text, None))
                # Sentinela de término
                await fila_reproducao.put(None)

            produtor_task = asyncio.create_task(produtor_audio())
            primeiro_tocado = False

            while True:
                item = await fila_reproducao.get()
                if item is None:
                    # Todos os chunks foram reproduzidos
                    break

                idx, chunk_text, arquivo_audio = item

                if not primeiro_tocado:
                    # Restaura a legenda com o texto formatado original assim que o áudio começa
                    await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=texto, padrao="falando")
                    primeiro_tocado = True

                if arquivo_audio and os.path.exists(arquivo_audio) and pygame is not None:
                    try:
                        pygame.mixer.music.load(arquivo_audio)
                        pygame.mixer.music.play()

                        # Delay ultrabaixo de 20ms para checagem rápida de fim de reprodução (gapless)
                        while pygame.mixer.music.get_busy():
                            agita = random.uniform(0.4, 0.9)
                            await atualizar_jarvis(intensidade=agita, texto=texto)
                            await asyncio.sleep(0.02)
                    except Exception as playback_error:
                        print(f"[VOZ] Erro na reprodução do chunk {idx}: {playback_error}")
                    finally:
                        try:
                            pygame.mixer.music.unload()
                        except Exception:
                            pass
                        if os.path.exists(arquivo_audio):
                            try:
                                os.remove(arquivo_audio)
                            except Exception:
                                pass
                else:
                    await atualizar_jarvis(intensidade=0.1, texto=texto)
                    await asyncio.sleep(len(chunk_text) * 0.04)

            # Aguarda a tarefa produtora concluir
            try:
                await produtor_task
            except Exception:
                pass

            # Limpeza final de arquivos residuais caso algum tenha sobrado
            for arq in arquivos_para_limpar:
                if os.path.exists(arq):
                    try:
                        os.remove(arq)
                    except Exception:
                        pass

            await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao="conversa")

        except Exception as e:
            print(f"[ERRO CRÍTICO VOZ]: {e}")
        finally:
            STATUS_FALANDO = False
            try:
                from MODULOS.ear.recorder import limpar_pre_buffer
                limpar_pre_buffer()
            except Exception:
                pass

```


==================================================
 ARQUIVO: .\TESTES\testar_fala_jarvis.py
==================================================

```python
import os
import sys

# Adiciona a raiz do projeto ao sys.path para permitir a execução direta do script de teste
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from MODULOS.voice.kokoro_tts_module import init_kokoro_tts, gerar_audio_kokoro

def main():
    print("--- INICIANDO TESTE DE VOZ DO JARVIS (KOKORO-TTS) ---")
    
    # 1. Inicializa o modelo Kokoro TTS na CPU
    init_kokoro_tts()
    
    # 2. Lista de frases para teste
    frases = [
        "Olá senhor, sou o Jarvis. Minha voz agora é gerada localmente pelo modelo Kokoro TTS.",
        "Testando a naturalidade da fala em português. O que o senhor achou da minha nova voz?",
        "O sistema está operante e todos os núcleos neurais estão estáveis. Aguardo seus comandos.",
        "A tecnologia avança, e agora posso falar de forma muito mais humana, rápida e natural na CPU."
    ]
    
    # 3. Cria pasta de teste se não existir
    output_dir = "TESTE_FALA"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nOs áudios serão salvos em: {os.path.abspath(output_dir)}")
    
    # 4. Gera os áudios de forma sequencial
    for i, frase in enumerate(frases):
        filename = os.path.join(output_dir, f"teste_{i+1}.wav")
        print(f"\n[Gerando {i+1}/{len(frases)}] -> '{frase[:50]}...'")
        
        sucesso = gerar_audio_kokoro(frase, filename, voz="pm_alex", velocidade=1.1)
        
        if sucesso:
            print(f"[OK] SUCESSO: Áudio gerado em {filename}")
        else:
            print(f"[ERRO] FALHA: Erro ao gerar o áudio {i+1}. Verifique se a biblioteca kokoro está instalada.")

    print("\n" + "="*40)
    print("TESTE FINALIZADO!")
    print(f"Vá até a pasta '{output_dir}' para ouvir as amostras.")
    print("="*40)

if __name__ == "__main__":
    main()

```


==================================================
 ARQUIVO: .\TESTES\testar_microfone.py
==================================================

```python
"""
testar_microfone.py
───────────────────
Script simplificado e direto para teste do microfone no Jarvis.
Gravação em etapa única com medidor de volume em tempo real e transcrição via Whisper Small.
"""

import os
import sys
import time
import numpy as np

# Garante acesso aos módulos do projeto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import sounddevice as sd
from MODULOS.ear import recorder
from MODULOS.ear.recorder import (
    selecionar_microfone,
    calibrar_ruido,
    garantir_stream,
    gravar_fala,
    FS,
)
from MODULOS.ear.models import carregar_whisper_small

def main():
    print("=" * 60)
    print("      DIAGNÓSTICO E TESTE DO MICROFONE - JARVIS")
    print("=" * 60)

    # 1. Seleciona e exibe dispositivo otimizado
    garantir_stream()
    dev_info = sd.query_devices(recorder.DEVICE_ID) if recorder.DEVICE_ID is not None else sd.query_devices(kind='input')
    print(f"\n[1/4] Microfone Ativo (DirectSound Otimizado):")
    print(f"   Índice [{recorder.DEVICE_ID}]: {dev_info['name']}")
    print(f"   Taxa nativa: {dev_info.get('default_samplerate')} Hz | Taxa Jarvis: {FS} Hz\n")

    # 2. Calibração de silêncio
    print("[2/4] Calibrando nível de ruído...")
    print("-> Por favor, FIQUE EM SILÊNCIO por 2 segundos...")
    calibrar_ruido(duracao=2)
    print(f"-> Limiar de detecção definido para: {recorder.THRESHOLD_BARULHO:.5f}\n")

    # 3. Gravação direta com feedback em tempo real
    print("[3/4] Gravando sua fala:")
    print("=" * 60)
    print(">>> PODE FALAR SUA FRASE AGORA! <<<")
    print("Exemplo: 'Jarvis, você é capaz de me ouvir perfeitamente agora?'")
    print("=" * 60)

    def feedback_terminal(gravando, vol, duracao):
        largura = int(min(vol * 2000, 35))
        barra = "█" * largura + "░" * (35 - largura)
        if gravando:
            sys.stdout.write(f"\r[GRAVANDO] [{barra}] Vol: {vol:.4f} | Duração: {duracao:.1f}s   ")
        else:
            sys.stdout.write(f"\r[AGUARDANDO VOZ] [{barra}] Vol: {vol:.4f}   ")
        sys.stdout.flush()

    arquivo_teste = "TEMP_AUDIO/teste_diagnostico.wav"
    gravou = gravar_fala(max_silencio_frames=35, arquivo=arquivo_teste, callback_feedback=feedback_terminal)
    print("\n")

    if not gravou:
        print("[FALHA] Nenhum som acima do limiar foi capturado.")
        print("DICA: Verifique nas configurações de som do Windows se o microfone não está mudo ou com volume baixo.")
        return

    print(f"[OK] Áudio gravado com sucesso em: {arquivo_teste}")

    # 4. Transcrição com Whisper Small (Alta Precisão em Português)
    print("\n[4/4] Transcrevendo com Whisper Small (modelo de alta precisão)...")
    carregar_whisper_small()
    from MODULOS.ear import models
    
    segs, _ = models.whisper_model.transcribe(
        arquivo_teste,
        language="pt",
        vad_filter=False
    )
    texto = " ".join([s.text for s in segs]).strip()
    
    print("\n" + "=" * 50)
    print(f"TRANSCRITO PELO JARVIS: \"{texto}\"")
    print("=" * 50)

    # 5. Reprodução do áudio gravado
    try:
        import soundfile as sf
        audio_data, samplerate = sf.read(arquivo_teste)
        print("\n-> Reproduzindo o áudio completo que o Jarvis capturou...")
        sd.play(audio_data, samplerate)
        sd.wait()
        print("-> Reprodução concluída.")
    except Exception as e:
        print(f"(Não foi possível reproduzir o áudio: {e})")

    print("\nTeste concluído com sucesso!")

if __name__ == "__main__":
    main()

```


==================================================
 ARQUIVO: .\TESTES\teste.py
==================================================

```python
import torch

print(f"Versão do Torch: {torch.__version__}")
print(f"CUDA disponível: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Placa detetada: {torch.cuda.get_device_name(0)}")
else:
    print("A NVIDIA ainda não foi detetada pelo Python.")
```


==================================================
 ARQUIVO: .\TESTES\teste_fiis.py
==================================================

```python
import sys
import os

# Adiciona a raiz do projeto e a pasta MODULOS/skills ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'MODULOS', 'skills')))

try:
    from MODULOS.skills.fii_monitor import obter_resumo_fiis
except ImportError:
    from fii_monitor import obter_resumo_fiis

def testar_monitor_financeiro():
    print("="*60)
    print("TESTE DO MÓDULO FINANCEIRO - JARVIS")
    print("="*60)
    print("Buscando cotações e indicadores (isso pode levar alguns segundos)...")
    
    try:
        # Chama a função principal do monitor
        resultado = obter_resumo_fiis()
        
        print("\nRELATÓRIO GERADO PARA VOZ:")
        print("-" * 30)
        print(resultado)
        print("-" * 30)
        print("\nTeste concluído com sucesso!")
        
    except Exception as e:
        print(f"\n[ERRO] Ocorreu uma falha durante o teste: {e}")

if __name__ == "__main__":
    testar_monitor_financeiro()

```


==================================================
 ARQUIVO: .\TESTES\teste_global.py
==================================================

```python
import asyncio
import os
import sys
import time
import json
import traceback

# --- ADICIONE ESTE BLOCO DE CÓDIGO AQUI ---
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# -------------------------------------------

# Configuração de cores para o terminal
class Cores:
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    RESET = '\033[0m'

RELATORIO_PATH = "DADOS/relatorio_diagnostico.txt"
resultados = []

def log_resultado(modulo, status, mensagem):
    simbolo = "[OK]" if status == "OK" else ("[AVISO]" if status == "AVISO" else "[ERRO]")
    cor = Cores.VERDE if status == "OK" else (Cores.AMARELO if status == "AVISO" else Cores.VERMELHO)
    
    linha_texto = f"{simbolo} [{modulo}] {status}: {mensagem}"
    print(f"{cor}{linha_texto}{Cores.RESET}")
    resultados.append(linha_texto)

async def testar_sistema():
    print(f"\n{Cores.AZUL}--- INICIANDO DIAGNÓSTICO GLOBAL DO JARVIS ---{Cores.RESET}\n")
    
    # 1. MÓDULOS DE SISTEMA
    try:
        from MODULOS.system.logger import log
        log.debug("Teste de log silencioso.")
        log_resultado("SYSTEM.LOGGER", "OK", "Logger carregado e operante.")
    except Exception as e:
        log_resultado("SYSTEM.LOGGER", "ERRO", str(e))

    try:
        from MODULOS.system.config import carregar_configuracao
        cfg = carregar_configuracao()
        if cfg:
            log_resultado("SYSTEM.CONFIG", "OK", f"Configuração lida com sucesso: HD={cfg.get('hd_path')}")
        else:
            log_resultado("SYSTEM.CONFIG", "AVISO", "Arquivo de configuração não encontrado ou vazio.")
    except Exception as e:
        log_resultado("SYSTEM.CONFIG", "ERRO", str(e))

    # 2. AUDIÇÃO (EAR)
    try:
        from MODULOS.ear import models, recorder, states
        log_resultado("EAR.IMPORTS", "OK", "Módulos de áudio importados.")
        
        # Teste de microfone básico
        try:
            import sounddevice as sd
            dispositivos = sd.query_devices()
            if len(dispositivos) > 0:
                log_resultado("EAR.HARDWARE", "OK", f"{len(dispositivos)} dispositivos de entrada de áudio detectados.")
            else:
                log_resultado("EAR.HARDWARE", "AVISO", "Nenhum dispositivo de entrada de áudio encontrado.")
        except:
            log_resultado("EAR.HARDWARE", "ERRO", "Falha ao acessar sounddevice.")
    except Exception as e:
        log_resultado("EAR.EAR_MODULE", "ERRO", f"Falha crítica nos módulos de áudio: {e}")

    # 3. CÉREBRO E INTELIGÊNCIA (BRAIN)
    try:
        from MODULOS.brain.selector import selector as brain_selector
        hw = brain_selector.detectar_hardware()
        log_resultado("BRAIN.SELECTOR", "OK", f"Hardware detectado: VRAM={hw.get('vram_gb')}GB, GPU={hw.get('gpu_modelo')}")
        
        from MODULOS import brain
        log_resultado("BRAIN.INIT", "OK", "Módulo principal do cérebro carregado.")
        
        from MODULOS.brain.core import router
        log_resultado("BRAIN.ROUTER", "OK", "Roteador de intenções carregado.")
    except Exception as e:
        log_resultado("BRAIN.MODULES", "ERRO", f"Erro ao carregar componentes do cérebro: {e}")

    # 4. MEMÓRIA
    try:
        from MODULOS.memory import memory_long, memory_short
        db_ok = memory_long.inicializar_banco()
        log_resultado("MEMORY.LONG", "OK", "Banco de dados de longo prazo conectado.")
        
        memory_short.adicionar_mensagem("system", "teste")
        log_resultado("MEMORY.SHORT", "OK", "Memória de curto prazo (contexto) ativa.")
    except Exception as e:
        log_resultado("MEMORY", "ERRO", f"Falha nos sistemas de memória: {e}")

    # 5. VOZ E VISÃO
    try:
        from MODULOS.voice import voice_manager
        log_resultado("VOICE", "OK", "Gerenciador de voz carregado.")
    except Exception as e:
        log_resultado("VOICE", "ERRO", str(e))

    try:
        from MODULOS.skills import vision_module
        log_resultado("VISION", "OK", "Módulo de visão (análise de tela) disponível.")
    except Exception as e:
        log_resultado("VISION", "AVISO", f"Dependências de visão incompletas: {e}")

    # 6. ESPECIALISTAS E FERRAMENTAS
    try:
        from MODULOS.skills import hardware_module
        stats = await hardware_module.obter_status_hardware()
        if stats:
            log_resultado("HARDWARE_STATS", "OK", "Coleta de telemetria (CPU/GPU) funcionando.")
    except Exception as e:
        log_resultado("HARDWARE_STATS", "ERRO", str(e))

    try:
        from MODULOS.skills import fii_monitor
        log_resultado("FINANCE", "OK", "Monitor de FIIs carregado.")
    except Exception as e:
        log_resultado("FINANCE", "ERRO", str(e))

    try:
        from MODULOS.brain.models import identity_module
        log_resultado("IDENTITY", "OK", "Módulo de identidade da máquina ativo.")
    except Exception as e:
        log_resultado("IDENTITY", "ERRO", str(e))

    try:
        from MODULOS.brain import nlp_processor
        res, txt = nlp_processor.processar_intencao("teste")
        log_resultado("NLP_PROCESSOR", "OK", f"Processador de linguagem legado operacional ({res}).")
    except Exception as e:
        log_resultado("NLP_PROCESSOR", "ERRO", str(e))

    try:
        from MODULOS.brain import airllm_module
        log_resultado("AIRLLM", "OK", "Infraestrutura AirLLM (Modelos Gigantes) carregada.")
    except Exception as e:
        log_resultado("AIRLLM", "ERRO", str(e))

    try:
        from MODULOS.skills import actions_module
        log_resultado("ACTIONS", "OK", "Módulo de ações do sistema (abrir apps) ativo.")
    except Exception as e:
        log_resultado("ACTIONS", "ERRO", str(e))

    try:
        from MODULOS.system import comunicacao_visual
        log_resultado("GUI.VISUAL", "OK", "Sistema de cores e feedback visual operacional.")
    except Exception as e:
        log_resultado("GUI.VISUAL", "ERRO", str(e))

    try:
        from MODULOS.system import interface_server
        log_resultado("GUI.SERVER", "OK", "Servidor de interface carregado.")
    except Exception as e:
        log_resultado("GUI.SERVER", "ERRO", str(e))

    # 7. FINALIZAÇÃO E RELATÓRIO
    os.makedirs(os.path.dirname(RELATORIO_PATH), exist_ok=True)
    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO DE DIAGNÓSTICO GLOBAL DO JARVIS\n")
        f.write("="*40 + "\n")
        f.write(f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        for res in resultados:
            f.write(res + "\n")
    
    print(f"\n{Cores.AZUL}" + "="*40)
    print("DIAGNÓSTICO CONCLUÍDO!")
    print(f"Relatório salvo em: {RELATORIO_PATH}")
    print("="*40 + Cores.RESET)

if __name__ == "__main__":
    asyncio.run(testar_sistema())
```


==================================================
 ARQUIVO: .\TESTES\teste_hardware.py
==================================================

```python
import torch
import torch_directml
from faster_whisper import WhisperModel

def testar_gpu_real():
    print("=== Testando Aceleração Jarvis ===")
    
    # 1. Identifica o hardware
    if torch.cuda.is_available():
        selected_device = "cuda"
        print("[+] Usando NVIDIA CUDA")
    elif torch_directml.is_available():
        # Aqui está o segredo: DirectML
        selected_device = "cpu" 
        print("[!] DirectML detectado. Nota: Para usar GPU AMD no faster-whisper puro")
        print("    o ideal é usar o modo ONNX. Vamos rodar na CPU otimizada por enquanto.")
    else:
        selected_device = "cpu"
        print("[-] Usando CPU Padrão")

    # 2. Carrega com otimização de inteiros (INT8)
    # Isso faz o modelo rodar MUITO rápido mesmo que seja na CPU do seu Ryzen
    try:
        print(f"\nCarregando modelo 'small' em modo {selected_device}...")
        model = WhisperModel("small", device=selected_device, compute_type="int8")
        print("[OK] Modelo carregado!")
    except Exception as e:
        print(f"[ERRO]: {e}")

testar_gpu_real()
```


==================================================
 ARQUIVO: .\TESTES\teste_ias.py
==================================================

```python
import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from MODULOS.brain.selector import selector as brain_selector
from MODULOS import brain
import ollama

# Injetando o mesmo caminho do HD para simular o ambiente real
os.environ["HF_HOME"] = r"D:\ModelosIA"

async def testar_tudo():
    print("="*50)
    print("INICIANDO TESTE DO CEREBRO JARVIS")
    print("="*50)

    # 1. Testando as Seleções de Modelos
    print("\n[TESTE 1] Verificando as especialidades no model_registry.json...")
    
    mod_conversa, tipo_conversa = brain_selector.escolher_melhor_modelo("CONVERSA")
    print(f"-> CONVERSA está usando o modelo: '{mod_conversa}' | Motor: {tipo_conversa.upper()}")
    
    mod_codigo, tipo_codigo = brain_selector.escolher_melhor_modelo("CODIGO")
    print(f"-> CODIGO está usando o modelo: '{mod_codigo}' | Motor: {tipo_codigo.upper()}")
    
    # 2. Testando o Roteador de Intenções
    print("\n[TESTE 2] Verificando para qual IA o Roteador manda os comandos...")
    
    comando_simples = "Olá Jarvis, como você está hoje?"
    decisao_1 = await brain.router.rotear_intencao(comando_simples)
    print(f"Comando: '{comando_simples}'")
    print(f"-> Direcionado para a categoria: {decisao_1.get('categoria')}")
    
    comando_pesado = "Jarvis, crie um código python complexo de rede neural."
    decisao_2 = await brain.router.rotear_intencao(comando_pesado)
    print(f"Comando: '{comando_pesado}'")
    print(f"-> Direcionado para a categoria: {decisao_2.get('categoria')}")

    # 3. Testando o Bate-papo leve no Ollama Localmente
    print("\n[TESTE 3] Testando se o Ollama está vivo e respondendo...")
    try:
        if tipo_conversa == "llm":
            resposta = ollama.chat(model=mod_conversa, messages=[{'role': 'user', 'content': 'Isso é um teste. Responda apenas "Ollama Operacional Mestre!".'}])
            print(f"-> Resposta da IA Inteligente (Ollama): {resposta['message']['content'].strip()}")
    except Exception as e:
        print(f"-> FALHA NO OLLAMA: {e}\nVocê esqueceu de ligar o app Ollama ou não tem o modelo '{mod_conversa}' instalado.")
        
    print("\n[AVISO] Teste de requisição de Código via AirLLM foi IGNORADO neste script para")
    print("não travar o seu computador tentando baixar 150GB caso o download não tenha terminado!")
    print("\nTUDO PRONTO! Se o Ollama respondeu e as rotas estao certas, as duas inteligencias estao de maos dadas.")

if __name__ == "__main__":
    asyncio.run(testar_tudo())

```


==================================================
 ARQUIVO: .\TESTES\teste_visual.py
==================================================

```python
import sys
import os

# Adiciona a pasta raiz do projeto ao PATH do Python
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import asyncio
# Importação absoluta ajustada (sem os ".." no início)
from MODULOS.system.comunicacao_visual import atualizar_jarvis

async def testar():
    print("--- INICIANDO TESTE VISUAL ---")
    
    print("1. Mudando para CIANO (Padrão)...")
    await atualizar_jarvis(cor_hex="#00ffff", texto="TESTE: MODO PADRÃO")
    await asyncio.sleep(2)
    
    print("2. Mudando para AMARELO (Engenheiro)...")
    await atualizar_jarvis(cor_hex="#ffff00", texto="TESTE: MODO ENGENHEIRO")
    await asyncio.sleep(2)
    
    print("3. Mudando para VERMELHO (Alerta Técnico)...")
    await atualizar_jarvis(cor_hex="#ff0000", texto="ALERTA: TESTE DE TEMPERATURA!")
    await asyncio.sleep(2)
    
    print("4. Resetando...")
    await atualizar_jarvis(cor_hex="#00ffff", texto="SISTEMAS ONLINE")
    print("--- TESTE CONCLUÍDO ---")

if __name__ == "__main__":
    asyncio.run(testar())
```


==================================================
 ARQUIVO: .\TESTES\test_imports.py
==================================================

```python
import importlib
import os

root_dir = r"c:\projeto ia\teste 2\Meu-agente-IA-main"
modulos_dir = os.path.join(root_dir, "MODULOS")

failures = 0
for dp, dnx, fnx in os.walk(modulos_dir):
    for f in fnx:
        if f.endswith('.py') and f != '__init__.py':
            rel_path = os.path.relpath(os.path.join(dp, f), root_dir)
            module_name = rel_path.replace('.py', '').replace(os.path.sep, '.')
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as e:
                # ignore third party errors we don't have installed locally in this environment, but flag internal refactor errors
                if 'MODULOS' in str(e):
                    print(f"FAILED IMPORT in {module_name}: {e}")
                    failures += 1

if failures == 0:
    print("ALL IMPORTS RESOLVED CORRECTLY!")

```


==================================================
 ARQUIVO: .\TESTES\tmp_teste_cascata.py
==================================================

```python
from MODULOS.memory import memory_long
memory_long.inicializar_banco()
r = memory_long.buscar_historico_relevante("como esta o sistema de memoria")
print(f"Resultados encontrados: {len(r)}")
if r:
    print(f"Primeiro: [{r[0]['papel']}] {r[0]['mensagem'][:80]}")
else:
    print("(esperado: 0 no historico antigo sem ts_unix, funcionar para novas mensagens)")
    
# Simular uma conversa nova e ver se encontra
memory_long.registrar_conversa_global("user", "este e um teste de busca por cascata mensal")
r2 = memory_long.buscar_historico_relevante("cascata mensal teste")
print(f"\nApos salvar nova mensagem: {len(r2)} resultados")
if r2:
    print(f"Encontrado: {r2[0]['mensagem']}")

```
