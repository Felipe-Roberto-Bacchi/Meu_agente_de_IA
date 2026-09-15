# CONTEXTO COMPLETO DO PROJETO JARVIS



==================================================
 ARQUIVO: .\empacotar.py
==================================================

```python
import os

# Configurações
ARQUIVO_SAIDA = "CONTEXTO_JARVIS.md"
PASTAS_IGNORAR = {'.git', '__pycache__', 'monitor', 'TEMP_AUDIO', 'DADOS'} # Pastas pesadas/binárias
EXTENSOES_PERMITIDAS = {'.py', '.json', '.yaml', '.html', '.css'} # Só o que é código/texto

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

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
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
    
    # Saudação inicial baseada no horário
    hora = time.localtime().tm_hour
    if hora < 12: saudacao = "Bom dia, senhor."
    elif hora < 18: saudacao = "Boa tarde, senhor."
    else: saudacao = "Boa noite, senhor."
    
    await atualizar_jarvis(cor_hex="#00ffff", texto=saudacao, padrao="conversa")
    await voice_manager.falar("Jarvis", saudacao, prioridade=1)
    
    estado_anterior = None
    
    while True:
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

        await atualizar_jarvis(cor_hex="#00ffff", texto="Ouvindo...", padrao="ouvindo")
        texto_bruto = ear.transcrever_audio()
        if not texto_bruto: continue

        log.info(f"[ESCUTADO]: \"{texto_bruto}\"")
        memory_long.registrar_conversa_global("user", texto_bruto)

        if ear.verificar_despedida(texto_bruto):
            ear.set_estado(ear.Estado.DORMINDO)
            despedida = "Até logo, senhor. Estarei aqui quando precisar."
            await atualizar_jarvis(cor_hex="#1a0033", texto=despedida, padrao="dormindo")
            await voice_manager.falar("Jarvis", despedida, prioridade=1)
            memory_long.registrar_conversa_global("assistant", despedida)
            continue

        cor_fala, padrao, resposta = await brain.processar_comando(texto_bruto)
        if resposta:
            await atualizar_jarvis(cor_hex=cor_fala, texto=resposta, padrao=padrao)
            log.info(f"[JARVIS]: {resposta}")
            memory_long.registrar_conversa_global("assistant", resposta)
            await voice_manager.falar("Jarvis", resposta, prioridade=1)

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
            subprocess.Popen(["cmd", "/k", python_exe, "-m", "MODULOS.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
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
        subprocess.Popen(["cmd", "/k", sys.executable, "-m", "MODULOS.interface_server"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(2)
        webbrowser.open("http://localhost:8000")

        # 2. VERIFICAÇÃO DE INTEGRIDADE: Se deletou modelos ou shards, inicia recuperação
        print("\n[MOCK/TESTE] Verificação de integridade e download de modelos PESADOS pulada.")
        # if asyncio.run(verificar_modelos_faltantes(config)):
        #     log.warning("Núcleos neurais ou shards incompletos. Iniciando recuperação...")
        #     asyncio.run(gerenciar_downloads_iniciais(config))
        #     log.info("Integridade restaurada. Reiniciando fluxo principal...")

        brain_selector.calibrar_e_salvar()
        memory_long.inicializar_banco()
        ear.inicializar_whisper()

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
    proc = subprocess.Popen([sys.executable, "-m", "MODULOS.interface_server"], 
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
 ARQUIVO: .\test_imports.py
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
 ARQUIVO: .\INTERFACE\index.html
==================================================

```text
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>JARVIS CORE V5</title>
    <link rel="stylesheet" href="/INTERFACE/style.css">
</head>
<body>

<!-- 🛠️ SWITCHER DE DEBUG (ORIGINAL + GRÁFICOS) -->
<div id="debug-switcher">
    <button class="debug-btn" onclick="debugSetState('home')">Home</button>
    <button class="debug-btn" onclick="debugSetState('setup')">Setup</button>
    <button class="debug-btn" onclick="debugSetState('download')">Download</button>
    <button class="debug-btn" onclick="debugSetState('sharding')">Sharding</button>
    <button class="debug-btn" onclick="showGraphs(true)" style="border-color:#ff00ff; color:#ff00ff;">Gráficos</button>
</div>

<!-- DASHBOARD DE HARDWARE (HUD) -->
<div id="page-graphs">
    <div style="width:100%; display:flex; justify-content:flex-end; max-width:1200px;">
        <button class="debug-btn" onclick="showGraphs(false)">FECHAR HUD [X]</button>
    </div>
    <h2 style="color:#00ffff; letter-spacing:15px; margin-bottom:40px; font-weight:300; text-shadow:0 0 10px #00ffff; text-align:center;">SISTEMA NEURAL</h2>
    <div class="grid-container">
        <div class="card">
            <div class="card-title">PROCESSADOR (CPU)</div>
            <div class="metric-value"><span id="metric-cpu">0</span><span class="metric-unit">%</span></div>
            <div id="chart-cpu" class="chart-container"></div>
            <div style="font-size:10px; color:#444;" id="cpu-temp">TEMP: --°C</div>
        </div>
        <div class="card">
            <div class="card-title">ACELERAÇÃO NEURAL (GPU)</div>
            <div class="metric-value"><span id="metric-gpu">0</span><span class="metric-unit">%</span></div>
            <div id="chart-gpu" class="chart-container"></div>
            <div style="font-size:10px; color:#444;" id="gpu-stats">TEMP: --°C | VRAM: -- | PWR: --</div>
        </div>
        <div class="card">
            <div class="card-title">MEMÓRIA RAM</div>
            <div class="metric-value"><span id="metric-ram">0</span><span class="metric-unit">%</span></div>
            <div id="chart-ram" class="chart-container"></div>
        </div>
        <div class="card">
            <div class="card-title">AIRLLM (ESTIMATIVA)</div>
            <div class="metric-value">READY</div>
            <div style="font-size:10px; color:#444;">I/O: 350MB/s (SSD/HD)</div>
        </div>
    </div>
</div>

<div id="canvas-container"></div>
<div id="ui-layer">
    <div class="label" id="status-label">Neural Core V5 Active</div>
    <div id="subtitles">INICIALIZANDO SISTEMAS...</div>
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
   JARVIS CORE V5 - STYLE SYSTEM
   ═══════════════════════════════════════════════════════ */

* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #000; overflow: hidden; font-family: 'Segoe UI', sans-serif; height: 100vh; width: 100vw; }

#canvas-container { position: absolute; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; z-index: 1; }
#ui-layer { position: absolute; bottom: 8%; width: 100%; text-align: center; pointer-events: none; z-index: 10; }
.label { text-transform: uppercase; letter-spacing: 5px; font-size: 14px; opacity: 0.5; transition: color 1.2s ease, text-shadow 1.2s ease; }
#subtitles { font-size: 26px; margin-top: 10px; font-weight: 300; font-style: italic; transition: color 1.2s ease, text-shadow 1.2s ease; }

/* 🛠️ ESTILOS DE DEBUG */
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

/* Sharding Effects */
#sharding-visual {
    height: 150px; width: 100%; display: flex; flex-direction: column-reverse; align-items: center; gap: 4px; overflow: hidden; margin-bottom: 20px;
}

/* ═══════════════════════════════════════════════════════
   PÁGINA DE GRÁFICOS (DASHBOARD HUD)
   ═══════════════════════════════════════════════════════ */
#page-graphs {
    position: fixed; inset: 0; z-index: 9998;
    display: none; padding-top: 60px;
    flex-direction: column; align-items: center; padding: 80px 20px 20px;
    overflow-y: auto; background: rgba(0,0,0,0.8);
    backdrop-filter: blur(5px);
}
.grid-container {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px; width: 100%; max-width: 1200px;
}
.card {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(0,255,255,0.1);
    border-radius: 12px; padding: 25px; display: flex; flex-direction: column; gap: 10px;
}
.card-title { color: #00ffff; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; opacity: 0.8; }
.chart-container { height: 60px; position: relative; display: flex; align-items: flex-end; gap: 3px; background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; overflow: hidden; }
.chart-bar { flex: 1; background: #00ffff; min-height: 2px; transition: 0.3s; opacity: 0.6; }
.metric-value { font-size: 24px; font-weight: 200; color: #fff; }
.metric-unit { font-size: 12px; color: #555; margin-left: 5px; }

/* NAV Header (Abas) */
#nav-header {
    position: fixed; top: 0; left: 0; width: 100%; height: 50px;
    display: flex; justify-content: flex-start; align-items: center;
    padding: 0 20px; z-index: 10001; 
    background: rgba(0,0,0,0.5); border-bottom: 1px solid rgba(0,255,255,0.1);
}
.nav-tab {
    background: none; border: none; color: #555; font-size: 11px;
    letter-spacing: 2px; padding: 15px 24px; cursor: pointer;
    transition: 0.3s; text-transform: uppercase;
}
.nav-tab.active { color: #00ffff; border-bottom: 2px solid #00ffff; }
.nav-tab:hover { color: #fff; }

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
    
    # Sempre buscamos o modelo original no HD (D:) para economizar SSD
    os.environ["HF_HOME"] = r"D:\ModelosIA"
    
    if "72B" in model_id:
        print(f"[AIRLLM] Modo 72B: Tudo no HD (D:\\ModelosIA) devido ao tamanho extremo.")
        shards_path = None # Fica tudo no D:
    else:
        # Para o modelo de Código (32B), queremos velocidade SSD nas fatias!
        print(f"[AIRLLM] Modo Performance: Lendo original do HD (D:) e usando fatias no SSD (C:)")
        # Pasta de shards no SSD (C:) do usuário
        shards_path = r"C:\Users\felip\.cache\huggingface\jarvis_shards_32b"
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


async def gerar_resposta_airllm(model_id: str, prompt: str, system_prompt: str = "") -> str:
    """
    Função exposta para ser chamada pelo brain_module.py
    Ao rodar, ele acorda o AirLLM (se ainda não estive acordado).
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
from rapidfuzz import utils

# Dicionário focado em corrigir o que o Whisper ouve errado
DICIONARIO_CORRECAO = {
    "aprei": "abrir", "abri": "abrir", "abre": "abrir", "apear": "abrir",
    "painel amd": "radeonsofiwre", "adrenalina": "radeonsofiwre",
    "fúzeo": "fusion", "ópera": "opera", "fogo no fox": "firefox",
    "cepeu": "cpu", "gepeu": "gpu", "code": "qual", "quanto": "qual",
    "rano": "ram", "pirâmide": "hardware"
}

def processar_intencao(comando_voz):
    # 1. Normalização e Correção Fonética
    palavras = comando_voz.lower().split()
    for i, p in enumerate(palavras):
        if p in DICIONARIO_CORRECAO: 
            palavras[i] = DICIONARIO_CORRECAO[p]
    
    texto = " ".join(palavras)

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
        alvo = utils.default_process(texto)
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
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.memory import memory_short
from MODULOS.memory import memory_long
from MODULOS.brain import airllm_module
from MODULOS.system.logger import log

async def gerar_resposta_conversa(texto: str, especialidade: str = "CONVERSA") -> str:
    print(f"\n[MOCK/TESTE] Modelo de inteligência para '{especialidade}' DESATIVADO temporariamente.")
    return f"Recebi seu comando: '{texto}'. O cérebro foi desativado temporariamente para testes do sistema de voz."

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
            loop = asyncio.get_running_loop()
            resultado = await loop.run_in_executor(
                None,
                lambda: asyncio.run(airllm_module.gerar_resposta_airllm(modelo, prompt, ""))
            )
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
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.system.logger import log

def carregar_descricoes_especialistas():
    try:
        with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)
            especialistas = dados.get("especialistas", {})
            return "\n".join([f"- {k}: {v['descricao']}" for k, v in especialistas.items()])
    except Exception as e:
        log.error(f"[REGISTRY]: {e}")
        return "HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA"

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

def _rota_por_keywords(texto: str) -> dict:
    t = texto.lower()

    gatilhos_app = ["abrir", "abre", "iniciar", "executar", "lançar", "start", "abra"]
    gatilhos_hw  = ["temperatura", "cpu", "gpu", "ram", "vram", "verra", "vera", "hardware", "processador", "status", "placa de vídeo", "placa de video", "memória de vídeo", "usando a vram", "usando vram", "processamento", "uso do"]
    gatilhos_cod = ["código", "script", "função", "bug", "erro no código", "programa em python"]
    gatilhos_fii = ["fii", "investimento", "bolsa", "ação", "cotacao", "cotação", "fundo", "oportunidade de compra", "ganhar dinheiro", "mxrf11", "xpml11", "vghf11", "btlg11"]

    gatilhos_salvar = ["guarda", "salva", "anota", "grava", "recorda",
                       "não esqueça", "memoriza", "sabe que"]
    gatilhos_buscar_mem = ["qual é meu", "qual meu", "qual a minha", "qual o meu",
                           "você sabe meu", "lembra meu", "lembra qual", "me diz meu",
                           "quem sou", "como me chamo"]
    gatilhos_esquecer_mem = ["esquece", "apaga", "deleta"]

    for g in gatilhos_app:
        if g in t:
            alvo = t
            for term in gatilhos_app + ["o ", "a ", "por favor", "meu", "minha"]:
                alvo = alvo.replace(term, "")
            return {"categoria": "ABRIR_APP", "alvo": alvo.strip()}

    if any(g in t for g in gatilhos_hw):
        foco = None
        if "cpu" in t or "processador" in t:          foco = "CPU"
        elif "gpu" in t or "placa" in t:              foco = "GPU"
        elif "vram" in t or "memória de vídeo" in t or "memoria de video" in t: foco = "VRAM"
        elif "ram" in t or "memória" in t:            foco = "RAM"
        return {"categoria": "HARDWARE", "alvo": foco}

    if any(g in t for g in gatilhos_salvar + gatilhos_buscar_mem + gatilhos_esquecer_mem):
        return {"categoria": "MEMORIA", "alvo": texto}

    if any(g in t for g in gatilhos_cod):
        return {"categoria": "CODIGO", "alvo": texto}

    if any(g in t for g in gatilhos_fii):
        return {"categoria": "FINANCE", "alvo": texto}

    return {"categoria": "CONVERSA", "alvo": None}

async def rotear_intencao(comando: str) -> dict:
    print("\n[MOCK/TESTE] Roteador LLM desativado para evitar downloads. Usando roteamento básico por palavras-chave.")
    return _rota_por_keywords(comando)

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
import pynvml
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
        path = os.path.join("teste", "jarvis_identity.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _detectar_vram_psutil() -> float:
    try:
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

def escolher_melhor_modelo(especialidade: str) -> tuple[str, str]:
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            registry = json.load(f)
        esp = registry.get("especialistas", {}).get(especialidade, {})
        tipo = esp.get("tipo", "llm")
        if tipo == "airllm":
            return esp.get("repo_id", "Qwen/Qwen2.5-72B-Instruct"), "airllm"
        else:
            return esp.get("modelo_ollama", "llama3.2:3b"), "llm"
    except Exception:
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
import time
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

FS               = 16000
THRESHOLD_BARULHO = 0.05
DEVICE_ID        = None

def selecionar_microfone():
    global DEVICE_ID
    DEVICE_ID = None
    try:
        info = sd.query_devices(kind='input')
        log.info(f"Microfone: [{info['index']}] {info['name']}")
    except Exception as e:
        log.warning(f"Usando dispositivo padrão do sistema ({e})")

def calibrar_ruido(duracao=3):
    global THRESHOLD_BARULHO
    selecionar_microfone()
    log.info("Calibrando microfone... Fique em silêncio.")
    try:
        gravacao = sd.rec(int(duracao * FS), samplerate=FS, channels=1, device=DEVICE_ID)
        sd.wait()
        rms = np.sqrt(np.mean(gravacao**2))
        THRESHOLD_BARULHO = max(0.035, rms * 2.8)
        if rms < 0.001:
            log.warning("\nO volume do microfone está EXTREMAMENTE baixo ou mudo.")
            log.warning("Verifique se o dispositivo de entrada padrão do Windows é o correto.\n")
        log.info(f"Filtro definido em: {THRESHOLD_BARULHO:.5f}")
    except Exception as e:
        log.error(f"Erro na calibragem: {e}")
        THRESHOLD_BARULHO = 0.04

def gravar_fala(max_silencio_frames=22, arquivo="TEMP_AUDIO/input.wav") -> bool:
    chunk_size       = 1024
    pre_buffer       = deque(maxlen=int(FS / chunk_size * 1.5))
    audio_buffer     = []
    falando          = False
    silencio_frames  = 0
    
    max_chunks_sem_fala = int(3.0 * FS / chunk_size)
    chunks_sem_fala = 0

    try:
        with sd.InputStream(samplerate=FS, channels=1, blocksize=chunk_size, device=DEVICE_ID) as stream:
            while True:
                if voice_manager.STATUS_FALANDO:
                    return False

                data, _ = stream.read(chunk_size)
                volume   = np.linalg.norm(data) / np.sqrt(len(data))

                if volume > THRESHOLD_BARULHO:
                    if not falando:
                        log.debug(f"Som detectado! Vol: {volume:.4f}")
                        falando = True
                        audio_buffer.extend(list(pre_buffer))
                    audio_buffer.append(data.copy())
                    silencio_frames = 0
                elif falando:
                    audio_buffer.append(data.copy())
                    silencio_frames += 1
                    if silencio_frames > max_silencio_frames:
                        break
                else:
                    pre_buffer.append(data.copy())
                    chunks_sem_fala += 1
                    if chunks_sem_fala > max_chunks_sem_fala:
                        return False

        if audio_buffer:
            audio_final = np.concatenate(audio_buffer, axis=0)
            write(arquivo, FS, audio_final.astype(np.float32))
            return True
    except sd.PortAudioError as e:
        log.error(f"Erro de áudio (PortAudio): {e}")
        time.sleep(1)
    except Exception as e:
        log.error(f"Erro inesperado na gravação: {e}")
        time.sleep(1)
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
from MODULOS.ear.models import whisper_model, carregar_whisper_small, _whisper_backend
from MODULOS.system.logger import log

def transcrever_audio() -> str:
    try:
        if whisper_model is None:
            carregar_whisper_small()

        if _whisper_backend == "openai_whisper_dml":
            import whisper as openai_whisper
            result = openai_whisper.transcribe(
                whisper_model,
                "TEMP_AUDIO/input.wav",
                language="pt",
                initial_prompt="Jarvis, comando de voz.",
                fp16=False,
                beam_size=5,
                condition_on_previous_text=False,
            )
            return (result.get("text") or "").strip()

        segments, _ = whisper_model.transcribe(
            "TEMP_AUDIO/input.wav",
            language="pt",
            initial_prompt="Jarvis, comando de voz.",
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False
        )
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        log.error(f"Erro na transcrição completa: {e}")
        return ""

```


==================================================
 ARQUIVO: .\MODULOS\ear\wake_word.py
==================================================

```python
from rapidfuzz import fuzz
from MODULOS.voice import voice_manager
from MODULOS.system.logger import log
from MODULOS.ear.recorder import gravar_fala
from MODULOS.ear.models import whisper_tiny

WAKE_WORDS = ["jarvis", "jarbas", "javes", "travis", "garvis", "service", "yaves", "lajardis", "jardis", "jarves"]

def _contem_wake_word(texto: str) -> bool:
    palavras = texto.lower().split()
    for palavra in palavras:
        for wake in WAKE_WORDS:
            if fuzz.ratio(palavra, wake) >= 70:
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
        log.debug(f"Erro transcrição tiny: {e}")
        return ""

def escutar_wake_word() -> bool:
    if voice_manager.STATUS_FALANDO:
        return False

    if gravar_fala(max_silencio_frames=15, arquivo="TEMP_AUDIO/wake.wav"):
        texto = _transcrever_tiny("TEMP_AUDIO/wake.wav")
        log.debug(f"WAKE - Ouvi: '{texto}'")
        if _contem_wake_word(texto):
            log.info(f"WAKE WORD Detectada! (Ouvi: '{texto}')")
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

# Configurando as funções de callback no states
from MODULOS.ear import states
states._set_estado = lambda novo: states._set_estado_base(novo, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

# Wrapper para set_estado exportado para manter compatibilidade com código antigo
def set_estado(novo_estado: str):
    states.set_estado(novo_estado, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

def inicializar_whisper():
    inicializar_whisper_tiny()

def capturar_comando_dinamico() -> tuple[bool, str]:
    estado_atual = get_estado()

    if estado_atual == Estado.DORMINDO:
        if escutar_wake_word():
            set_estado(Estado.ATIVO)
            resetar_timeout()
            return False, Estado.ATIVO
        return False, Estado.DORMINDO

    # MODO ATIVO
    from MODULOS.ear.recorder import TIMEOUT_ATIVO
    if verificar_timeout(60): # timeout default de 60s
        log.info("EAR Timeout de inatividade. Voltando a dormir.")
        set_estado(Estado.DORMINDO)
        return False, Estado.DORMINDO

    if voice_manager.STATUS_FALANDO:
        return False, estado_atual

    if gravar_fala(max_silencio_frames=35, arquivo="TEMP_AUDIO/input.wav"):
        resetar_timeout()
        return True, estado_atual

    return False, estado_atual

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

import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import uuid

# ─────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────

# Embedding local via sentence-transformers (roda na CPU, sem internet)
_EMB = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_client_fatos     = None
_client_historico = None
_col_fatos        = None
_col_historico    = None


def inicializar_banco():
    """Cria/abre os dois bancos ChromaDB. Chame uma vez no boot."""
    global _client_fatos, _client_historico, _col_fatos, _col_historico

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
    if _col_fatos.count() == 0:
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
    doc_id = f"fato_{chave.strip().lower().replace(' ', '_')}"
    try:
        _col_fatos.delete(ids=[doc_id])
        return f"Memória sobre '{chave}' apagada, senhor."
    except Exception as e:
        return f"Não encontrei nada sobre '{chave}' para apagar."


def listar_fatos(n=20) -> list[dict]:
    """Retorna os N fatos mais recentes (para debug ou interface)."""
    _garantir_init()
    if _col_fatos.count() == 0:
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
    if _col_historico.count() == 0:
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
```


==================================================
 ARQUIVO: .\MODULOS\skills\fii_monitor.py
==================================================

```python
import time
import re
import requests
import yfinance as yf
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
    resultado = {"gpu_temp": "N/A", "vram_used_gb": "N/A", "gpu_power": "N/A"}
    dados = await _buscar_lhm()
    palavras_gpu = ['GPU', 'Radeon', 'GeForce', 'RX ', 'RTX', 'GTX']
    try:
        for hardware in dados['Children'][0]['Children']:
            if any(p in hardware['Text'] for p in palavras_gpu):
                for sensor_group in hardware['Children']:
                    if sensor_group['Text'] == 'Temperatures':
                        for s in sensor_group['Children']:
                            if 'GPU' in s['Text'] or 'Core' in s['Text']:
                                resultado['gpu_temp'] = float(s['Value'].replace(',', '.').replace(' °C', ''))
                    elif sensor_group['Text'] == 'Load':
                        pass
                    elif sensor_group['Text'] == 'Data':
                        for s in sensor_group['Children']:
                            if 'Memory Used' in s['Text']:
                                val = s['Value'].replace(',', '.').replace(' MB', '').replace(' GB', '')
                                try:
                                    resultado['vram_used_gb'] = round(float(val) / 1024, 2) if 'MB' in s['Value'] else round(float(val), 2)
                                except Exception:
                                    pass
                    elif sensor_group['Text'] == 'Powers':
                        for s in sensor_group['Children']:
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
            status = await obter_status_hardware()
            if status and "N/A" not in status:
                temps = [float(t) for t in re.findall(r"(\d+\.\d+)", status)]
                if any(t > 85.0 for t in temps):
                    msg_alerta = f"ALERTA TÉRMICO: {max(temps)}°C!"
                    await atualizar_jarvis(cor_hex="#ff0000", texto=msg_alerta, padrao="alerta")
                    await voice_manager.falar("Sentinela", msg_alerta, prioridade=0)
                    await asyncio.sleep(8)
                    await atualizar_jarvis(cor_hex="#1a0033", texto="Aguardando...", padrao="dormindo")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SENTINELA] Erro: {e}")
        await asyncio.sleep(20)

```


==================================================
 ARQUIVO: .\MODULOS\skills\vision_module.py
==================================================

```python
import pyautogui
import ollama
import os

def analisar_tela(pergunta_usuario):
    print("📸 Jarvis abrindo os olhos... Tirando print da tela.")
    
    # Caminho do print
    image_path = "temp_screen.png"
    
    # Tira o print e salva
    screenshot = pyautogui.screenshot()
    screenshot.save(image_path)
    
    # Envia para o modelo de visão Moondream
    # O contexto da pergunta ajuda o Moondream a focar no que você quer
    try:
        res = ollama.chat(model="moondream", messages=[
            {
                'role': 'user', 
                'content': f"Com base na imagem da minha tela, responda: {pergunta_usuario}", 
                'images': [image_path]
            }
        ])
        
        return res['message']['content']
    except Exception as e:
        return f"Senhor, tive uma falha ao processar a visão: {e}"
    finally:
        # Garante que o print seja deletado mesmo se a análise falhar
        if os.path.exists(image_path):
            os.remove(image_path)

```


==================================================
 ARQUIVO: .\MODULOS\system\comunicacao_visual.py
==================================================

```python
import httpx

async def atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao=None):
    payload = {"cor": cor_hex, "intensidade": intensidade, "texto": texto}
    if padrao:
        payload["padrao"] = padrao
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/update", json=payload, timeout=0.5)
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
        from . import hardware_module
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
        with open("index.html", "r", encoding="utf-8") as f:
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

```


==================================================
 ARQUIVO: .\MODULOS\system\logger.py
==================================================

```python
import os
import logging
import colorlog
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

    # 2. Handler para Console (Apenas INFO para cima, com cores)
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

async def gerenciar_downloads_iniciais(config):
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
            else: nomes_ollama.add(m)
    
    todos_ids = list(nomes_ollama) + [x['id'] for x in nomes_airllm]
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

    for model in nomes_airllm:
        etapa_atual += 1
        prog_total = int((etapa_atual / total_etapas) * 100)
        repo_id = model['id']
        
        target_dir = os.path.join(config['hd_path'], repo_id.split('/')[-1])
        path_cache = os.path.join(config['hd_path'], "hub", f"models--{repo_id.replace('/', '--')}")
        
        modelo_base_existe = os.path.exists(path_cache) or (os.path.exists(target_dir) and len(os.listdir(target_dir)) > 5)
        
        if not modelo_base_existe:
            await reportar_progresso(20, f"Baixando {repo_id}...", model_id=repo_id, progresso_total=prog_total)
            try:
                os.makedirs(target_dir, exist_ok=True)
                snapshot_download(repo_id=repo_id, local_dir=target_dir, local_dir_use_symlinks=False)
            except Exception as e:
                log.error(f"DOWNLOAD ERROR {repo_id}: {e}")
                await reportar_progresso(0, f"Erro no download: {model['nome']}", model_id=repo_id, progresso_total=prog_total)
                continue 

        shards_path = r"C:\Users\felip\.cache\huggingface\jarvis_shards_32b"
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

```


==================================================
 ARQUIVO: .\MODULOS\voice\qwen_tts_module.py
==================================================

```python
import os
import time
import warnings
import torch
import soundfile as sf
from MODULOS.system.logger import log

# Suprime o aviso de SoX — não é usado neste módulo (usamos soundfile diretamente)
warnings.filterwarnings("ignore", message=".*SoX.*")
warnings.filterwarnings("ignore", message=".*sox.*")

_model = None

def init_qwen_tts(max_tentativas: int = 3, espera_base: int = 10):
    """
    Inicializa o modelo Qwen3-TTS com retry automático em caso de erro 429
    (Too Many Requests) do HuggingFace.
    
    Args:
        max_tentativas: Número máximo de tentativas de download.
        espera_base: Segundos base de espera (dobra a cada tentativa).
    """
    global _model
    if _model is not None:
        return  # Já carregado, ignora

    for tentativa in range(1, max_tentativas + 1):
        try:
            log.info(f"[QWEN-TTS] Inicializando modelo Qwen3-TTS (CPU). Tentativa {tentativa}/{max_tentativas}...")
            from qwen_tts import Qwen3TTSModel
            
            model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
            _model = Qwen3TTSModel.from_pretrained(model_id, device_map="cpu")
            log.info(f"[QWEN-TTS] Modelo {model_id} carregado com sucesso na CPU!")
            return  # Sucesso, sai do loop

        except Exception as e:
            erro_str = str(e)
            # Trata rate limit do HuggingFace (erro 429)
            if "429" in erro_str or "Too Many Requests" in erro_str:
                espera = espera_base * (2 ** (tentativa - 1))  # 10s, 20s, 40s...
                log.warning(
                    f"[QWEN-TTS] HuggingFace com limite de requisições (429). "
                    f"Aguardando {espera}s antes de tentar novamente... ({tentativa}/{max_tentativas})"
                )
                print(f"[QWEN-TTS] Rate limit do HuggingFace. Tentando novamente em {espera}s...")
                if tentativa < max_tentativas:
                    time.sleep(espera)
                else:
                    log.error("[QWEN-TTS] Todas as tentativas falharam (429). TTS desativado.")
                    print("[QWEN-TTS] Todas as tentativas falharam. O sistema rodará sem voz Qwen.")
                    _model = None
            else:
                # Outro tipo de erro — falha imediata
                log.error(f"[QWEN-TTS] Falha ao carregar modelo: {e}")
                print(f"[QWEN-TTS] Falha ao carregar modelo: {e}")
                _model = None
                return

def gerar_audio_qwen(texto: str, output_path: str) -> bool:
    global _model
    if _model is None:
        return False
        
    try:
        # Garante que a pasta temporária exista
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Caminhos para arquivos de referência de voz (Clonagem)
        ref_audio = "DADOS/vozes/referencia.wav"
        ref_text_path = "DADOS/vozes/referencia.txt"
        
        # A geração em CPU demorará um pouco
        log.info(f"[QWEN-TTS] Processando fala: '{texto[:30]}...'")
        
        res = None
        # Se houver arquivo de áudio e texto de referência, fazemos CLONAGEM
        if os.path.exists(ref_audio) and os.path.exists(ref_text_path):
            with open(ref_text_path, "r", encoding="utf-8") as f:
                ref_text = f.read().strip()
            
            log.info(f"[QWEN-TTS] Usando voz de referência: {ref_audio}")
            # Tenta usar a função de clonagem do modelo
            res = _model.generate_voice_clone(
                text=texto,
                language="Portuguese", # Forçamos português para o Jarvis
                ref_audio=ref_audio,
                ref_text=ref_text
            )
        else:
            # Caso contrário, usa a geração base (voz padrão do modelo)
            res = _model.generate(texto)

        # O generate() retorna os dados de áudio e a taxa de amostragem
        if isinstance(res, tuple):
            wav_data = res[0]
            sr = res[1] if len(res) > 1 else 24000
        else:
            wav_data = res
            sr = 24000

        import numpy as np

        # Se for uma lista (comum em modelos que geram chunks), concatenamos
        if isinstance(wav_data, list):
            processed_chunks = []
            for chunk in wav_data:
                if hasattr(chunk, "cpu"):
                    processed_chunks.append(chunk.cpu().numpy())
                else:
                    processed_chunks.append(np.array(chunk))
            wav_data = np.concatenate(processed_chunks)

        # Converte para numpy se for um único Tensor do PyTorch
        elif hasattr(wav_data, "cpu"):
            wav_data = wav_data.cpu().numpy()
            
        # Garante que seja um array numpy e remove dimensões extras
        wav_data = np.squeeze(np.array(wav_data))

        # Salva o arquivo de áudio WAV
        sf.write(output_path, wav_data, sr)
        return True
    except Exception as e:
        log.error(f"[QWEN-TTS] Erro ao gerar audio: {e}")
        print(f"[QWEN-TTS] ERRO na geracao de voz: {e}")
        return False

if __name__ == "__main__":
    # Script de teste isolado
    print("--- TESTE QWEN-TTS ---")
    init_qwen_tts()
    if _model:
        teste_texto = "Olá senhor, o sistema de voz Qwen3-TTS está pronto e operante."
        os.makedirs("TEMP_AUDIO", exist_ok=True)
        sucesso = gerar_audio_qwen(teste_texto, "TEMP_AUDIO/teste_qwen.wav")
        if sucesso:
            print("Sucesso! Audio gerado em TEMP_AUDIO/teste_qwen.wav")
        else:
            print("Falha na geracao do audio.")
    else:
        print("Modelo nao carregado.")


```


==================================================
 ARQUIVO: .\MODULOS\voice\voice_manager.py
==================================================

```python
import asyncio
import edge_tts
import pygame
import os
import uuid
import random
import pyttsx3
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice.qwen_tts_module import gerar_audio_qwen, init_qwen_tts

STATUS_FALANDO = False
fila_fala = asyncio.PriorityQueue()

# Defer pygame init to avoid hanging on boot
_pygame_inited = False

def init_pygame_safe():
    global _pygame_inited
    if not _pygame_inited:
        try:
            pygame.mixer.init()
            _pygame_inited = True
        except Exception as e:
            print(f"[VOZ] Erro ao inicializar mixer (hardware de som): {e}")

async def falar(bot_nome, texto, prioridade=1):
    if not texto: return
    await fila_fala.put((prioridade, bot_nome, texto))

def _gerar_audio_qwen_sync(texto, arquivo_final):
    # Lazy load here: if model is not loaded, init_qwen_tts will load it.
    init_qwen_tts() 
    return gerar_audio_qwen(texto, arquivo_final)

def _gerar_fallback_pyttsx3(texto, arquivo_final):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        if 'brazil' in v.id.lower() or 'pt' in v.id.lower():
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(texto, arquivo_final)
    engine.runAndWait()

async def processador_de_fala():
    global STATUS_FALANDO
    VOICE = "pt-BR-FranciscaNeural"
    print("[SISTEMA] Processador de voz iniciado (Lazy Loading ativado).")

    while True:
        try:
            prioridade, bot_nome, texto = await fila_fala.get()
            STATUS_FALANDO = True
            
            arquivo_final = f"TEMP_AUDIO/fala_{uuid.uuid4().hex}.wav"
            sucesso_qwen = False
            
            # --- TENTATIVA 1: Qwen3-TTS Local ---
            try:
                # Executa sincronamente, mas em uma thread separada para não travar o loop de eventos
                sucesso = await asyncio.to_thread(_gerar_audio_qwen_sync, texto, arquivo_final)
                if sucesso and os.path.exists(arquivo_final):
                    sucesso_qwen = True
            except Exception as eq:
                print(f"[VOZ] Problema ao rodar Qwen-TTS: {eq}")

            # --- TENTATIVA 2: Fallbacks ANTIGOS ---
            if not sucesso_qwen:
                arquivo_final = arquivo_final.replace('.wav', '.mp3')
                try:
                    # 1. Tenta Voz Neural (Edge-TTS) - já é async nativo
                    communicate = edge_tts.Communicate(texto, VOICE)
                    await communicate.save(arquivo_final)
                    if not os.path.exists(arquivo_final): raise Exception("Falha save MP3")
                except Exception as e:
                    print(f"[VOZ] Edge TTS falhou ({e}). Tentando pyttsx3...")
                    try:
                        arquivo_final = arquivo_final.replace('.mp3', '.wav')
                        # Executa pyttsx3 numa thread separada
                        await asyncio.to_thread(_gerar_fallback_pyttsx3, texto, arquivo_final)
                    except Exception as e2:
                        print(f"[VOZ] Fallback local falhou: {e2}")

            # 3. Reprodução
            if os.path.exists(arquivo_final):
                init_pygame_safe()
                try:
                    pygame.mixer.music.load(arquivo_final)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        agita = random.uniform(0.4, 0.9)
                        await atualizar_jarvis(intensidade=agita, texto=texto)
                        await asyncio.sleep(0.1)
                except Exception as playback_error:
                    print(f"[VOZ] Erro na reprodução: {playback_error}")
                finally:
                    pygame.mixer.music.unload()
                    if os.path.exists(arquivo_final):
                        try: os.remove(arquivo_final)
                        except: pass
                
                await atualizar_jarvis(intensidade=0.1, texto="")
            else:
                print(f"[VOZ] Nenhuma saída de áudio para: '{texto}'")
                await atualizar_jarvis(intensidade=0.1, texto=texto)
                await asyncio.sleep(len(texto) * 0.1)
                await atualizar_jarvis(intensidade=0.1, texto="")

        except Exception as e:
            print(f"[ERRO CRÍTICO VOZ]: {e}")
        finally:
            STATUS_FALANDO = False

```


==================================================
 ARQUIVO: .\TESTES\testar_fala_jarvis.py
==================================================

```python
import os
import sys
import asyncio
from MODULOS.voice.qwen_tts_module import init_qwen_tts, gerar_audio_qwen

def main():
    print("--- INICIANDO TESTE DE VOZ DO JARVIS (QWEN3-TTS) ---")
    
    # 1. Inicializa o modelo
    # Como o init_qwen_tts é síncrono no módulo, chamamos direto
    init_qwen_tts()
    
    # 2. Lista de frases para teste
    frases = [
        "Olá senhor, sou o Jarvis. Minha voz agora é gerada localmente pelo modelo Qwen3-TTS.",
        "Testando a naturalidade da fala em português. O que o senhor achou da minha nova voz?",
        "O sistema está operante e todos os núcleos neurais estão estáveis. Aguardo seus comandos.",
        "A tecnologia avança, e agora posso falar de forma muito mais humana e natural."
    ]
    
    # 3. Cria pasta de teste se não existir
    output_dir = "TESTE_FALA"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"\nOs áudios serão salvos em: {os.path.abspath(output_dir)}")
    
    # 4. Gera os áudios de forma sequencial
    for i, frase in enumerate(frases):
        filename = f"{output_dir}/teste_{i+1}.wav"
        print(f"\n[Gerando {i+1}/{len(frases)}] -> '{frase[:50]}...'")
        
        sucesso = gerar_audio_qwen(frase, filename)
        
        if sucesso:
            print(f"[OK] SUCESSO: Audio gerado em {filename}")
        else:
            print(f"[ERRO] FALHA: Erro ao gerar o audio {i+1}. Verifique se o modelo foi baixado e se o SoX esta instalado.")

    print("\n" + "="*40)
    print("TESTE FINALIZADO!")
    print(f"Va ate a pasta '{output_dir}' para ouvir as amostras.")
    print("="*40)

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

# Adiciona a pasta MODULOS ao path para permitir a importação
sys.path.append(os.path.join(os.path.dirname(__file__), 'MODULOS'))

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
                log_resultado("EAR.HARDWARE", "OK", f"{len(dispositivos)} dispositivos de áudio detectados.")
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
    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO DE DIAGNÓSTICO GLOBAL DO JARVIS\n")
        f.write("="*40 + "\n")
        f.write(f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        for res in resultados:
            f.write(res + "\n")
    
    print(f"\n{Cores.AZUL}="*40)
    print(f"DIAGNÓSTICO CONCLUÍDO!")
    print(f"Relatório salvo em: {RELATORIO_PATH}")
    print(f"="*40 + Cores.RESET)

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
import asyncio
from comunicacao_visual import atualizar_jarvis

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
