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
