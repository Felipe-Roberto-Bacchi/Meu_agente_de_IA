import time
import threading

class Estado:
    DORMINDO = "DORMINDO"
    ATIVO    = "ATIVO"

_estado          = Estado.DORMINDO
_ultimo_comando  = time.time()
_lock_estado     = threading.Lock()

def get_estado() -> str:
    return _estado

def _set_estado(novo: str, carregar_cb=None, descarregar_cb=None):
    global _estado
    with _lock_estado:
        anterior = _estado
        _estado = novo
    if anterior != novo:
        if novo == Estado.ATIVO and carregar_cb:
            threading.Thread(target=carregar_cb, daemon=True).start()
        elif novo == Estado.DORMINDO and descarregar_cb:
            threading.Thread(target=descarregar_cb, daemon=True).start()

def set_estado(novo_estado: str, carregar_cb=None, descarregar_cb=None):
    if novo_estado in [Estado.ATIVO, Estado.DORMINDO]:
        _set_estado(novo_estado, carregar_cb, descarregar_cb)

def verificar_timeout(timeout) -> bool:
    return (time.time() - _ultimo_comando) > timeout

def resetar_timeout():
    global _ultimo_comando
    _ultimo_comando = time.time()
