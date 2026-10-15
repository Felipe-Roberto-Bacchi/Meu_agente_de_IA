"""
mcp_client.py
─────────────
Cliente e Gerenciador de Ferramentas MCP (Model Context Protocol) para o Jarvis.
Permite integração com ferramentas externas, servidores MCP oficiais e provedores
de busca na web em tempo real (DuckDuckGo, extração web, clima/tempo), com fallback nativo.
"""

import os
import json
import asyncio
import re
import httpx
import urllib.parse
from typing import Any
from MODULOS.system.logger import log
from MODULOS.brain.selector import selector as brain_selector

MCP_CONFIG_FILE = "DADOS/mcp_servers.json"
NEWS_CONFIG_FILE = "DADOS/news_config.json"

FEEDS_RSS_BRIEFING = {
    "mundo": {
        "rotulo": "🌍 CENÁRIO INTERNACIONAL / EUA & GEOPOLÍTICA",
        "url": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 3
    },
    "economia": {
        "rotulo": "📈 ECONOMIA, MERCADOS & EMPRESAS",
        "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 3
    },
    "brasil": {
        "rotulo": "🇧🇷 BRASIL & POLÍTICA NACIONAL",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 2
    },
    "tecnologia": {
        "rotulo": "💻 TECNOLOGIA, CIÊNCIA & IA",
        "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "limite": 2
    }
}

def carregar_config_noticias() -> dict:
    if os.path.exists(NEWS_CONFIG_FILE):
        try:
            with open(NEWS_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[MCP/NEWS] Erro ao carregar config notícias: {e}")
    return {
        "categorias": ["mundo", "economia", "brasil", "tecnologia"],
        "incluir_cotacoes": True,
        "detalhamento": "completo"
    }

def salvar_config_noticias(cfg: dict) -> dict:
    os.makedirs(os.path.dirname(NEWS_CONFIG_FILE), exist_ok=True)
    try:
        with open(NEWS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"[MCP/NEWS] Erro ao salvar config notícias: {e}")
    return cfg

def _limpar_titulo_noticia(titulo: str) -> str:
    """Remove o sufixo ' - Veículo' e espaços extras."""
    t = re.sub(r'\s+-\s+[^-]+$', '', titulo.strip())
    return t.strip()

async def obter_panorama_mercado() -> str:
    """
    Busca em ~1 segundo cotações globais e variação percentual de hoje:
    Dólar, Euro, Bitcoin (AwesomeAPI) e Ibovespa, S&P 500 (Yahoo Finance).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    linhas = []
    try:
        async with httpx.AsyncClient(headers=headers, timeout=2.5) as client:
            res_cambio, res_ibov, res_sp = await asyncio.gather(
                client.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval=1d&range=1d"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=1d"),
                return_exceptions=True
            )

            if isinstance(res_cambio, httpx.Response) and res_cambio.status_code == 200:
                dados = res_cambio.json()
                if "USDBRL" in dados:
                    d = dados["USDBRL"]
                    linhas.append(f"• Dólar Comercial: R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}%)")
                if "EURBRL" in dados:
                    d = dados["EURBRL"]
                    linhas.append(f"• Euro Comercial: R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}%)")
                if "BTCUSD" in dados:
                    d = dados["BTCUSD"]
                    linhas.append(f"• Bitcoin: US$ {float(d['bid']):,.0f} ({float(d['pctChange']):+.2f}%)")

            if isinstance(res_ibov, httpx.Response) and res_ibov.status_code == 200:
                try:
                    meta = res_ibov.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")
                    if price and prev:
                        var = ((price - prev) / prev) * 100
                        linhas.append(f"• Ibovespa (B3 Brasil): {price:,.0f} pts ({var:+.2f}%)")
                except Exception:
                    pass

            if isinstance(res_sp, httpx.Response) and res_sp.status_code == 200:
                try:
                    meta = res_sp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")
                    if price and prev:
                        var = ((price - prev) / prev) * 100
                        linhas.append(f"• S&P 500 (Wall St EUA): {price:,.0f} pts ({var:+.2f}%)")
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"[MCP/NEWS] Falha ao coletar panorama de mercado: {e}")

    if linhas:
        return "📊 COTAÇÕES GLOBAIS E MERCADO FINANCEIRO HOJE:\n" + "\n".join(linhas)
    return ""

async def _buscar_feed_categoria(client: httpx.AsyncClient, cat_id: str, titulos_vistos: set) -> tuple[str, list[str]]:
    info = FEEDS_RSS_BRIEFING.get(cat_id)
    if not info:
        return "", []
    rotulo = info["rotulo"]
    url = info["url"]
    limite = info["limite"]

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            items = root.findall('.//item')
            noticias = []
            for it in items:
                title_el = it.find('title')
                if title_el is not None and title_el.text:
                    tit_limpo = _limpar_titulo_noticia(title_el.text)
                    chave = re.sub(r'[^a-zA-Z0-9]', '', tit_limpo.lower())[:35]
                    if chave in titulos_vistos:
                        continue
                    titulos_vistos.add(chave)
                    noticias.append(f"• {tit_limpo}")
                    if len(noticias) >= limite:
                        break
            return rotulo, noticias
    except Exception as e:
        log.warning(f"[MCP/NEWS] Erro ao buscar feed '{cat_id}': {e}")
    return rotulo, []

async def buscar_briefing_executivo_global() -> str:
    """
    Executa o Briefing Executivo Global Multi-Fontes:
    Busca em paralelo no Google News RSS (Mundo, Economia, Brasil, Tecnologia)
    e anexa o panorama de cotações financeiras em tempo real no topo.
    """
    config = carregar_config_noticias()
    cats_ativas = config.get("categorias", ["mundo", "economia", "brasil", "tecnologia"])
    incluir_cotacoes = config.get("incluir_cotacoes", True)

    blocos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}

    log.info(f"[MCP/NEWS] Compilando Briefing Executivo Global Multi-Fontes (Categorias: {cats_ativas})...")

    titulos_vistos = set()
    async with httpx.AsyncClient(headers=headers, timeout=5.0, follow_redirects=True) as client:
        tarefas = []
        if incluir_cotacoes:
            tarefas.append(obter_panorama_mercado())

        for cat in cats_ativas:
            if cat in FEEDS_RSS_BRIEFING:
                tarefas.append(_buscar_feed_categoria(client, cat, titulos_vistos))

        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        idx = 0
        if incluir_cotacoes:
            res_cotacoes = resultados[0]
            idx += 1
            if isinstance(res_cotacoes, str) and res_cotacoes.strip():
                blocos.append(res_cotacoes.strip())

        for res in resultados[idx:]:
            if isinstance(res, tuple):
                rotulo, noticias = res
                if noticias:
                    blocos.append(f"{rotulo}:\n" + "\n".join(noticias))

    if blocos:
        return "[BRIEFING EXECUTIVO GLOBAL - DADOS EM TEMPO REAL DE HOJE]\n\n" + "\n\n".join(blocos)

    return await buscar_web("principais notícias hoje brasil mundo tecnologia economia", max_resultados=6)

# ──────────────────────────────────────────────────────────
#  FERRAMENTAS NATIVAS DE FALLBACK (OUT-OF-THE-BOX)
# ──────────────────────────────────────────────────────────

async def buscar_noticias_hoje(tema: str = "") -> str:
    """
    Consulta manchetes e notícias em tempo real via feeds RSS do Google News e Yahoo Finance.
    Se o tema for geral/vazio, compila o Briefing Executivo Global Multi-Fontes em paralelo.
    Se o tema for específico, realiza a busca focada.
    """
    tema_limpo = (tema or "").strip().lower()
    termos_genericos = [
        "", "mundo", "hoje", "principais", "notícias", "noticias", "geral",
        "brasil", "ultimas", "últimas", "notícia", "noticia", "dia", "acontecendo",
        "panorama", "briefing", "resumo", "giro", "manchetes", "manchete"
    ]

    if tema_limpo in termos_genericos or not tema_limpo:
        return await buscar_briefing_executivo_global()

    for stop in ["notícias de", "noticias de", "notícias sobre", "noticias sobre", "notícias", "noticias", "sobre"]:
        tema_limpo = tema_limpo.replace(stop, "").strip()

    if not tema_limpo:
        return await buscar_briefing_executivo_global()

    url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(tema_limpo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    log.info(f"[MCP/NEWS] Buscando notícias sobre '{tema_limpo}' via Google News RSS...")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                items = root.findall('.//item')
                if items:
                    noticias = []
                    titulos_vistos = set()
                    for it in items[:6]:
                        title_el = it.find('title')
                        pub_el = it.find('pubDate')
                        if title_el is not None and title_el.text:
                            tit = _limpar_titulo_noticia(title_el.text)
                            chave = re.sub(r'[^a-zA-Z0-9]', '', tit.lower())[:35]
                            if chave in titulos_vistos:
                                continue
                            titulos_vistos.add(chave)
                            pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                            if pub:
                                noticias.append(f"• {tit} ({pub})")
                            else:
                                noticias.append(f"• {tit}")
                    if noticias:
                        return f"Notícias em tempo real sobre '{tema_limpo}' obtidas hoje:\n" + "\n".join(noticias)
    except Exception as e:
        log.error(f"[MCP/NEWS] Erro ao buscar Google News RSS para '{tema_limpo}': {e}")

    return await buscar_web(f"noticias {tema_limpo}".strip(), max_resultados=5)


async def buscar_web(termo: str, max_resultados: int = 5) -> str:
    """Busca informações na web usando DuckDuckGo com múltiplos fallbacks."""
    termo = termo.strip()
    
    # Limpa termos conversacionais que atrapalham a busca na web
    termo_busca = termo
    for stop_word in [
        "me fale sobre", "me fale", "como está o", "como esta o", "como está a", "como esta a",
        "como está", "como esta", "tem alguma notícia relevante sobre", "tem alguma notícia sobre",
        "tem alguma noticia sobre", "o que você sabe sobre", "o que voce sabe sobre",
        "pesquise na internet sobre", "pesquise na web sobre", "pesquise sobre", "pesquise",
        "pesquisa sobre", "pesquisa", "busque sobre", "busque", "por favor", "me diga", "me conte"
    ]:
        if termo_busca.lower().startswith(stop_word):
            termo_busca = termo_busca[len(stop_word):].strip()
        else:
            termo_busca = re.sub(re.escape(stop_word), "", termo_busca, flags=re.IGNORECASE).strip()

    if not termo_busca:
        termo_busca = termo

    log.info(f"[MCP/WEB] Executando busca por: '{termo_busca}'")

    # 1. Tenta biblioteca oficial ddgs / duckduckgo_search silenciando warnings
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS

        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(termo_busca, max_results=max_resultados):
                titulo = r.get("title", "")
                link = r.get("href", "")
                snippet = r.get("body", "")
                resultados.append(f"• Título: {titulo}\n  Link: {link}\n  Resumo: {snippet}")
        if resultados:
            return "\n\n".join(resultados)
    except Exception as e:
        log.debug(f"[MCP/WEB] ddgs library indisponível ou falhou: {e}. Usando fallback HTTP.")

    # 2. Fallback HTTP direto via DuckDuckGo HTML
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(termo_busca)}", headers=headers)
            if resp.status_code == 200:
                texto_html = resp.text
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(texto_html, "html.parser")
                resultados = []
                for res in soup.find_all("div", class_="result", limit=max_resultados):
                    tit_tag = res.find("a", class_="result__a")
                    snip_tag = res.find("a", class_="result__snippet")
                    if tit_tag:
                        titulo = tit_tag.get_text(strip=True)
                        link = tit_tag.get("href", "")
                        snippet = snip_tag.get_text(strip=True) if snip_tag else ""
                        resultados.append(f"• Título: {titulo}\n  Link: {link}\n  Resumo: {snippet}")
                if resultados:
                    return "\n\n".join(resultados)
    except Exception as e:
        log.error(f"[MCP/WEB] Falha no fallback DuckDuckGo HTML: {e}")

    # 3. Fallback Wikipedia API em português
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            url_wiki = f"https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(termo_busca)}&utf8=&format=json"
            r = await client.get(url_wiki)
            if r.status_code == 200:
                dados = r.json()
                itens = dados.get("query", {}).get("search", [])[:max_resultados]
                if itens:
                    limpos = []
                    for item in itens:
                        tit = item.get("title", "")
                        snip = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                        limpos.append(f"• {tit}: {snip}")
                    return "\n".join(limpos)
    except Exception as e:
        log.error(f"[MCP/WEB] Falha no fallback Wikipedia: {e}")

    return f"Não foi possível obter dados online atualizados sobre '{termo}' no momento."


async def obter_previsao_tempo(cidade: str) -> str:
    """Consulta informações meteorológicas em tempo real para uma cidade."""
    log.info(f"[MCP/TEMPO] Buscando previsão para: {cidade}")
    cidade_limpa = cidade.strip().replace(" ", "+")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"https://wttr.in/{cidade_limpa}?format=j1")
            if resp.status_code == 200:
                dados = resp.json()
                atual = dados.get("current_condition", [{}])[0]
                temp = atual.get("temp_C", "N/A")
                sensacao = atual.get("FeelsLikeC", "N/A")
                umidade = atual.get("humidity", "N/A")
                vento = atual.get("windspeedKmph", "N/A")
                desc = atual.get("lang_pt", [{}])[0].get("value") if "lang_pt" in atual else atual.get("weatherDesc", [{}])[0].get("value", "Tempo estável")
                return (
                    f"Condições meteorológicas para {cidade}:\n"
                    f"- Condição: {desc}\n"
                    f"- Temperatura atual: {temp}°C (sensação de {sensacao}°C)\n"
                    f"- Umidade: {umidade}%\n"
                    f"- Velocidade do vento: {vento} km/h"
                )
    except Exception as e:
        log.error(f"[MCP/TEMPO] Erro ao obter previsão do tempo: {e}")

    return f"Não foi possível consultar a previsão meteorológica para '{cidade}' no momento."


async def obter_conteudo_url(url: str) -> str:
    """Baixa e extrai o texto principal de uma URL."""
    log.info(f"[MCP/FETCH] Lendo URL: {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for s in soup(["script", "style", "nav", "footer"]):
                    s.decompose()
                texto = soup.get_text(separator=" ", strip=True)
                return texto[:2500] + ("..." if len(texto) > 2500 else "")
    except Exception as e:
        log.error(f"[MCP/FETCH] Erro ao ler URL: {e}")
    return f"Falha ao carregar conteúdo da página {url}."


# Definição dos Schemas de ferramentas nativas no padrão Ollama
FERRAMENTAS_NATIVAS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "buscar_noticias_hoje",
            "description": "Obtém o Briefing Executivo Global de hoje em tempo real, cobrindo cotações financeiras, notícias internacionais/EUA, economia, Brasil e tecnologia. Use sempre que o usuário perguntar por notícias, manchetes, briefing diário ou o que está acontecendo no Brasil e no mundo hoje.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {
                        "type": "string",
                        "description": "Tema específico (ex: 'Petrobras', 'IA') ou deixe vazio para o Briefing Executivo completo de hoje."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_web",
            "description": "Busca informações atualizadas na internet sobre fatos, notícias, cotações, pessoas ou eventos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo ou frase chave para a pesquisa na web."
                    }
                },
                "required": ["termo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_previsao_tempo",
            "description": "Obtém a previsão do tempo atual e condições climáticas de uma cidade ou localidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {
                        "type": "string",
                        "description": "Nome da cidade (ex: São Paulo, Rio de Janeiro, Curitiba, Nova York)."
                    }
                },
                "required": ["cidade"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_conteudo_url",
            "description": "Lê e extrai o conteúdo em texto de um site ou página web a partir de sua URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "A URL completa da página a ser lida."
                    }
                },
                "required": ["url"]
            }
        }
    }
]


# ──────────────────────────────────────────────────────────
#  GERENCIADOR MCP CLIENT
# ──────────────────────────────────────────────────────────

def carregar_config_mcp() -> dict:
    if os.path.exists(MCP_CONFIG_FILE):
        try:
            with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[MCP] Erro ao ler {MCP_CONFIG_FILE}: {e}")
    return {"mcpServers": {}}


async def executar_ferramenta_local(nome: str, argumentos: dict) -> str:
    """Executa as ferramentas nativas de fallback."""
    if nome == "buscar_noticias_hoje":
        tema = argumentos.get("tema") or argumentos.get("query") or argumentos.get("termo") or ""
        return await buscar_noticias_hoje(str(tema))
    elif nome == "buscar_web":
        termo = argumentos.get("termo") or argumentos.get("query") or argumentos.get("q") or ""
        return await buscar_web(str(termo))
    elif nome == "obter_previsao_tempo":
        cidade = argumentos.get("cidade") or argumentos.get("location") or argumentos.get("city") or "São Paulo"
        return await obter_previsao_tempo(str(cidade))
    elif nome == "obter_conteudo_url":
        url = argumentos.get("url") or ""
        return await obter_conteudo_url(str(url))
    else:
        return f"Ferramenta desconhecida: {nome}"


async def coletar_ferramentas_mcp() -> tuple[list[dict], dict[str, Any]]:
    """
    Coleta ferramentas tanto de servidores MCP externos configurados (se houver e estiverem disponíveis)
    quanto das ferramentas nativas integradas.
    """
    ferramentas_ollama = list(FERRAMENTAS_NATIVAS_SCHEMA)
    mapa_executores = {
        "buscar_noticias_hoje": executar_ferramenta_local,
        "buscar_web": executar_ferramenta_local,
        "obter_previsao_tempo": executar_ferramenta_local,
        "obter_conteudo_url": executar_ferramenta_local,
    }

    # Tenta inspecionar servidores externos se o SDK mcp estiver instalado
    try:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession

        config = carregar_config_mcp()
        servidores = config.get("mcpServers", {})

        for srv_name, srv_conf in servidores.items():
            cmd = srv_conf.get("command")
            args = srv_conf.get("args", [])
            env = srv_conf.get("env")
            if not cmd or srv_name == "web-search":
                continue

            try:
                params = StdioServerParameters(command=cmd, args=args, env=env)
                # Tenta conexão rápida com timeout curto para não travar
                async with asyncio.timeout(2.0):
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_resp = await session.list_tools()
                            for t in tools_resp.tools:
                                schema_ollama = {
                                    "type": "function",
                                    "function": {
                                        "name": f"{srv_name}__{t.name}",
                                        "description": t.description or "",
                                        "parameters": t.inputSchema or {}
                                    }
                                }
                                ferramentas_ollama.append(schema_ollama)
            except Exception as e:
                log.debug(f"[MCP] Servidor MCP '{srv_name}' não está ativo no momento ({e}).")
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"[MCP] Inspecção de servidores MCP: {e}")

    return ferramentas_ollama, mapa_executores


async def executar_comandos_mcp_ou_web(pergunta: str) -> str:
    """
    Fluxo orquestrado de execução de ferramentas via MCP / Web:
    1. Envia a pergunta do usuário com a lista de tools para o modelo Ollama.
    2. Captura os tool_calls solicitados pelo modelo.
    3. Executa as ferramentas via MCP ou fallback nativo.
    4. Envia o resultado de volta para o LLM gerar a resposta elegante em português para o Jarvis falar.
    """
    import ollama

    # Escolhe o modelo mais apropriado para function calling e raciocínio
    modelo, _ = brain_selector.escolher_melhor_modelo("CONVERSA")

    tools_schema, mapa_exec = await coletar_ferramentas_mcp()

    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y")

    termos_noticia = [
        "notícia", "noticia", "notícias", "noticias", "acontecendo hoje",
        "mundo hoje", "manchetes", "manchete", "últimas notícias", "ultimas noticias",
        "o que aconteceu hoje", "acontecimentos de hoje", "novidades de hoje",
        "briefing", "resumo do dia", "giro de notícias", "giro do dia", "panorama",
        "mercado financeiro", "cotações", "cotacoes", "como está o mundo", "como esta o mundo"
    ]
    pergunta_lower = pergunta.lower()
    eh_noticia = any(k in pergunta_lower for k in termos_noticia)

    PROMPT_BRIEFING_EXECUTIVO = (
        "Você está apresentando o Briefing Executivo Diário para o senhor. "
        "Faça um panorama abrangente, elegante e fluido cobrindo TODAS as áreas fornecidas nos dados abaixo: "
        "comece pelo cenário Internacional/EUA e Geopolítica, passe pelo Mercado Financeiro (citando as cotações e bolsas), "
        "destaque o cenário no Brasil e finalize com Tecnologia. Cite pelo menos 5 a 6 fatos distintos de forma dinâmica, "
        "direta e sem usar asteriscos ou markdown, como um verdadeiro assistente executivo de alto nível."
    )

    if eh_noticia:
        system_prompt = (
            f"Hoje é dia {data_atual}.\n"
            "Você é o assistente executivo Jarvis apresentando o Briefing Executivo Diário em tempo real para o senhor.\n"
            "PROIBIDO inventar fatos ou notícias antigas de anos anteriores. Baseie-se estritamente nos dados em tempo real fornecidos abaixo.\n"
            f"{PROMPT_BRIEFING_EXECUTIVO}"
        )
    else:
        system_prompt = (
            f"Hoje é dia {data_atual}.\n"
            "Você é o assistente Jarvis com acesso a ferramentas em tempo real via internet e protocolo MCP.\n"
            "PROIBIDO inventar dados ou fatos antigos do seu treinamento.\n"
            "Baseie-se estritamente nas informações em tempo real obtidas pelas ferramentas.\n"
            "Formule uma resposta clara, natural, cortês e direta ao ponto em português para ser falada pela sua voz, sem usar asteriscos ou markdown."
        )

    mensagens = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": pergunta}
    ]

    try:
        loop = asyncio.get_running_loop()
        
        # 1. Primeira chamada com tools ativas
        resp = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo,
                messages=mensagens,
                tools=tools_schema
            )
        )

        msg = resp.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        # 2. Se o modelo não gerou tool_calls automaticamente mas a pergunta é nitidamente uma busca
        if not tool_calls:
            termos_clima = ["tempo em", "temperatura em", "previsão do tempo", "clima"]
            eh_clima = any(k in pergunta_lower for k in termos_clima)

            if eh_noticia:
                tema_noticia = pergunta_lower
                for c in ["quais são as", "quais as", "notícias de", "noticias de", "notícias sobre", "noticias sobre", "notícias", "noticias", "de hoje", "hoje", "acontecendo", "me fale sobre", "principais"]:
                    tema_noticia = tema_noticia.replace(c, "").strip()
                resultado_ferramenta = await buscar_noticias_hoje(tema_noticia)
                mensagens.append({"role": "assistant", "content": "Compilando o Briefing Executivo Diário..."})
                mensagens.append({
                    "role": "user",
                    "content": (
                        f"Com base nestes dados executivos e notícias em tempo real obtidos hoje ({data_atual}):\n\n"
                        f"{resultado_ferramenta}\n\n"
                        f"{PROMPT_BRIEFING_EXECUTIVO}"
                    )
                })
            elif eh_clima:
                cidade = pergunta_lower
                for c in ["qual a", "previsão do tempo em", "tempo em", "clima em", "temperatura em", "como está o", "como esta o", "por favor"]:
                    cidade = cidade.replace(c, "").strip()
                resultado_ferramenta = await obter_previsao_tempo(cidade)
                mensagens.append({"role": "assistant", "content": "Consultando o clima..."})
                mensagens.append({
                    "role": "user",
                    "content": f"Com base nestes dados meteorológicos obtidos em tempo real hoje ({data_atual}):\n\n{resultado_ferramenta}\n\nResponda com naturalidade ao senhor sobre: '{pergunta}'. Não use asteriscos ou formatação markdown."
                })
            else:
                resultado_ferramenta = await buscar_web(pergunta)
                mensagens.append({"role": "assistant", "content": "Consultando a rede mundial de computadores..."})
                mensagens.append({
                    "role": "user",
                    "content": f"Com base nestes dados obtidos na rede hoje ({data_atual}):\n\n{resultado_ferramenta}\n\nResponda com elegância ao senhor sobre sua pergunta inicial: '{pergunta}'. Não invente fatos antigos, use estritamente as informações fornecidas acima sem asteriscos ou markdown."
                })
        else:
            # 3. Executa cada ferramenta requisitada pelo modelo
            mensagens.append(msg)
            for call in tool_calls:
                func = call.get("function", {})
                nome_fn = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}

                if nome_fn == "buscar_noticias_hoje":
                    eh_noticia = True

                log.info(f"[MCP] Modelo solicitou ferramenta: {nome_fn}({args})")
                resultado_exec = await executar_ferramenta_local(nome_fn, args)

                mensagens.append({
                    "role": "tool",
                    "content": str(resultado_exec),
                })

            if eh_noticia:
                mensagens.append({
                    "role": "user",
                    "content": PROMPT_BRIEFING_EXECUTIVO
                })

        # 4. Segunda chamada para sintetizar a resposta final em voz
        resp_final = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=modelo,
                messages=mensagens
            )
        )
        resposta_texto = resp_final.get("message", {}).get("content", "").strip()
        if resposta_texto:
            return resposta_texto

    except Exception as e:
        log.error(f"[MCP] Erro no fluxo MCP: {e}")
        # Fallback de emergência: busca simples direta
        try:
            dados_web = await buscar_web(pergunta)
            return f"Senhor, obtive as seguintes informações da rede:\n{dados_web}"
        except Exception:
            pass

    return "Senhor, encontrei dificuldades ao consultar as ferramentas online no momento."
