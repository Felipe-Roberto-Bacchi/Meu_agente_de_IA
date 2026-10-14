"""
qwen_tts_module.py
──────────────────
Módulo mantido para compatibilidade retroativa.
Redireciona chamadas legadas para o novo motor ultraleve kokoro_tts_module.py.
"""

from MODULOS.voice.kokoro_tts_module import (
    init_kokoro_tts as init_qwen_tts,
    gerar_audio_kokoro as gerar_audio_qwen,
)
