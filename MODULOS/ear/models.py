from faster_whisper import WhisperModel
import threading
from MODULOS.system.logger import log

whisper_model     = None
whisper_tiny      = None    
_whisper_backend  = None    

def inicializar_whisper_tiny():
    global whisper_tiny
    log.info("Carregando Whisper tiny na CPU (wake word)...")
    whisper_tiny = WhisperModel("tiny", device="cpu", compute_type="int8")
    log.info("Whisper tiny pronto. Small será carregado ao ativar.")

def carregar_whisper_small():
    global whisper_model, _whisper_backend
    if whisper_model is None:
        try:
            import torch
            if torch.cuda.is_available():
                device, compute = "cuda", "float16"
                log.info(f"Carregando Whisper small no {device.upper()} (faster-whisper)...")
                whisper_model = WhisperModel("small", device=device, compute_type=compute)
                _whisper_backend = "faster_whisper"
                log.info("Whisper small pronto.")
                return
        except Exception:
            pass

        try:
            import torch_directml
            if torch_directml.is_available():
                import whisper as openai_whisper
                dml = torch_directml.device()
                log.info("DirectML detectado. Carregando Whisper small no DML (PyTorch)...")
                model = openai_whisper.load_model("small")
                model.to(dml)
                whisper_model = model
                _whisper_backend = "openai_whisper_dml"
                log.info("Whisper small pronto (DirectML).")
                return
        except Exception as e:
            log.warning(f"Backend DirectML indisponível, usando fallback CPU. Motivo: {e}")

        device, compute = "cpu", "int8"
        log.info(f"Carregando Whisper small no {device.upper()} (faster-whisper)...")
        whisper_model = WhisperModel("small", device=device, compute_type=compute)
        _whisper_backend = "faster_whisper"
        log.info("Whisper small pronto.")

def descarregar_whisper_small():
    global whisper_model, _whisper_backend
    if whisper_model is not None:
        log.info("Descarregando Whisper small...")
        del whisper_model
        whisper_model = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass

        if _whisper_backend == "faster_whisper":
            try:
                import torch
                if getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        _whisper_backend = None
        log.info("Recursos liberados.")
