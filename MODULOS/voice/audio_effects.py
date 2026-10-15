"""
audio_effects.py
────────────────
Processamento Digital de Sinais (DSP) para voz do assistente JARVIS.
Simula o efeito acústico autêntico de HUD holográfico / capacete de armadura (Mark suit).
"""

import numpy as np
import scipy.signal

def aplicar_efeito_jarvis_dsp(audio: np.ndarray, sr: int = 24000) -> np.ndarray:
    """
    Aplica processamento DSP para conferir a textura vocal característica da IA JARVIS:
    1. Filtro passa-alta suave em 110 Hz (remove sub-graves abafados) + boost de presença (1800-3500 Hz).
    2. Efeito Holográfico / Armadura: Chorus com atrasos curtos de 11ms (ganho 0.22) e 23ms (ganho 0.10).
    3. Saturação suave (np.tanh) e normalização de pico em 0.90 para corpo e presença constantes.
    """
    if audio is None or len(audio) == 0:
        return audio

    formato_original_2d = audio.ndim == 2
    sinal = audio.flatten().astype(np.float32)

    # 1. Filtro Passa-Alta em 110 Hz suave
    try:
        b_hp, a_hp = scipy.signal.butter(2, 110, btype='highpass', fs=sr)
        audio_hp = scipy.signal.lfilter(b_hp, a_hp, sinal)
    except Exception:
        audio_hp = sinal

    # Boost de Presença (1800 Hz a 3500 Hz) para definição da fala
    try:
        b_band, a_band = scipy.signal.butter(2, [1800, 3500], btype='bandpass', fs=sr)
        presenca = scipy.signal.lfilter(b_band, a_band, audio_hp)
        audio_eq = audio_hp + 0.35 * presenca
    except Exception:
        audio_eq = audio_hp

    # 2. Efeito Holográfico / Capacete (duplo short delay)
    d1 = int(0.011 * sr)  # 11 ms
    d2 = int(0.023 * sr)  # 23 ms

    copia_d1 = np.zeros_like(audio_eq)
    if d1 < len(audio_eq):
        copia_d1[d1:] = audio_eq[:-d1] * 0.22

    copia_d2 = np.zeros_like(audio_eq)
    if d2 < len(audio_eq):
        copia_d2[d2:] = audio_eq[:-d2] * 0.10

    audio_holo = audio_eq + copia_d1 + copia_d2

    # 3. Soft Clipping e Normalização de Pico em 0.90
    audio_tanh = np.tanh(audio_holo * 1.15)
    pico = np.max(np.abs(audio_tanh))
    if pico > 0:
        audio_final = (audio_tanh / pico) * 0.90
    else:
        audio_final = audio_tanh

    if formato_original_2d:
        return audio_final.reshape(-1, 1).astype(np.float32)

    return audio_final.astype(np.float32)
