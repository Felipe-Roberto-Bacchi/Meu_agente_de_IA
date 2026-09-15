import json
import re
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.system.logger import log

def carregar_descricoes_especialistas():
    try:
        with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)
            especialistas = dados.get("especialistas", {})
            return "\n".join([f"- {k}: {v['descricao']}" for k, v in especialistas.items()])
    except Exception as e:
        log.error(f"[REGISTRY]: {e}")
        return "HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA"

def _extrair_json(texto: str) -> dict | None:
    if not texto or not texto.strip():
        return None
    try:
        return json.loads(texto.strip())
    except Exception:
        pass
    sem_markdown = re.sub(r"```(?:json)?\s*", "", texto).replace("```", "")
    match = re.search(r"\{[^{}]+\}", sem_markdown, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    inicio = texto.find("{")
    fim = texto.rfind("}") + 1
    if inicio >= 0 and fim > inicio:
        try:
            return json.loads(texto[inicio:fim])
        except Exception:
            pass
    return None

def _rota_por_keywords(texto: str) -> dict:
    t = texto.lower()

    gatilhos_app = ["abrir", "abre", "iniciar", "executar", "lançar", "start", "abra"]
    gatilhos_hw  = ["temperatura", "cpu", "gpu", "ram", "vram", "verra", "vera", "hardware", "processador", "status", "placa de vídeo", "placa de video", "memória de vídeo", "usando a vram", "usando vram", "processamento", "uso do"]
    gatilhos_cod = ["código", "script", "função", "bug", "erro no código", "programa em python"]
    gatilhos_fii = ["fii", "investimento", "bolsa", "ação", "cotacao", "cotação", "fundo", "oportunidade de compra", "ganhar dinheiro", "mxrf11", "xpml11", "vghf11", "btlg11"]

    gatilhos_salvar = ["guarda", "salva", "anota", "grava", "recorda",
                       "não esqueça", "memoriza", "sabe que"]
    gatilhos_buscar_mem = ["qual é meu", "qual meu", "qual a minha", "qual o meu",
                           "você sabe meu", "lembra meu", "lembra qual", "me diz meu",
                           "quem sou", "como me chamo"]
    gatilhos_esquecer_mem = ["esquece", "apaga", "deleta"]

    for g in gatilhos_app:
        if g in t:
            alvo = t
            for term in gatilhos_app + ["o ", "a ", "por favor", "meu", "minha"]:
                alvo = alvo.replace(term, "")
            return {"categoria": "ABRIR_APP", "alvo": alvo.strip()}

    if any(g in t for g in gatilhos_hw):
        foco = None
        if "cpu" in t or "processador" in t:          foco = "CPU"
        elif "gpu" in t or "placa" in t:              foco = "GPU"
        elif "vram" in t or "memória de vídeo" in t or "memoria de video" in t: foco = "VRAM"
        elif "ram" in t or "memória" in t:            foco = "RAM"
        return {"categoria": "HARDWARE", "alvo": foco}

    if any(g in t for g in gatilhos_salvar + gatilhos_buscar_mem + gatilhos_esquecer_mem):
        return {"categoria": "MEMORIA", "alvo": texto}

    if any(g in t for g in gatilhos_cod):
        return {"categoria": "CODIGO", "alvo": texto}

    if any(g in t for g in gatilhos_fii):
        return {"categoria": "FINANCE", "alvo": texto}

    return {"categoria": "CONVERSA", "alvo": None}

async def rotear_intencao(comando: str) -> dict:
    print("\n[MOCK/TESTE] Roteador LLM desativado para evitar downloads. Usando roteamento básico por palavras-chave.")
    return _rota_por_keywords(comando)
