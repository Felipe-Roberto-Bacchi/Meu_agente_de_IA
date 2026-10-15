from MODULOS.ear import models
from MODULOS.system.logger import log

def transcrever_audio(arquivo: str = "TEMP_AUDIO/input.wav") -> str:
    try:
        if models.whisper_model is None:
            models.carregar_whisper_small()

        if models.whisper_model is None:
            log.error("[EAR] Não foi possível carregar o modelo Whisper.")
            return ""

        PROMPT_INICIAL = "Jarvis, comando de voz."

        if models._whisper_backend == "openai_whisper_dml":
            import whisper as openai_whisper
            result = openai_whisper.transcribe(
                models.whisper_model,
                arquivo,
                language="pt",
                initial_prompt=PROMPT_INICIAL,
                fp16=False,
                beam_size=5,
                condition_on_previous_text=False,
            )
            texto = (result.get("text") or "").strip()
            if texto == PROMPT_INICIAL or texto.rstrip('.').strip().lower() == PROMPT_INICIAL.rstrip('.').strip().lower():
                return ""
            return texto

        segments, _ = models.whisper_model.transcribe(
            arquivo,
            language="pt",
            initial_prompt=PROMPT_INICIAL,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
            beam_size=5,
            condition_on_previous_text=False
        )
        texto = " ".join([s.text for s in segments]).strip()
        if texto == PROMPT_INICIAL or texto.rstrip('.').strip().lower() == PROMPT_INICIAL.rstrip('.').strip().lower():
            return ""
        return texto
    except Exception as e:
        log.error(f"Erro na transcrição completa: {e}")
        return ""
