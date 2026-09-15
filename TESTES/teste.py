import torch

print(f"Versão do Torch: {torch.__version__}")
print(f"CUDA disponível: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Placa detetada: {torch.cuda.get_device_name(0)}")
else:
    print("A NVIDIA ainda não foi detetada pelo Python.")