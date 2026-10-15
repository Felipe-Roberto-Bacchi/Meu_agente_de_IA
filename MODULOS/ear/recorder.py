import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from collections import deque
import queue
import threading
import time
import os
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

FS               = 16000
CHUNK_SIZE       = 1024
THRESHOLD_BARULHO = 0.0025
DEVICE_ID        = None
TIMEOUT_ATIVO    = 60
MAX_DURACAO_FALA = 15.0

# Stream persistente com Pré-Buffer contínuo de 1.5s
_audio_queue = queue.Queue(maxsize=300)
_pre_buffer = deque(maxlen=int(FS / CHUNK_SIZE * 1.5))
_stream = None
_stream_lock = threading.Lock()

def _audio_callback(indata, frames, time_info, status):
    if status:
        pass
    chunk = indata.copy()
    _pre_buffer.append(chunk)
    try:
        _audio_queue.put_nowait(chunk)
    except queue.Full:
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            pass
        _audio_queue.put_nowait(chunk)

def selecionar_microfone():
    global DEVICE_ID
    try:
        devices = sd.query_devices()
        candidato = None
        # Prioriza driver DirectSound (hostapi 1 no Windows) que tem 10x mais ganho e menor latência que MME
        for idx, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                name = d['name'].lower()
                if 'steam' in name or 'mixagem' in name:
                    continue
                if d.get('hostapi') == 1 and ('realtek' in name or 'microf' in name):
                    candidato = idx
                    break

        if candidato is not None:
            DEVICE_ID = candidato
            log.info(f"[EAR] Microfone de alta precisão selecionado (DirectSound): [{DEVICE_ID}] {devices[DEVICE_ID]['name']}")
            return DEVICE_ID

        # Fallback para dispositivo padrão
        info = sd.query_devices(kind='input')
        DEVICE_ID = info.get('index', None)
        log.info(f"[EAR] Microfone padrão: [{DEVICE_ID}] {info.get('name')}")
    except Exception as e:
        DEVICE_ID = None
        log.warning(f"[EAR] Usando dispositivo padrão do sistema ({e})")
    return DEVICE_ID

def garantir_stream():
    """Garante que o stream contínuo do microfone esteja ativo (latência zero)."""
    global _stream, DEVICE_ID
    with _stream_lock:
        if _stream is not None and _stream.active:
            return _stream

        if _stream is not None:
            try:
                _stream.stop()
                _stream.close()
            except Exception:
                pass
            _stream = None

        if DEVICE_ID is None:
            selecionar_microfone()

        try:
            _stream = sd.InputStream(
                samplerate=FS,
                channels=1,
                blocksize=CHUNK_SIZE,
                device=DEVICE_ID,
                callback=_audio_callback
            )
            _stream.start()
            log.info("[EAR] Stream contínuo do microfone ativado com DirectSound (latência zero).")
        except Exception as e:
            log.error(f"[EAR] Falha ao iniciar stream contínuo do microfone: {e}")
            _stream = None
        return _stream

def limpar_pre_buffer():
    global _pre_buffer
    _pre_buffer.clear()

def calibrar_ruido(duracao=2):
    global THRESHOLD_BARULHO
    garantir_stream()
    log.info("[EAR] Calibrando microfone... Fique em silêncio por 2 segundos.")
    
    # Esvazia fila acumulada
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break

    num_chunks = int(duracao * FS / CHUNK_SIZE)
    chunks = []
    fim = time.time() + duracao + 1.0

    while len(chunks) < num_chunks and time.time() < fim:
        try:
            chunk = _audio_queue.get(timeout=0.2)
            chunks.append(chunk)
        except queue.Empty:
            pass

    if chunks:
        dados = np.concatenate(chunks, axis=0)
        rms = float(np.sqrt(np.mean(dados**2)))
        
        # Limiar adaptativo: 2.2x o ruído ambiente, mínimo 0.0008 e máximo 0.012
        novo_threshold = max(0.0008, min(0.012, rms * 2.2))
        THRESHOLD_BARULHO = novo_threshold

        log.info(f"[EAR] Ruído ambiente médio (RMS): {rms:.5f} | Limiar de ativação definido em: {THRESHOLD_BARULHO:.5f}")
    else:
        THRESHOLD_BARULHO = 0.0015

def gravar_fala(max_silencio_frames=16, arquivo="TEMP_AUDIO/input.wav", callback_feedback=None) -> bool:
    global _pre_buffer
    stream = garantir_stream()
    if stream is None or not stream.active:
        return False

    flag_stop = "DADOS/mic_stop.flag"
    flag_cmd = "DADOS/comando_manual.txt"
    if os.path.exists(flag_stop):
        try:
            os.remove(flag_stop)
        except Exception:
            pass

    # 1. Esvazia fila acumulada para ler áudio ao vivo
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break

    audio_buffer = []
    falando = False
    silencio_frames = 0
    chunks_sem_fala = 0
    max_chunks_sem_fala = int(6.0 * FS / CHUNK_SIZE)  # Aguarda até 6s pelo início da fala

    # Limiares adaptativos calibrados
    limiar_ativacao = max(0.0010, THRESHOLD_BARULHO)
    limiar_sustentacao = max(0.0012, THRESHOLD_BARULHO * 0.85)
    MAX_DURACAO_FALA = 15.0  # Teto de segurança: máximo 15 segundos gravando

    while True:
        if os.path.exists("DADOS/mic_muted.flag"):
            while not _audio_queue.empty():
                try:
                    _audio_queue.get_nowait()
                except queue.Empty:
                    break
            _pre_buffer.clear()
            time.sleep(0.2)
            return False

        if voice_manager.STATUS_FALANDO:
            time.sleep(0.05)
            return False

        # Se houver comando manual de texto enviado pela interface, aborta escuta imediatamente
        if os.path.exists(flag_cmd):
            return False

        # Se o usuário clicou no botão "PARAR E ENVIAR" na interface
        if os.path.exists(flag_stop):
            try:
                os.remove(flag_stop)
            except Exception:
                pass
            log.info("[EAR] Parada manual de áudio solicitada via interface. Finalizando captura...")
            if not falando and len(_pre_buffer) > 0:
                audio_buffer.extend(list(_pre_buffer))
            falando = True
            break

        try:
            data = _audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        volume = float(np.linalg.norm(data) / np.sqrt(len(data)))

        if not falando:
            if volume > limiar_ativacao:
                falando = True
                audio_buffer.extend(list(_pre_buffer))
                audio_buffer.append(data.copy())
                silencio_frames = 0
                if callback_feedback:
                    callback_feedback(True, volume, len(audio_buffer) * CHUNK_SIZE / FS)
            else:
                chunks_sem_fala += 1
                if callback_feedback:
                    callback_feedback(False, volume, 0.0)
                if chunks_sem_fala > max_chunks_sem_fala:
                    return False
        else:
            audio_buffer.append(data.copy())
            duracao_atual = len(audio_buffer) * CHUNK_SIZE / FS
            if callback_feedback:
                callback_feedback(True, volume, duracao_atual)

            # Teto de segurança: impede gravação infinita
            if duracao_atual >= MAX_DURACAO_FALA:
                log.info(f"[EAR] Limite de {MAX_DURACAO_FALA}s atingido ({duracao_atual:.1f}s). Processando áudio...")
                break

            limiar_corte_silencio = max(limiar_sustentacao, limiar_ativacao * 0.90)
            if volume > limiar_corte_silencio:
                silencio_frames = 0
            else:
                silencio_frames += 1
                if silencio_frames > max_silencio_frames:
                    break

    if audio_buffer and falando:
        audio_final = np.concatenate(audio_buffer, axis=0)

        # Se tiver pelo menos 0.45s de áudio, salva e processa (evita cliques de mouse/teclado)
        duracao_segundos = len(audio_final) / FS
        if duracao_segundos < 0.45:
            return False

        # Normalização de ganho (AGC)
        max_val = np.max(np.abs(audio_final))
        if max_val > 0.001:
            audio_final = (audio_final / max_val) * 0.85

        dir_saida = os.path.dirname(os.path.abspath(arquivo))
        if dir_saida:
            os.makedirs(dir_saida, exist_ok=True)

        write(arquivo, FS, audio_final.astype(np.float32))
        return True

    return False
