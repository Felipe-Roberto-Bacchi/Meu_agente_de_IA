import asyncio
import edge_tts
try:
    import pygame
except ImportError:
    pygame = None
import os
import uuid
import random
import pyttsx3
from MODULOS.system.comunicacao_visual import atualizar_jarvis
STATUS_FALANDO = False
fila_fala = asyncio.PriorityQueue()

# Defer pygame init to avoid hanging on boot
_pygame_inited = False

def init_pygame_safe():
    global _pygame_inited
    if not _pygame_inited and pygame is not None:
        try:
            pygame.mixer.init()
            _pygame_inited = True
        except Exception as e:
            print(f"[VOZ] Erro ao inicializar mixer (hardware de som): {e}")

async def falar(bot_nome, texto, prioridade=1):
    if not texto: return
    global STATUS_FALANDO
    STATUS_FALANDO = True
    await fila_fala.put((prioridade, bot_nome, texto))

import re
import json
from MODULOS.voice.kokoro_tts_module import limpar_texto_para_voz, gerar_audio_kokoro, init_kokoro_tts

CONFIG_VOZ_PATH = "DADOS/voice_config.json"

VOZES_DISPONIVEIS = [
    {"id": "kokoro_blend", "motor": "kokoro", "voz": "blend_jarvis", "nome": "🎙️ Kokoro: Jarvis Blend (Stark DSP)"},
    {"id": "kokoro_santa", "motor": "kokoro", "voz": "pm_santa", "nome": "🎙️ Kokoro: Santa (Local CPU - Grave)"},
    {"id": "kokoro_alex", "motor": "kokoro", "voz": "pm_alex", "nome": "🎙️ Kokoro: Alex (Local CPU)"},
    {"id": "kokoro_dora", "motor": "kokoro", "voz": "pf_dora", "nome": "🎙️ Kokoro: Dora (Local CPU - Clara)"},
    {"id": "edge_antonio", "motor": "edge", "voz": "pt-BR-AntonioNeural", "nome": "⚡ Neural: Antonio (Zero CPU - Rápido)"},
    {"id": "edge_francisca", "motor": "edge", "voz": "pt-BR-FranciscaNeural", "nome": "⚡ Neural: Francisca (Zero CPU - Rápido)"},
]

def carregar_config_voz() -> dict:
    if os.path.exists(CONFIG_VOZ_PATH):
        try:
            with open(CONFIG_VOZ_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "motor": "edge",
        "voz": "pt-BR-AntonioNeural",
        "nome": "⚡ Neural: Antonio (Zero CPU - Rápido)",
        "efeito_jarvis": True
    }

def salvar_config_voz(motor: str, voz: str, nome: str = "", efeito_jarvis: bool = None) -> dict:
    os.makedirs(os.path.dirname(CONFIG_VOZ_PATH), exist_ok=True)
    cfg_atual = carregar_config_voz()
    if efeito_jarvis is None:
        if voz == "blend_jarvis":
            efeito_jarvis = True
        else:
            efeito_jarvis = cfg_atual.get("efeito_jarvis", False)

    if not nome:
        for opt in VOZES_DISPONIVEIS:
            if opt["motor"] == motor and opt["voz"] == voz:
                nome = opt["nome"]
                break
    cfg = {
        "motor": motor,
        "voz": voz,
        "nome": nome or f"{motor} - {voz}",
        "efeito_jarvis": bool(efeito_jarvis)
    }
    try:
        with open(CONFIG_VOZ_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[VOZ] Erro salvando config de voz: {e}")
    return cfg

KOKORO_VOICE = "pm_alex"
VOICE = "pt-BR-FranciscaNeural"

def dividir_em_sentencas(texto: str) -> list[str]:
    """
    Divide o texto em chunks inteligentes para streaming com latência zero:
    - O 1º chunk tem entre 40 e 100 caracteres para começar a falar em ~1 segundo.
    - Os chunks seguintes são agrupados entre 150 e 260 caracteres para fala coesa e fluida.
    """
    if not texto or not texto.strip():
        return []

    partes = re.split(r'(?<=[.!?:])\s+|\n+', texto.strip())
    chunks = []
    acumulado = ""
    primeiro_chunk = True

    for p in partes:
        p = p.strip()
        if not p:
            continue

        limite_min = 40 if primeiro_chunk else 150
        limite_max = 100 if primeiro_chunk else 260

        if not acumulado:
            acumulado = p
        else:
            acumulado += " " + p

        if len(acumulado) >= limite_min:
            chunks.append(acumulado)
            acumulado = ""
            primeiro_chunk = False

    if acumulado:
        if chunks and len(acumulado) < 35:
            chunks[-1] += " " + acumulado
        else:
            chunks.append(acumulado)

    return chunks or [texto.strip()]

def _gerar_audio_kokoro_sync(texto, arquivo_final, voz=None, aplicar_dsp=False):
    init_kokoro_tts()
    voz_usar = voz or KOKORO_VOICE
    return gerar_audio_kokoro(texto, arquivo_final, voz=voz_usar, velocidade=1.0, aplicar_dsp=aplicar_dsp)

def _gerar_fallback_pyttsx3(texto, arquivo_final):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        if 'brazil' in v.id.lower() or 'pt' in v.id.lower():
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(texto, arquivo_final)
    engine.runAndWait()

async def _sintetizar_chunk_audio(texto_chunk: str, fallback_voice: str = VOICE, motor: str = None, voz: str = None, efeito_jarvis: bool = None) -> str | None:
    """
    Sintetiza um único chunk de texto para arquivo de áudio
    respeitando o motor ativo ('edge' ou 'kokoro'), voz configurada e efeitos DSP.
    """
    if not texto_chunk or not texto_chunk.strip():
        return None

    os.makedirs("TEMP_AUDIO", exist_ok=True)
    arquivo_wav = f"TEMP_AUDIO/fala_{uuid.uuid4().hex}.wav"
    arquivo_mp3 = arquivo_wav.replace('.wav', '.mp3')

    cfg = carregar_config_voz()
    if motor is None:
        motor = cfg.get("motor", "edge")
    if voz is None:
        voz_ativa = cfg.get("voz", "pt-BR-AntonioNeural")
    else:
        voz_ativa = voz
    if efeito_jarvis is None:
        efeito_jarvis = cfg.get("efeito_jarvis", True)

    if motor == "edge":
        # 1. Tenta Edge-TTS primeiro (Zero CPU, instantâneo)
        voz_edge = voz_ativa if "Neural" in voz_ativa else "pt-BR-AntonioNeural"
        try:
            if "Antonio" in voz_edge:
                communicate = edge_tts.Communicate(texto_chunk, voz_edge, rate="+8%", pitch="-5Hz")
            else:
                communicate = edge_tts.Communicate(texto_chunk, voz_edge)
            await communicate.save(arquivo_mp3)

            if os.path.exists(arquivo_mp3):
                # Se o efeito Stark estiver ativo, aplica o DSP no sinal gerado
                if efeito_jarvis:
                    try:
                        import soundfile as sf
                        from MODULOS.voice.audio_effects import aplicar_efeito_jarvis_dsp
                        audio_data, sr = sf.read(arquivo_mp3)
                        audio_dsp = aplicar_efeito_jarvis_dsp(audio_data, sr)
                        sf.write(arquivo_wav, audio_dsp, sr)
                        try:
                            os.remove(arquivo_mp3)
                        except Exception:
                            pass
                        return arquivo_wav
                    except Exception as edsp:
                        print(f"[VOZ] Erro aplicando DSP no Edge-TTS: {edsp}")
                        return arquivo_mp3
                return arquivo_mp3
        except Exception as e:
            print(f"[VOZ] Edge-TTS falhou ({e}). Tentando Kokoro...")

        # 2. Fallback Kokoro
        try:
            sucesso = await asyncio.to_thread(_gerar_audio_kokoro_sync, texto_chunk, arquivo_wav, "blend_jarvis", efeito_jarvis)
            if sucesso and os.path.exists(arquivo_wav):
                return arquivo_wav
        except Exception as ek:
            print(f"[VOZ] Kokoro-TTS falhou no fallback: {ek}")

    else:
        # 1. Tenta Kokoro TTS primeiro (Local CPU com a voz configurada e Stark DSP)
        voz_kokoro = voz_ativa if not "Neural" in voz_ativa else "blend_jarvis"
        try:
            sucesso = await asyncio.to_thread(_gerar_audio_kokoro_sync, texto_chunk, arquivo_wav, voz_kokoro, efeito_jarvis)
            if sucesso and os.path.exists(arquivo_wav):
                return arquivo_wav
        except Exception as ek:
            print(f"[VOZ] Kokoro-TTS falhou no chunk: {ek}")

        # 2. Fallback Edge-TTS
        try:
            communicate = edge_tts.Communicate(texto_chunk, fallback_voice)
            await communicate.save(arquivo_mp3)
            if os.path.exists(arquivo_mp3):
                return arquivo_mp3
        except Exception as e:
            print(f"[VOZ] Edge-TTS falhou no chunk ({e}). Tentando pyttsx3...")

    # 3. Fallback pyttsx3 offline de emergência
    try:
        await asyncio.to_thread(_gerar_fallback_pyttsx3, texto_chunk, arquivo_wav)
        if os.path.exists(arquivo_wav):
            return arquivo_wav
    except Exception as e2:
        print(f"[VOZ] Fallback local falhou: {e2}")

    return None

async def processador_de_fala():
    global STATUS_FALANDO
    print("[SISTEMA] Processador de voz iniciado (Kokoro TTS com Streaming e Queue contínua).")

    while True:
        try:
            prioridade, bot_nome, texto = await fila_fala.get()
            STATUS_FALANDO = True

            # Sinaliza imediatamente a interface visual que estamos sintetizando áudio
            await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.2, texto="Sintetizando voz... 🔊", padrao="tarefa")

            texto_limpo = limpar_texto_para_voz(texto)
            if not texto_limpo:
                texto_limpo = texto

            chunks = dividir_em_sentencas(texto_limpo)
            if not chunks:
                chunks = [texto_limpo]

            init_pygame_safe()

            # Fila de áudios sintetizados pronta para reprodução imediata
            fila_reproducao = asyncio.Queue(maxsize=12)
            arquivos_para_limpar = []

            # Produtor em background: sintetiza continuamente todos os chunks sem travar a reprodução
            async def produtor_audio():
                for idx, chunk_text in enumerate(chunks):
                    try:
                        arq = await _sintetizar_chunk_audio(chunk_text, VOICE)
                        if arq and os.path.exists(arq):
                            arquivos_para_limpar.append(arq)
                            await fila_reproducao.put((idx, chunk_text, arq))
                        else:
                            await fila_reproducao.put((idx, chunk_text, None))
                    except Exception as e_prod:
                        print(f"[VOZ] Erro na síntese do chunk {idx}: {e_prod}")
                        await fila_reproducao.put((idx, chunk_text, None))
                # Sentinela de término
                await fila_reproducao.put(None)

            produtor_task = asyncio.create_task(produtor_audio())
            primeiro_tocado = False

            while True:
                item = await fila_reproducao.get()
                if item is None:
                    # Todos os chunks foram reproduzidos
                    break

                idx, chunk_text, arquivo_audio = item

                if not primeiro_tocado:
                    # Restaura a legenda com o texto formatado original assim que o áudio começa
                    await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=texto, padrao="falando")
                    primeiro_tocado = True

                if arquivo_audio and os.path.exists(arquivo_audio) and pygame is not None:
                    try:
                        pygame.mixer.music.load(arquivo_audio)
                        pygame.mixer.music.play()

                        # Delay ultrabaixo de 20ms para checagem rápida de fim de reprodução (gapless)
                        while pygame.mixer.music.get_busy():
                            agita = random.uniform(0.4, 0.9)
                            await atualizar_jarvis(intensidade=agita, texto=texto)
                            await asyncio.sleep(0.02)
                    except Exception as playback_error:
                        print(f"[VOZ] Erro na reprodução do chunk {idx}: {playback_error}")
                    finally:
                        try:
                            pygame.mixer.music.unload()
                        except Exception:
                            pass
                        if os.path.exists(arquivo_audio):
                            try:
                                os.remove(arquivo_audio)
                            except Exception:
                                pass
                else:
                    await atualizar_jarvis(intensidade=0.1, texto=texto)
                    await asyncio.sleep(len(chunk_text) * 0.04)

            # Aguarda a tarefa produtora concluir
            try:
                await produtor_task
            except Exception:
                pass

            # Limpeza final de arquivos residuais caso algum tenha sobrado
            for arq in arquivos_para_limpar:
                if os.path.exists(arq):
                    try:
                        os.remove(arq)
                    except Exception:
                        pass

            await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao="conversa")

        except Exception as e:
            print(f"[ERRO CRÍTICO VOZ]: {e}")
        finally:
            STATUS_FALANDO = False
            try:
                from MODULOS.ear.recorder import limpar_pre_buffer
                limpar_pre_buffer()
            except Exception:
                pass
