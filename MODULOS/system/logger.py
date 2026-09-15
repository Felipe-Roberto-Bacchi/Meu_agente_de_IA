import os
import logging
import colorlog
from datetime import datetime

# Garante que o diretório DADOS exista
LOG_DIR = "DADOS"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "jarvis.log")

def _setup_logger():
    logger = logging.getLogger("Jarvis")
    # Evita adicionar múltiplos handlers se a função for chamada novamente
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    # 1. Handler para Arquivo (Completo, sem cores)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | [%(module)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # 2. Handler para Console (Apenas INFO para cima, com cores)
    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(levelname)s]%(reset)s %(message)s",
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'white',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Instância global do logger
log = _setup_logger()

# Atalhos para uso fácil:
def debug(msg: str): log.debug(msg)
def info(msg: str): log.info(msg)
def warning(msg: str): log.warning(msg)
def error(msg: str): log.error(msg)
def critical(msg: str): log.critical(msg)
def exception(msg: str): log.exception(msg)
