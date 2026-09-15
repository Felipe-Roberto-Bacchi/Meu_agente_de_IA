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
