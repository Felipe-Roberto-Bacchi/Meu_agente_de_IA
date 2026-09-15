import torch
import torch_directml
from faster_whisper import WhisperModel

def testar_gpu_real():
    print("=== Testando Aceleração Jarvis ===")
    
    # 1. Identifica o hardware
    if torch.cuda.is_available():
        selected_device = "cuda"
        print("[+] Usando NVIDIA CUDA")
    elif torch_directml.is_available():
        # Aqui está o segredo: DirectML
        selected_device = "cpu" 
        print("[!] DirectML detectado. Nota: Para usar GPU AMD no faster-whisper puro")
        print("    o ideal é usar o modo ONNX. Vamos rodar na CPU otimizada por enquanto.")
    else:
        selected_device = "cpu"
        print("[-] Usando CPU Padrão")

    # 2. Carrega com otimização de inteiros (INT8)
    # Isso faz o modelo rodar MUITO rápido mesmo que seja na CPU do seu Ryzen
    try:
        print(f"\nCarregando modelo 'small' em modo {selected_device}...")
        model = WhisperModel("small", device=selected_device, compute_type="int8")
        print("[OK] Modelo carregado!")
    except Exception as e:
        print(f"[ERRO]: {e}")

testar_gpu_real()