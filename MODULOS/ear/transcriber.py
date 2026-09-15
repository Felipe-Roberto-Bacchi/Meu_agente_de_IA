from MODULOS.ear.models import whisper_model, carregar_whisper_small, _whisper_backend
from MODULOS.system.logger import log

def transcrever_audio() -> str:
    try:
        if whisper_model is None:
            carregar_whisper_small()

        if _whisper_backend == "openai_whisper_dml":
            import whisper as openai_whisper
            result = openai_whisper.transcribe(
                whisper_model,
                "TEMP_AUDIO/input.wav",
                language="pt",
                initial_prompt="Jarvis, comando de voz.",
                fp16=False,
                beam_size=5,
                condition_on_previous_text=False,
            )
            return (result.get("text") or "").strip()

        segments, _ = whisper_model.transcribe(
            "TEMP_AUDIO/input.wav",
            language="pt",
            initial_prompt="Jarvis, comando de voz.",
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False
        )
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        log.error(f"Erro na transcrição completa: {e}")
        return ""
