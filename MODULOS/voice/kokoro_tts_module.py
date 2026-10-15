"""
kokoro_tts_module.py
────────────────────
Motor de síntese de voz (TTS) ultraleve e de alta qualidade baseado no Kokoro TTS (KPipeline).
Opera 100% em CPU sem necessidade de binários externos pesados como SoX.
Configurado para Português do Brasil ('p') com vozes masculinas e femininas (ex: 'pm_alex', 'pf_dora').
"""

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import os
import re
import soundfile as sf
import numpy as np
from MODULOS.system.logger import log

_pipeline = None

def normalizar_pronuncia_pt(texto: str) -> str:
    """
    Normaliza siglas, expressões numéricas, moedas e abreviações
    para pronúncia clara, fluida e natural em Português pelo sintetizador TTS.
    """
    if not texto:
        return ""

    t = texto

    # 1. Expressões numéricas tipo 6x1 -> 6 por 1
    t = re.sub(r'(\d+)\s*[xX]\s*(\d+)', r'\1 por \2', t)

    # 2. Moeda R$ 100 -> 100 reais
    t = re.sub(r'R\$\s*(\d+(?:[.,]\d+)?)', r'\1 reais', t)

    # 3. Porcentagem e temperatura
    t = re.sub(r'(\d+)\s*%', r'\1 por cento', t)
    t = t.replace('%', ' por cento')
    t = re.sub(r'(\d+)\s*°\s*C\b', r'\1 graus Celsius', t)
    t = t.replace('°C', ' graus Celsius')

    # 4. Siglas e abreviações comuns do português
    expansoes = {
        "SP": "São Paulo",
        "RJ": "Rio de Janeiro",
        "RS": "Rio Grande do Sul",
        "MG": "Minas Gerais",
        "DF": "Distrito Federal",
        "EUA": "Estados Unidos",
        "PEC": "Péc",
        "MEI": "Mêi",
        "PIB": "Píbi",
        "PIX": "Píx",
        "IA": "I A",
        "CPU": "C P U",
        "GPU": "G P U",
        "RAM": "Rãm",
        "VRAM": "V Rãm",
        "SSD": "S S D",
        "HD": "H D",
    }

    def substituir_sigla(match):
        palavra = match.group(0)
        if palavra in expansoes:
            return expansoes[palavra]
        # Para outras siglas de 2 a 4 letras todas em maiúsculo (STF, TSE, OEA, ONU, CNPJ, FII)
        return " ".join(list(palavra))

    t = re.sub(r'\b[A-Z]{2,4}\b', substituir_sigla, t)

    return t

def limpar_texto_para_voz(texto: str) -> str:
    """
    Remove marcações de Markdown, URLs e caracteres visuais,
    aplicando normalização fonética para leitura limpa e fluida pelo sintetizador TTS.
    """
    if not texto or not texto.strip():
        return ""

    t = texto

    # 1. Substitui blocos de código
    t = re.sub(r'```[\s\S]*?```', ' código exibido na tela. ', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # 2. Links Markdown [texto](url) -> texto (deve vir ANTES de remover URLs)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)

    # 3. Remove URLs restantes
    t = re.sub(r'https?://\S+', '', t)

    # 4. Remove títulos (#)
    t = re.sub(r'^#{1,6}\s*', '', t, flags=re.MULTILINE)

    # 5. Remove marcadores de lista (*, -, +, 1.)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)

    # 6. Remove caracteres especiais de Markdown, delimitadores e acentos graves
    t = re.sub(r'[*_~>\[\]|\\#`]', ' ', t)

    # 7. Remove bullets unicode
    t = re.sub(r'[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25CF]', ' ', t)

    # 8. Trata parênteses vazios
    t = re.sub(r'\(\s*\)', ' ', t)

    # 9. Aplica normalização fonética de siglas, números e porcentagens
    t = normalizar_pronuncia_pt(t)

    # 10. Trata quebras de linha como pausas naturais
    linhas = [l.strip() for l in t.splitlines() if l.strip()]
    linhas_com_pausa = []
    for l in linhas:
        if not re.search(r'[.!?:]$', l):
            linhas_com_pausa.append(l + '.')
        else:
            linhas_com_pausa.append(l)

    t = ' '.join(linhas_com_pausa)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\s+([.,!?])', r'\1', t)
    t = re.sub(r'\.{2,}', '.', t)

    return t.strip()

def init_kokoro_tts():
    """
    Inicializa o pipeline do Kokoro TTS de forma preguiçosa (Lazy Loading).
    Utiliza lang_code='p' para Português (Brasil).
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        log.info("[KOKORO-TTS] Inicializando modelo Kokoro TTS na CPU (lang_code='p')...")
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', device='cpu')
        log.info("[KOKORO-TTS] Pipeline carregado com sucesso.")
        return _pipeline
    except ImportError:
        log.warning("[KOKORO-TTS] Pacote 'kokoro' não está instalado. Instale com: pip install kokoro soundfile")
        return None
    except Exception as e:
        log.error(f"[KOKORO-TTS] Falha ao inicializar KPipeline: {e}")
        return None


_cached_voices = {}

def obter_voz_kokoro(voz_id):
    """
    Retorna o tensor ou identificador da voz Kokoro.
    Suporta vozes nativas ('pm_alex', 'pf_dora', 'pm_santa') e
    a voz composta 'blend_jarvis' (70% pm_alex + 30% pm_santa).
    """
    global _pipeline, _cached_voices
    if not isinstance(voz_id, str):
        return voz_id
    if _pipeline is None:
        init_kokoro_tts()
    if _pipeline is None:
        return voz_id

    if voz_id in _cached_voices:
        return _cached_voices[voz_id]

    if voz_id == "blend_jarvis":
        try:
            v_santa = _pipeline.load_voice("pm_santa")
            v_alex = _pipeline.load_voice("pm_alex")
            v_george = _pipeline.load_voice("bm_george")
            blend = v_santa * 0.50 + v_alex * 0.30 + v_george * 0.20
            _cached_voices[voz_id] = blend
            return blend
        except Exception as e:
            log.warning(f"[KOKORO-TTS] Falha ao criar blend_jarvis: {e}. Usando pm_alex.")
            return "pm_alex"

    return voz_id

def gerar_audio_kokoro(texto: str, output_path: str, voz: str = "pm_alex", velocidade: float = 1.0, aplicar_dsp: bool = False) -> bool:
    """
    Gera arquivo de áudio WAV a partir de texto utilizando Kokoro TTS.
    
    Args:
        texto: Texto a ser sintetizado em voz.
        output_path: Caminho completo para salvar o arquivo .wav.
        voz: Identificador da voz (padrão 'pm_alex', 'pf_dora', 'pm_santa' ou 'blend_jarvis').
        velocidade: Fator de velocidade da fala (padrão 1.0 para velocidade natural).
        aplicar_dsp: Se True, aplica o processamento de áudio Stark HUD DSP.
        
    Returns:
        bool: True se o áudio foi gerado e salvo com sucesso, False caso contrário.
    """
    global _pipeline
    if not texto or not texto.strip():
        return False

    texto_limpo = limpar_texto_para_voz(texto)
    if not texto_limpo:
        texto_limpo = texto.strip()

    if _pipeline is None:
        init_kokoro_tts()

    if _pipeline is None:
        return False

    try:
        dir_saida = os.path.dirname(os.path.abspath(output_path))
        if dir_saida:
            os.makedirs(dir_saida, exist_ok=True)

        voz_obj = obter_voz_kokoro(voz)
        generator = _pipeline(texto_limpo, voice=voz_obj, speed=velocidade)
        audio_chunks = []

        for gs, ps, audio in generator:
            if audio is not None:
                # Converte tensor PyTorch para NumPy caso necessário
                if hasattr(audio, 'cpu') and hasattr(audio, 'numpy'):
                    audio_arr = audio.cpu().numpy()
                elif hasattr(audio, 'numpy'):
                    audio_arr = audio.numpy()
                else:
                    audio_arr = np.array(audio, dtype=np.float32)

                audio_chunks.append(np.array(audio_arr, dtype=np.float32))

        if not audio_chunks:
            log.warning(f"[KOKORO-TTS] Nenhum chunk de áudio foi retornado para o texto: '{texto[:40]}...'")
            return False

        # Concatena múltiplos trechos em um áudio contínuo
        audio_final = np.concatenate(audio_chunks)
        
        # Corte de silêncio nas pontas (Audio Trimming de 15ms para gapless playback)
        indices = np.where(np.abs(audio_final) > 0.008)[0]
        if len(indices) > 0:
            margem = int(0.015 * 24000)  # 15 ms
            start_idx = max(0, indices[0] - margem)
            end_idx = min(len(audio_final), indices[-1] + margem + 1)
            audio_final = audio_final[start_idx:end_idx]

        # Processamento Stark HUD DSP (automático no blend_jarvis ou se solicitado explicitamente)
        if aplicar_dsp or voz == "blend_jarvis":
            from MODULOS.voice.audio_effects import aplicar_efeito_jarvis_dsp
            audio_final = aplicar_efeito_jarvis_dsp(audio_final, 24000)

        # Salva o arquivo de saída com taxa de amostragem padrão de 24 kHz
        sf.write(output_path, audio_final, 24000)
        return True

    except Exception as e:
        log.error(f"[KOKORO-TTS] Erro durante a geração de áudio: {e}")
        return False
