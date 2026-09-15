from MODULOS.system.logger import log
from MODULOS.ear.states import Estado, get_estado, set_estado, verificar_timeout, resetar_timeout
from MODULOS.ear.models import inicializar_whisper_tiny, carregar_whisper_small, descarregar_whisper_small
from MODULOS.ear.recorder import calibrar_ruido, selecionar_microfone, gravar_fala
from MODULOS.ear.wake_word import escutar_wake_word
from MODULOS.ear.farewell import verificar_despedida
from MODULOS.ear.transcriber import transcrever_audio
from MODULOS.voice import voice_manager

# Configurando as funções de callback no states
from MODULOS.ear import states
states._set_estado = lambda novo: states._set_estado_base(novo, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

# Wrapper para set_estado exportado para manter compatibilidade com código antigo
def set_estado(novo_estado: str):
    states.set_estado(novo_estado, carregar_cb=carregar_whisper_small, descarregar_cb=descarregar_whisper_small)

def inicializar_whisper():
    inicializar_whisper_tiny()

def capturar_comando_dinamico() -> tuple[bool, str]:
    estado_atual = get_estado()

    if estado_atual == Estado.DORMINDO:
        if escutar_wake_word():
            set_estado(Estado.ATIVO)
            resetar_timeout()
            return False, Estado.ATIVO
        return False, Estado.DORMINDO

    # MODO ATIVO
    from MODULOS.ear.recorder import TIMEOUT_ATIVO
    if verificar_timeout(60): # timeout default de 60s
        log.info("EAR Timeout de inatividade. Voltando a dormir.")
        set_estado(Estado.DORMINDO)
        return False, Estado.DORMINDO

    if voice_manager.STATUS_FALANDO:
        return False, estado_atual

    if gravar_fala(max_silencio_frames=35, arquivo="TEMP_AUDIO/input.wav"):
        resetar_timeout()
        return True, estado_atual

    return False, estado_atual
