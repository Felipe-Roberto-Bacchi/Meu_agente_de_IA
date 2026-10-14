from MODULOS.system.logger import log
from MODULOS.ear.states import Estado, get_estado, set_estado, verificar_timeout, resetar_timeout
from MODULOS.ear.models import inicializar_whisper_tiny, carregar_whisper_small, descarregar_whisper_small
from MODULOS.ear.recorder import calibrar_ruido, selecionar_microfone, gravar_fala
from MODULOS.ear.wake_word import escutar_wake_word
from MODULOS.ear.farewell import verificar_despedida
from MODULOS.ear.transcriber import transcrever_audio
from MODULOS.voice import voice_manager

from MODULOS.ear import states

# Wrapper para set_estado exportado para manter compatibilidade com código antigo
def set_estado(novo_estado: str):
    states.set_estado(novo_estado, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

def inicializar_whisper():
    carregar_whisper_small()

def capturar_comando_dinamico() -> tuple[bool, str]:
    # ── MODO WAKE WORD COMENTADO TEMPORARIAMENTE A PEDIDO DO USUÁRIO ──
    # estado_atual = get_estado()
    # if estado_atual == Estado.DORMINDO:
    #     if escutar_wake_word():
    #         set_estado(Estado.ATIVO)
    #         resetar_timeout()
    #         return False, Estado.ATIVO
    #     return False, Estado.DORMINDO

    # MODO ESCUTA DIRETA (SEMPRE ATIVO):
    if get_estado() != Estado.ATIVO:
        set_estado(Estado.ATIVO)

    if voice_manager.STATUS_FALANDO:
        return False, Estado.ATIVO

    if gravar_fala(max_silencio_frames=18, arquivo="TEMP_AUDIO/input.wav"):
        resetar_timeout()
        return True, Estado.ATIVO

    return False, Estado.ATIVO
