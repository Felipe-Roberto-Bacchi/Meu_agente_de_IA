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
