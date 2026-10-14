"""
kokoro_tts_module.py
────────────────────
Motor de síntese de voz (TTS) ultraleve e de alta qualidade baseado no Kokoro TTS (KPipeline).
Opera 100% em CPU sem necessidade de binários externos pesados como SoX.
Configurado para Português do Brasil ('p') com vozes masculinas e femininas (ex: 'pm_alex', 'pf_dora').
"""

import os
import soundfile as sf
import numpy as np
from MODULOS.system.logger import log

_pipeline = None

def init_kokoro_tts():
    """
    Inicializa o pipeline do Kokoro TTS de forma preguiçosa (Lazy Loading).
    Utiliza lang_code='p' para Português (Brasil).
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        log.info("[KOKORO-TTS] Inicializando modelo Kokoro TTS na CPU (lang_code='p')...")
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', device='cpu')
        log.info("[KOKORO-TTS] Pipeline carregado com sucesso.")
        return _pipeline
    except ImportError:
        log.warning("[KOKORO-TTS] Pacote 'kokoro' não está instalado. Instale com: pip install kokoro soundfile")
        return None
    except Exception as e:
        log.error(f"[KOKORO-TTS] Falha ao inicializar KPipeline: {e}")
        return None


def gerar_audio_kokoro(texto: str, output_path: str, voz: str = "pm_alex", velocidade: float = 1.1) -> bool:
    """
    Gera arquivo de áudio WAV a partir de texto utilizando Kokoro TTS.
    
    Args:
        texto: Texto a ser sintetizado em voz.
        output_path: Caminho completo para salvar o arquivo .wav.
        voz: Identificador da voz (padrão 'pm_alex' para português masculino, 'pf_dora' para feminino).
        velocidade: Fator de velocidade da fala (padrão 1.1).
        
    Returns:
        bool: True se o áudio foi gerado e salvo com sucesso, False caso contrário.
    """
    global _pipeline
    if not texto or not texto.strip():
        return False

    if _pipeline is None:
        init_kokoro_tts()

    if _pipeline is None:
        return False

    try:
        dir_saida = os.path.dirname(os.path.abspath(output_path))
        if dir_saida:
            os.makedirs(dir_saida, exist_ok=True)

        generator = _pipeline(texto.strip(), voice=voz, speed=velocidade)
        audio_chunks = []

        for gs, ps, audio in generator:
            if audio is not None:
                # Converte tensor PyTorch para NumPy caso necessário
                if hasattr(audio, 'cpu') and hasattr(audio, 'numpy'):
                    audio_arr = audio.cpu().numpy()
                elif hasattr(audio, 'numpy'):
                    audio_arr = audio.numpy()
                else:
                    audio_arr = np.array(audio, dtype=np.float32)

                audio_chunks.append(np.array(audio_arr, dtype=np.float32))

        if not audio_chunks:
            log.warning(f"[KOKORO-TTS] Nenhum chunk de áudio foi retornado para o texto: '{texto[:40]}...'")
            return False

        # Concatena múltiplos trechos em um áudio contínuo
        audio_final = np.concatenate(audio_chunks)
        
        # Salva o arquivo de saída com taxa de amostragem padrão de 24 kHz
        sf.write(output_path, audio_final, 24000)
        return True

    except Exception as e:
        log.error(f"[KOKORO-TTS] Erro durante a geração de áudio: {e}")
        return False
