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
