from rapidfuzz import fuzz
from MODULOS.voice import voice_manager
from MODULOS.system.logger import log
from MODULOS.ear.recorder import gravar_fala
from MODULOS.ear.models import whisper_tiny

WAKE_WORDS = ["jarvis", "jarbas", "javes", "travis", "garvis", "service", "yaves", "lajardis", "jardis", "jarves"]

def _contem_wake_word(texto: str) -> bool:
    palavras = texto.lower().split()
    for palavra in palavras:
        for wake in WAKE_WORDS:
            if fuzz.ratio(palavra, wake) >= 70:
                return True
    return False

def _transcrever_tiny(arquivo="TEMP_AUDIO/wake.wav") -> str:
    try:
        segments, _ = whisper_tiny.transcribe(
            arquivo,
            language="pt",
            vad_filter=True,
            condition_on_previous_text=False
        )
        return " ".join([s.text for s in segments]).strip().lower()
    except Exception as e:
        log.debug(f"Erro transcrição tiny: {e}")
        return ""

def escutar_wake_word() -> bool:
    if voice_manager.STATUS_FALANDO:
        return False

    if gravar_fala(max_silencio_frames=15, arquivo="TEMP_AUDIO/wake.wav"):
        texto = _transcrever_tiny("TEMP_AUDIO/wake.wav")
        log.debug(f"WAKE - Ouvi: '{texto}'")
        if _contem_wake_word(texto):
            log.info(f"WAKE WORD Detectada! (Ouvi: '{texto}')")
            return True
    return False
