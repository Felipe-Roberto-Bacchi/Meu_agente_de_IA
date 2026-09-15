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