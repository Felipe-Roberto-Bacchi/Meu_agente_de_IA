import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from collections import deque
import time
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

FS               = 16000
THRESHOLD_BARULHO = 0.05
DEVICE_ID        = None

def selecionar_microfone():
    global DEVICE_ID
    DEVICE_ID = None
    try:
        info = sd.query_devices(kind='input')
        log.info(f"Microfone: [{info['index']}] {info['name']}")
    except Exception as e:
        log.warning(f"Usando dispositivo padrão do sistema ({e})")

def calibrar_ruido(duracao=3):
    global THRESHOLD_BARULHO
    selecionar_microfone()
    log.info("Calibrando microfone... Fique em silêncio.")
    try:
        gravacao = sd.rec(int(duracao * FS), samplerate=FS, channels=1, device=DEVICE_ID)
        sd.wait()
        rms = np.sqrt(np.mean(gravacao**2))
        THRESHOLD_BARULHO = max(0.035, rms * 2.8)
        if rms < 0.001:
            log.warning("\nO volume do microfone está EXTREMAMENTE baixo ou mudo.")
            log.warning("Verifique se o dispositivo de entrada padrão do Windows é o correto.\n")
        log.info(f"Filtro definido em: {THRESHOLD_BARULHO:.5f}")
    except Exception as e:
        log.error(f"Erro na calibragem: {e}")
        THRESHOLD_BARULHO = 0.04

def gravar_fala(max_silencio_frames=22, arquivo="TEMP_AUDIO/input.wav") -> bool:
    chunk_size       = 1024
    pre_buffer       = deque(maxlen=int(FS / chunk_size * 1.5))
    audio_buffer     = []
    falando          = False
    silencio_frames  = 0
    
    max_chunks_sem_fala = int(3.0 * FS / chunk_size)
    chunks_sem_fala = 0

    try:
        with sd.InputStream(samplerate=FS, channels=1, blocksize=chunk_size, device=DEVICE_ID) as stream:
            while True:
                if voice_manager.STATUS_FALANDO:
                    return False

                data, _ = stream.read(chunk_size)
                volume   = np.linalg.norm(data) / np.sqrt(len(data))

                if volume > THRESHOLD_BARULHO:
                    if not falando:
                        log.debug(f"Som detectado! Vol: {volume:.4f}")
                        falando = True
                        audio_buffer.extend(list(pre_buffer))
                    audio_buffer.append(data.copy())
                    silencio_frames = 0
                elif falando:
                    audio_buffer.append(data.copy())
                    silencio_frames += 1
                    if silencio_frames > max_silencio_frames:
                        break
                else:
                    pre_buffer.append(data.copy())
                    chunks_sem_fala += 1
                    if chunks_sem_fala > max_chunks_sem_fala:
                        return False

        if audio_buffer:
            audio_final = np.concatenate(audio_buffer, axis=0)
            write(arquivo, FS, audio_final.astype(np.float32))
            return True
    except sd.PortAudioError as e:
        log.error(f"Erro de áudio (PortAudio): {e}")
        time.sleep(1)
    except Exception as e:
        log.error(f"Erro inesperado na gravação: {e}")
        time.sleep(1)
    return False
