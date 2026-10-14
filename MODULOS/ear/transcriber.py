from MODULOS.ear import models
from MODULOS.system.logger import log

def transcrever_audio(arquivo: str = "TEMP_AUDIO/input.wav") -> str:
    try:
        if models.whisper_model is None:
            models.carregar_whisper_small()

        if models.whisper_model is None:
            log.error("[EAR] Não foi possível carregar o modelo Whisper.")
            return ""

        if models._whisper_backend == "openai_whisper_dml":
            import whisper as openai_whisper
            result = openai_whisper.transcribe(
                models.whisper_model,
                arquivo,
                language="pt",
                initial_prompt="Jarvis, comando de voz.",
                fp16=False,
                beam_size=5,
                condition_on_previous_text=False,
            )
            return (result.get("text") or "").strip()

        segments, _ = models.whisper_model.transcribe(
            arquivo,
            language="pt",
            initial_prompt="Jarvis, comando de voz.",
            vad_filter=False,
            beam_size=5,
            condition_on_previous_text=False
        )
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        log.error(f"Erro na transcrição completa: {e}")
        return ""
