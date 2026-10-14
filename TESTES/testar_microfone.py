"""
testar_microfone.py
───────────────────
Script simplificado e direto para teste do microfone no Jarvis.
Gravação em etapa única com medidor de volume em tempo real e transcrição via Whisper Small.
"""

import os
import sys
import time
import numpy as np

# Garante acesso aos módulos do projeto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import sounddevice as sd
from MODULOS.ear import recorder
from MODULOS.ear.recorder import (
    selecionar_microfone,
    calibrar_ruido,
    garantir_stream,
    gravar_fala,
    FS,
)
from MODULOS.ear.models import carregar_whisper_small

def main():
    print("=" * 60)
    print("      DIAGNÓSTICO E TESTE DO MICROFONE - JARVIS")
    print("=" * 60)

    # 1. Seleciona e exibe dispositivo otimizado
    garantir_stream()
    dev_info = sd.query_devices(recorder.DEVICE_ID) if recorder.DEVICE_ID is not None else sd.query_devices(kind='input')
    print(f"\n[1/4] Microfone Ativo (DirectSound Otimizado):")
    print(f"   Índice [{recorder.DEVICE_ID}]: {dev_info['name']}")
    print(f"   Taxa nativa: {dev_info.get('default_samplerate')} Hz | Taxa Jarvis: {FS} Hz\n")

    # 2. Calibração de silêncio
    print("[2/4] Calibrando nível de ruído...")
    print("-> Por favor, FIQUE EM SILÊNCIO por 2 segundos...")
    calibrar_ruido(duracao=2)
    print(f"-> Limiar de detecção definido para: {recorder.THRESHOLD_BARULHO:.5f}\n")

    # 3. Gravação direta com feedback em tempo real
    print("[3/4] Gravando sua fala:")
    print("=" * 60)
    print(">>> PODE FALAR SUA FRASE AGORA! <<<")
    print("Exemplo: 'Jarvis, você é capaz de me ouvir perfeitamente agora?'")
    print("=" * 60)

    def feedback_terminal(gravando, vol, duracao):
        largura = int(min(vol * 2000, 35))
        barra = "█" * largura + "░" * (35 - largura)
        if gravando:
            sys.stdout.write(f"\r[GRAVANDO] [{barra}] Vol: {vol:.4f} | Duração: {duracao:.1f}s   ")
        else:
            sys.stdout.write(f"\r[AGUARDANDO VOZ] [{barra}] Vol: {vol:.4f}   ")
        sys.stdout.flush()

    arquivo_teste = "TEMP_AUDIO/teste_diagnostico.wav"
    gravou = gravar_fala(max_silencio_frames=35, arquivo=arquivo_teste, callback_feedback=feedback_terminal)
    print("\n")

    if not gravou:
        print("[FALHA] Nenhum som acima do limiar foi capturado.")
        print("DICA: Verifique nas configurações de som do Windows se o microfone não está mudo ou com volume baixo.")
        return

    print(f"[OK] Áudio gravado com sucesso em: {arquivo_teste}")

    # 4. Transcrição com Whisper Small (Alta Precisão em Português)
    print("\n[4/4] Transcrevendo com Whisper Small (modelo de alta precisão)...")
    carregar_whisper_small()
    from MODULOS.ear import models
    
    segs, _ = models.whisper_model.transcribe(
        arquivo_teste,
        language="pt",
        vad_filter=False
    )
    texto = " ".join([s.text for s in segs]).strip()
    
    print("\n" + "=" * 50)
    print(f"TRANSCRITO PELO JARVIS: \"{texto}\"")
    print("=" * 50)

    # 5. Reprodução do áudio gravado
    try:
        import soundfile as sf
        audio_data, samplerate = sf.read(arquivo_teste)
        print("\n-> Reproduzindo o áudio completo que o Jarvis capturou...")
        sd.play(audio_data, samplerate)
        sd.wait()
        print("-> Reprodução concluída.")
    except Exception as e:
        print(f"(Não foi possível reproduzir o áudio: {e})")

    print("\nTeste concluído com sucesso!")

if __name__ == "__main__":
    main()
