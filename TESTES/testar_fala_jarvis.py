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
