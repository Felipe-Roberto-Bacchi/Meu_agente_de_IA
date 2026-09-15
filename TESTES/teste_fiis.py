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
