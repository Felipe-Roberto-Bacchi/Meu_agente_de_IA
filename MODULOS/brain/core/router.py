import json
import re
import asyncio
import ollama
from MODULOS.brain.selector import selector as brain_selector
from MODULOS.system.logger import log

def carregar_descricoes_especialistas():
    try:
        with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)
            especialistas = dados.get("especialistas", {})
            if especialistas:
                return "\n".join([f"- {k}: {v.get('descricao', '')}" for k, v in especialistas.items()])
    except Exception:
        pass
    try:
        from MODULOS.brain.models.profiles import _DESCRICOES
        return "\n".join([f"- {k}: {v}" for k, v in _DESCRICOES.items()])
    except Exception:
        return "HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA, WEB_MCP, TAREFA_LONGA, FINANCE, VISAO"

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

def _rota_por_keywords(texto: str) -> dict | None:
    t = texto.lower()

    gatilhos_app = ["abrir", "abre", "iniciar", "executar", "lançar", "start", "abra"]
    gatilhos_hw  = ["temperatura", "cpu", "gpu", "ram", "vram", "verra", "vera", "hardware", "processador", "status", "placa de vídeo", "placa de video", "memória de vídeo", "usando a vram", "usando vram", "processamento", "uso do"]
    gatilhos_cod = ["código", "codigo", "script", "função", "funcao", "bug", "erro no código", "programa em python", "escreva um código", "crie uma função"]
    gatilhos_fii = ["fii", "investimento", "bolsa", "ação", "cotacao", "cotação", "fundo", "oportunidade de compra", "ganhar dinheiro", "mxrf11", "xpml11", "vghf11", "btlg11"]
    
    gatilhos_web = [
        "pesquise na internet", "pesquise na web", "pesquisa na internet", "pesquisa na web",
        "pesquise", "pesquisa", "busque na web", "busque na internet", "busca na internet",
        "busca na web", "busque", "notícias sobre", "noticias sobre", "notícia", "noticia",
        "previsão do tempo", "previsao do tempo", "clima em", "clima hoje", "tempo em",
        "temperatura em", "o que aconteceu hoje", "qual o preço atual", "preço atual de",
        "preco atual de", "cotação do dólar", "cotacao do dolar", "preço do bitcoin",
        "preco do bitcoin", "pesquisar na internet", "procure na web", "procure na internet"
    ]

    gatilhos_salvar = ["guarda", "salva", "anota", "grava", "recorda",
                       "não esqueça", "memoriza", "sabe que"]
    gatilhos_buscar_mem = ["qual é meu", "qual meu", "qual a minha", "qual o meu",
                           "você sabe meu", "lembra meu", "lembra qual", "me diz meu",
                           "quem sou", "como me chamo"]
    gatilhos_esquecer_mem = ["esquece", "apaga", "deleta"]

    gatilhos_briefing = [
        "bom dia", "resumo do dia", "notícias de hoje", "noticias de hoje",
        "briefing matinal", "briefing", "telemetria matinal", "giro do dia",
        "panorama do dia", "iniciar briefing"
    ]
    if any(g in t for g in gatilhos_briefing):
        return {"categoria": "BRIEFING", "alvo": texto}

    gatilhos_followup_briefing = [
        "me fale mais sobre", "fale mais sobre", "me fala mais sobre", "fala mais sobre",
        "explique melhor a notícia", "explique melhor a noticia",
        "explique melhor essa notícia", "explique melhor essa noticia",
        "explique a notícia", "explique a noticia", "explique melhor",
        "sobre esse assunto", "sobre este assunto", "sobre essa notícia", "sobre essa noticia",
        "sobre essa materia", "sobre essa matéria", "sobre essa manchete",
        "detalhe a notícia", "detalhe a noticia", "detalhe essa notícia", "detalhe essa noticia",
        "detalhe a matéria", "detalhe a materia", "detalhe mais", "detalhes sobre",
        "me conte mais sobre", "conte mais sobre", "me conta mais sobre", "conta mais sobre",
        "qual é a notícia", "qual e a noticia", "qual é essa notícia", "qual e essa noticia",
        "fale mais dessa notícia", "fale mais dessa noticia",
        "mais detalhes sobre", "mais detalhes da notícia", "mais detalhes dessa notícia"
    ]
    if any(g in t for g in gatilhos_followup_briefing):
        return {"categoria": "BRIEFING_FOLLOWUP", "alvo": texto}

    gatilhos_lembretes = [
        "me lembre de", "me lembre", "lembrar de", "adicionar lembrete",
        "criar lembrete", "novo lembrete", "minha agenda", "meus lembretes",
        "quais são meus lembretes", "quais sao meus lembretes", "listar lembretes",
        "concluir lembrete", "marcar lembrete", "agenda de hoje"
    ]
    if any(g in t for g in gatilhos_lembretes):
        return {"categoria": "LEMBRETES", "alvo": texto}

    # 1. Abertura de apps
    for g in gatilhos_app:
        if g in t:
            alvo = t
            for term in gatilhos_app + ["o ", "a ", "por favor", "meu", "minha"]:
                alvo = alvo.replace(term, "")
            return {"categoria": "ABRIR_APP", "alvo": alvo.strip()}

    # 2. Hardware
    if any(g in t for g in gatilhos_hw):
        foco = None
        if "cpu" in t or "processador" in t:          foco = "CPU"
        elif "gpu" in t or "placa" in t:              foco = "GPU"
        elif "vram" in t or "memória de vídeo" in t or "memoria de video" in t: foco = "VRAM"
        elif "ram" in t or "memória" in t:            foco = "RAM"
        return {"categoria": "HARDWARE", "alvo": foco}

    # 3. Web & Ferramentas Online (MCP)
    if any(g in t for g in gatilhos_web):
        return {"categoria": "WEB_MCP", "alvo": texto}

    # 4. Memória
    if any(g in t for g in gatilhos_salvar + gatilhos_buscar_mem + gatilhos_esquecer_mem):
        return {"categoria": "MEMORIA", "alvo": texto}

    # 5. Código
    if any(g in t for g in gatilhos_cod):
        return {"categoria": "CODIGO", "alvo": texto}

    # 6. Mercado Financeiro
    if any(g in t for g in gatilhos_fii):
        return {"categoria": "FINANCE", "alvo": texto}

    # 7. Visão / Análise de Tela
    gatilhos_visao = [
        "modo de visão", "modo de visao", "modo visão", "modo visao",
        "sua visão", "sua visao", "olha a tela", "olhe a tela",
        "vê na tela", "ve na tela", "o que está na tela", "o que esta na tela",
        "analise a tela", "analisar tela", "tira um print", "tire um print",
        "o que você vê", "o que voce ve", "descreva a tela", "descrever a tela",
        "olhe para a tela", "olha pra tela", "olhe pra tela"
    ]
    if any(g in t for g in gatilhos_visao):
        return {"categoria": "VISAO", "alvo": texto}

    return None

async def rotear_intencao(comando: str) -> dict:
    from MODULOS.brain.nlp_processor import normalizar_fonetica
    comando_normalizado = normalizar_fonetica(comando)

    # 1. Fast-Path por palavras-chave
    rota_rapida = _rota_por_keywords(comando_normalizado)
    if rota_rapida is not None:
        return rota_rapida

    # 2. Roteamento via LLM Roteador para dúvidas ou comandos genéricos
    try:
        modelo_roteador = "qwen2.5:1.5b"
        try:
            with open('DADOS/model_registry.json', 'r', encoding='utf-8') as f:
                dados = json.load(f)
                modelo_roteador = dados.get("modelo_roteador", "qwen2.5:1.5b")
        except Exception:
            pass

        descricoes = carregar_descricoes_especialistas()
        prompt_sistema = (
            "Você é o roteador neural do Jarvis.\n"
            "Analise a intenção do usuário e classifique-a em uma destas categorias:\n"
            f"{descricoes}\n\n"
            "Categorias válidas: HARDWARE, ABRIR_APP, CONVERSA, CODIGO, MEMORIA, WEB_MCP, TAREFA_LONGA, FINANCE, VISAO.\n"
            "Retorne estritamente um JSON no formato:\n"
            '{"categoria": "NOME_CATEGORIA", "alvo": "detalhes_ou_texto"}\n'
            "Responda apenas com o JSON."
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo_roteador,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": comando_normalizado}
                ],
                options={"temperature": 0.0}
            )
        )
        conteudo = response['message']['content']
        decisao = _extrair_json(conteudo)
        if decisao and "categoria" in decisao:
            cat = str(decisao["categoria"]).upper()
            return {"categoria": cat, "alvo": decisao.get("alvo", comando)}
    except Exception as e:
        log.warning(f"[ROTEADOR] Consulta ao modelo roteador falhou: {e}. Usando rota padrão.")

    return {"categoria": "CONVERSA", "alvo": None}
