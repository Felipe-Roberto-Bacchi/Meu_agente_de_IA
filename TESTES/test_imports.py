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
