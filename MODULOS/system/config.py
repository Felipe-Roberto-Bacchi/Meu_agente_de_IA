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
