import os
import time
import warnings
import torch
import soundfile as sf
from MODULOS.system.logger import log

# Suprime o aviso de SoX — não é usado neste módulo (usamos soundfile diretamente)
warnings.filterwarnings("ignore", message=".*SoX.*")
warnings.filterwarnings("ignore", message=".*sox.*")

_model = None

def init_qwen_tts(max_tentativas: int = 3, espera_base: int = 10):
    """
    Inicializa o modelo Qwen3-TTS com retry automático em caso de erro 429
    (Too Many Requests) do HuggingFace.
    
    Args:
        max_tentativas: Número máximo de tentativas de download.
        espera_base: Segundos base de espera (dobra a cada tentativa).
    """
    global _model
    if _model is not None:
        return  # Já carregado, ignora

    for tentativa in range(1, max_tentativas + 1):
        try:
            log.info(f"[QWEN-TTS] Inicializando modelo Qwen3-TTS (CPU). Tentativa {tentativa}/{max_tentativas}...")
            from qwen_tts import Qwen3TTSModel
            
            model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
            _model = Qwen3TTSModel.from_pretrained(model_id, device_map="cpu")
            log.info(f"[QWEN-TTS] Modelo {model_id} carregado com sucesso na CPU!")
            return  # Sucesso, sai do loop

        except Exception as e:
            erro_str = str(e)
            # Trata rate limit do HuggingFace (erro 429)
            if "429" in erro_str or "Too Many Requests" in erro_str:
                espera = espera_base * (2 ** (tentativa - 1))  # 10s, 20s, 40s...
                log.warning(
                    f"[QWEN-TTS] HuggingFace com limite de requisições (429). "
                    f"Aguardando {espera}s antes de tentar novamente... ({tentativa}/{max_tentativas})"
                )
                print(f"[QWEN-TTS] Rate limit do HuggingFace. Tentando novamente em {espera}s...")
                if tentativa < max_tentativas:
                    time.sleep(espera)
                else:
                    log.error("[QWEN-TTS] Todas as tentativas falharam (429). TTS desativado.")
                    print("[QWEN-TTS] Todas as tentativas falharam. O sistema rodará sem voz Qwen.")
                    _model = None
            else:
                # Outro tipo de erro — falha imediata
                log.error(f"[QWEN-TTS] Falha ao carregar modelo: {e}")
                print(f"[QWEN-TTS] Falha ao carregar modelo: {e}")
                _model = None
                return

def gerar_audio_qwen(texto: str, output_path: str) -> bool:
    global _model
    if _model is None:
        return False
        
    try:
        # Garante que a pasta temporária exista
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Caminhos para arquivos de referência de voz (Clonagem)
        ref_audio = "DADOS/vozes/referencia.wav"
        ref_text_path = "DADOS/vozes/referencia.txt"
        
        # A geração em CPU demorará um pouco
        log.info(f"[QWEN-TTS] Processando fala: '{texto[:30]}...'")
        
        res = None
        # Se houver arquivo de áudio e texto de referência, fazemos CLONAGEM
        if os.path.exists(ref_audio) and os.path.exists(ref_text_path):
            with open(ref_text_path, "r", encoding="utf-8") as f:
                ref_text = f.read().strip()
            
            log.info(f"[QWEN-TTS] Usando voz de referência: {ref_audio}")
            # Tenta usar a função de clonagem do modelo
            res = _model.generate_voice_clone(
                text=texto,
                language="Portuguese", # Forçamos português para o Jarvis
                ref_audio=ref_audio,
                ref_text=ref_text
            )
        else:
            # Caso contrário, usa a geração base (voz padrão do modelo)
            res = _model.generate(texto)

        # O generate() retorna os dados de áudio e a taxa de amostragem
        if isinstance(res, tuple):
            wav_data = res[0]
            sr = res[1] if len(res) > 1 else 24000
        else:
            wav_data = res
            sr = 24000

        import numpy as np

        # Se for uma lista (comum em modelos que geram chunks), concatenamos
        if isinstance(wav_data, list):
            processed_chunks = []
            for chunk in wav_data:
                if hasattr(chunk, "cpu"):
                    processed_chunks.append(chunk.cpu().numpy())
                else:
                    processed_chunks.append(np.array(chunk))
            wav_data = np.concatenate(processed_chunks)

        # Converte para numpy se for um único Tensor do PyTorch
        elif hasattr(wav_data, "cpu"):
            wav_data = wav_data.cpu().numpy()
            
        # Garante que seja um array numpy e remove dimensões extras
        wav_data = np.squeeze(np.array(wav_data))

        # Salva o arquivo de áudio WAV
        sf.write(output_path, wav_data, sr)
        return True
    except Exception as e:
        log.error(f"[QWEN-TTS] Erro ao gerar audio: {e}")
        print(f"[QWEN-TTS] ERRO na geracao de voz: {e}")
        return False

if __name__ == "__main__":
    # Script de teste isolado
    print("--- TESTE QWEN-TTS ---")
    init_qwen_tts()
    if _model:
        teste_texto = "Olá senhor, o sistema de voz Qwen3-TTS está pronto e operante."
        os.makedirs("TEMP_AUDIO", exist_ok=True)
        sucesso = gerar_audio_qwen(teste_texto, "TEMP_AUDIO/teste_qwen.wav")
        if sucesso:
            print("Sucesso! Audio gerado em TEMP_AUDIO/teste_qwen.wav")
        else:
            print("Falha na geracao do audio.")
    else:
        print("Modelo nao carregado.")

