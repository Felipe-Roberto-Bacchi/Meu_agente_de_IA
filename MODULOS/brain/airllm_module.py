"""
airllm_module.py
────────────────
Fornece uma interface lazy-loaded para modelos grandes via AirLLM,
possibilitando rodar LLMs imensos (como 70B ou 72B) e repassando o gargalo
da VRAM para o I/O de disco.
"""

import sys
import os

# Flag global para manter a instância do modelo aquecida e não instanciar mais de uma vez
_airllm_instance = None
# Guarda o nome do último modelo carregado pra evitar recarregar se for o mesmo
_loaded_model_id = None

def _inicializar_airllm(model_id: str):
    """Inicializa o AirLLM Llama/Qwen de forma preguiçosa (apenas quando solicitado)."""
    global _airllm_instance, _loaded_model_id
    
    # Se já temos um modelo carregado mas é DIFERENTE do que o solicitado agora,
    # precisamos deletar o antigo para liberar a VRAM/RAM (Híbrido SSD/HD)
    if _airllm_instance is not None and _loaded_model_id != model_id:
        print(f"[AIRLLM] Trocando modelo: {_loaded_model_id} -> {model_id}. Limpando memória...")
        del _airllm_instance
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        _airllm_instance = None

    # Se o modelo já está carregado e é o mesmo solicitado, retorna a instância existente
    if _airllm_instance is not None and _loaded_model_id == model_id:
        return _airllm_instance
        
    # --- ESTRATÉGIA DE PERFORMANCE MÁXIMA (HÍBRIDA) ---
    # Original (64GB+) fica no HD para não lotar o PC.
    # Fatias Shards (20GB) ficam no SSD para a IA falar RÁPIDO.
    from MODULOS.system.config import carregar_configuracao
    cfg = carregar_configuracao()
    hd_path = cfg.get("hd_path", "D:\\ModelosIA") if cfg else "D:\\ModelosIA"
    ssd_path = cfg.get("ssd_path", os.path.expanduser("~/.cache/huggingface")) if cfg else os.path.expanduser("~/.cache/huggingface")

    # Sempre buscamos o modelo original no HD para economizar SSD
    os.environ["HF_HOME"] = hd_path
    
    if "72B" in model_id:
        print(f"[AIRLLM] Modo 72B: Tudo no HD ({hd_path}) devido ao tamanho extremo.")
        shards_path = None # Fica tudo no HD
    else:
        # Para o modelo de Código (32B), queremos velocidade SSD nas fatias!
        print(f"[AIRLLM] Modo Performance: Lendo original do HD ({hd_path}) e usando fatias no SSD ({ssd_path})")
        shards_path = os.path.join(ssd_path, "jarvis_shards_32b")
        if not os.path.exists(shards_path):
            os.makedirs(shards_path, exist_ok=True)

    print(f"\n[AIRLLM] Inicializando AirLLM pela primeira vez...")
    print(f"[AIRLLM] Carregando camadas do modelo: {model_id}")
    print(f"[AIRLLM] Isso pode demorar bastante e usar muito espaço em disco (cache HuggingFace).")
    
    try:
        from airllm import AutoModel
        
        # Inicializa com quantização 4-bit para poupar RAM e disco
        # prefetching=True acelera o processo sobrepondo cópia pro disco e cálculo
        _airllm_instance = AutoModel.from_pretrained(
            model_id,
            compression='4bit', 
            profiling_mode=False,
            max_seq_len=2048, # Aumentado de 512 para 2048 para suportar codigos longos
            layer_shards_saving_path=shards_path # Salva o processamento pesado no HD
        )
        _loaded_model_id = model_id
        
        print("[AIRLLM] Modelo carregado com sucesso.\n")
        return _airllm_instance
        
    except ImportError:
        print("[AIRLLM ERRO] airllm não está instalado. Use: pip install airllm bitsandbytes")
        return None
    except Exception as e:
        print(f"[AIRLLM ERRO] Falha crítica ao inicializar modelo: {e}")
        return None


def gerar_resposta_airllm(model_id: str, prompt: str, system_prompt: str = "") -> str:
    """
    Função exposta síncrona para ser chamada com asyncio.to_thread(...).
    Ao rodar, ele acorda o AirLLM (se ainda não estiver acordado).
    """
    modelo = _inicializar_airllm(model_id)
    if modelo is None:
        return "[ERRO INTERNO] Não foi possível carregar o assistente avançado de disco."
        
    try:
        texto_final = system_prompt + "\n\n" + prompt if system_prompt else prompt
        
        # O AirLLM usa a API parecida com a do transformers
        input_tokens = modelo.tokenizer(
            [texto_final],
            return_tensors="pt",
            return_attention_mask=True,
            truncation=True,
            max_length=2048, # Contexto máximo (ajuste se precisar de mais para programação)
            padding=False
        )
        
        # Rodando na GPU
        print("[AIRLLM] Gerando reposta (Lendo camadas do disco)...")
        generation_output = modelo.generate(
            input_tokens['input_ids'].cuda(),
            attention_mask=input_tokens['attention_mask'].cuda(),
            max_new_tokens=1000, # Quantidade maxima de tokens de resposta
            use_cache=True,
            return_dict_in_generate=True
        )
        
        # O resultado é uma lista seq
        output_ids = generation_output.sequences[0]
        
        # Remover os tokens do prompt inicial do output gerado para não ser um eco
        input_length = input_tokens['input_ids'].shape[1]
        resposta_tokens = output_ids[input_length:]
        
        # Decodificar texto final 
        resposta_texto = modelo.tokenizer.decode(resposta_tokens, skip_special_tokens=True)
        return resposta_texto.strip()
        
    except Exception as e:
        print(f"[AIRLLM EXECUCTION ERROR] {e}")
        return f"[ERRO AirLLM Geração] {e}"
