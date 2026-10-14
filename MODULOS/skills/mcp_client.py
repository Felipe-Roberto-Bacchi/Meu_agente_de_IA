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
from typing import Any
from MODULOS.system.logger import log
from MODULOS.brain.selector import selector as brain_selector

MCP_CONFIG_FILE = "DADOS/mcp_servers.json"

# ──────────────────────────────────────────────────────────
#  FERRAMENTAS NATIVAS DE FALLBACK (OUT-OF-THE-BOX)
# ──────────────────────────────────────────────────────────

async def buscar_web(termo: str, max_resultados: int = 5) -> str:
    """Busca informações na web usando DuckDuckGo com múltiplos fallbacks."""
    termo = termo.strip()
    log.info(f"[MCP/WEB] Executando busca por: '{termo}'")

    # 1. Tenta biblioteca oficial duckduckgo_search se instalada
    try:
        from duckduckgo_search import DDGS
        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(termo, max_results=max_resultados):
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
            resp = await client.get(f"https://html.duckduckgo.com/html/?q={httpx.URL(termo)}", headers=headers)
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
            url_wiki = f"https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch={httpx.URL(termo)}&utf8=&format=json"
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
    if nome == "buscar_web":
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

    system_prompt = (
        "Você é o assistente Jarvis com acesso a ferramentas em tempo real via internet e protocolo MCP.\n"
        "Quando o usuário perguntar sobre fatos recentes, notícias, previsão do tempo ou links, "
        "utilize as ferramentas disponíveis para obter dados atualizados.\n"
        "Ao receber o resultado das ferramentas, formule uma resposta clara, natural, cortês e direta ao ponto "
        "em português para ser falada pela sua voz."
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
            eh_clima = any(k in pergunta.lower() for k in termos_clima)
            
            if eh_clima:
                cidade = pergunta.lower()
                for c in ["qual a", "previsão do tempo em", "tempo em", "clima em", "temperatura em", "como está o", "por favor"]:
                    cidade = cidade.replace(c, "")
                resultado_ferramenta = await obter_previsao_tempo(cidade.strip())
            else:
                resultado_ferramenta = await buscar_web(pergunta)

            mensagens.append({"role": "assistant", "content": "Consultando a rede mundial de computadores..."})
            mensagens.append({
                "role": "user",
                "content": f"Com base nestes dados obtidos em tempo real:\n\n{resultado_ferramenta}\n\nResponda com elegância ao senhor sobre sua pergunta inicial: '{pergunta}'"
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

                log.info(f"[MCP] Modelo solicitou ferramenta: {nome_fn}({args})")
                resultado_exec = await executar_ferramenta_local(nome_fn, args)

                mensagens.append({
                    "role": "tool",
                    "content": str(resultado_exec),
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
