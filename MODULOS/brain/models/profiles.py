PERFIS = {
    "CPU_ONLY": {
        "descricao": "Sem GPU dedicada ou VRAM < 4GB — modelos mínimos na CPU/GPU.",
        "modelos": {
            "ROTEADOR": ["qwen2.5:1.5b"],
            "CONVERSA": ["phi3:mini", "gemma3:1b"],
            "CODIGO": ["qwen2.5-coder:1.5b"],
            "VISAO": ["moondream2"],
            "TAREFA_LONGA": ["qwen2.5:3b"]
        }
    },
    "LOW": {
        "descricao": "VRAM 4-6 GB — Modelos balanceados com quantização leve e AirLLM.",
        "modelos": {
            "ROTEADOR": ["qwen3:1.7b", "qwen2.5:1.5b"],
            "CONVERSA": ["llama3.2:3b", "gemma3:4b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["moondream"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "MEDIUM": {
        "descricao": "VRAM 6-8 GB — Modelos de tamanho médio e grandes offline.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b", "qwen2.5:3b"],
            "CONVERSA": ["qwen2.5:7b", "llama3.2:3b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llava:7b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "HIGH": {
        "descricao": "VRAM 8-12 GB — Modelos maiores para alta precisão.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["llama3.3:8b", "qwen2.5:14b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:11b", "llava:13b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "ULTRA": {
        "descricao": "VRAM 12-16 GB — Modelos muito grandes, quase sem quantização.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["qwen3:14b", "mixtral:8x7b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["qwen2.5vl:7b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "MONSTER": {
        "descricao": "VRAM >= 24 GB — Modelos de ponta, sem compromissos.",
        "modelos": {
            "ROTEADOR": ["qwen3:4b"],
            "CONVERSA": ["llama3.3:70b-q4", "qwen3:32b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:11b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "SERVER": {
        "descricao": "Hardware de servidor — Múltiplas GPUs, alta performance.",
        "modelos": {
            "ROTEADOR": ["qwen3:8b"],
            "CONVERSA": ["llama3.3:70b", "deepseek-v3"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:90b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    },
    "DATACENTER": {
        "descricao": "Datacenter — Máxima performance, modelos de ponta.",
        "modelos": {
            "ROTEADOR": ["qwen3:32b"],
            "CONVERSA": ["deepseek-v3", "llama3.3:70b"],
            "CODIGO": ["Qwen/Qwen2.5-Coder-32B-Instruct-air"],
            "VISAO": ["llama3.2-vision:90b"],
            "TAREFA_LONGA": ["Qwen/Qwen2.5-72B-Instruct-air"]
        }
    }
}

_DESCRICOES = {
    "HARDWARE":     "Monitoramento de CPU, GPU, RAM e temperaturas.",
    "ABRIR_APP":    "Execução de programas e comandos do Windows.",
    "CONVERSA":     "Interações sociais, perguntas e dúvidas gerais.",
    "CODIGO":       "Criação de scripts, depuração e lógica de programação.",
    "VISAO":        "Análise de tela e imagens.",
    "TAREFA_LONGA": "Raciocínio complexo, planejamento e tarefas que exigem múltiplos passos.",
    "MEMORIA":      "Guardar, lembrar ou esquecer informações e fatos pessoais. Ativado por palavras como: guarda, salva, lembra, anota, grava, esquece, sabe que.",
    "WEB_MCP":      "Pesquisas na internet, notícias em tempo real, previsão do tempo, cotações e ferramentas online via protocolo MCP.",
}
