import asyncio
import edge_tts
import pygame
import os
import uuid
import random
import pyttsx3
from MODULOS.system.comunicacao_visual import atualizar_jarvis
from MODULOS.voice.qwen_tts_module import gerar_audio_qwen, init_qwen_tts

STATUS_FALANDO = False
fila_fala = asyncio.PriorityQueue()

# Defer pygame init to avoid hanging on boot
_pygame_inited = False

def init_pygame_safe():
    global _pygame_inited
    if not _pygame_inited:
        try:
            pygame.mixer.init()
            _pygame_inited = True
        except Exception as e:
            print(f"[VOZ] Erro ao inicializar mixer (hardware de som): {e}")

async def falar(bot_nome, texto, prioridade=1):
    if not texto: return
    await fila_fala.put((prioridade, bot_nome, texto))

def _gerar_audio_qwen_sync(texto, arquivo_final):
    # Lazy load here: if model is not loaded, init_qwen_tts will load it.
    init_qwen_tts() 
    return gerar_audio_qwen(texto, arquivo_final)

def _gerar_fallback_pyttsx3(texto, arquivo_final):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        if 'brazil' in v.id.lower() or 'pt' in v.id.lower():
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(texto, arquivo_final)
    engine.runAndWait()

async def processador_de_fala():
    global STATUS_FALANDO
    VOICE = "pt-BR-FranciscaNeural"
    print("[SISTEMA] Processador de voz iniciado (Lazy Loading ativado).")

    while True:
        try:
            prioridade, bot_nome, texto = await fila_fala.get()
            STATUS_FALANDO = True
            
            arquivo_final = f"TEMP_AUDIO/fala_{uuid.uuid4().hex}.wav"
            sucesso_qwen = False
            
            # --- TENTATIVA 1: Qwen3-TTS Local ---
            try:
                # Executa sincronamente, mas em uma thread separada para não travar o loop de eventos
                sucesso = await asyncio.to_thread(_gerar_audio_qwen_sync, texto, arquivo_final)
                if sucesso and os.path.exists(arquivo_final):
                    sucesso_qwen = True
            except Exception as eq:
                print(f"[VOZ] Problema ao rodar Qwen-TTS: {eq}")

            # --- TENTATIVA 2: Fallbacks ANTIGOS ---
            if not sucesso_qwen:
                arquivo_final = arquivo_final.replace('.wav', '.mp3')
                try:
                    # 1. Tenta Voz Neural (Edge-TTS) - já é async nativo
                    communicate = edge_tts.Communicate(texto, VOICE)
                    await communicate.save(arquivo_final)
                    if not os.path.exists(arquivo_final): raise Exception("Falha save MP3")
                except Exception as e:
                    print(f"[VOZ] Edge TTS falhou ({e}). Tentando pyttsx3...")
                    try:
                        arquivo_final = arquivo_final.replace('.mp3', '.wav')
                        # Executa pyttsx3 numa thread separada
                        await asyncio.to_thread(_gerar_fallback_pyttsx3, texto, arquivo_final)
                    except Exception as e2:
                        print(f"[VOZ] Fallback local falhou: {e2}")

            # 3. Reprodução
            if os.path.exists(arquivo_final):
                init_pygame_safe()
                try:
                    pygame.mixer.music.load(arquivo_final)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        agita = random.uniform(0.4, 0.9)
                        await atualizar_jarvis(intensidade=agita, texto=texto)
                        await asyncio.sleep(0.1)
                except Exception as playback_error:
                    print(f"[VOZ] Erro na reprodução: {playback_error}")
                finally:
                    pygame.mixer.music.unload()
                    if os.path.exists(arquivo_final):
                        try: os.remove(arquivo_final)
                        except: pass
                
                await atualizar_jarvis(intensidade=0.1, texto="")
            else:
                print(f"[VOZ] Nenhuma saída de áudio para: '{texto}'")
                await atualizar_jarvis(intensidade=0.1, texto=texto)
                await asyncio.sleep(len(texto) * 0.1)
                await atualizar_jarvis(intensidade=0.1, texto="")

        except Exception as e:
            print(f"[ERRO CRÍTICO VOZ]: {e}")
        finally:
            STATUS_FALANDO = False
