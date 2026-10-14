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
