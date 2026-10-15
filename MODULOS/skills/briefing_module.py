"""
briefing_module.py
──────────────────
Motor do Briefing Matinal Coreografado com Cards Visuais e Imagens para o Jarvis.
Executa a telemetria matinal, coleta clima, agenda/lembretes, cotações de mercado e
notícias reais multi-fontes com imagens, coordenando a fala do TTS com a exibição
e movimentação de cards holográficos na interface HUD.
"""

import os
import json
import asyncio
import re
import urllib.parse
import xml.etree.ElementTree as ET
import httpx
from datetime import datetime

from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import atualizar_jarvis, enviar_evento_interface
from MODULOS.voice import voice_manager
from MODULOS.skills import reminders_module

BRIEFING_EM_ANDAMENTO = False
ULTIMO_BRIEFING_CARDS: list[dict] = []

# Carrega cache do último briefing se existir
try:
    if os.path.exists("DADOS/ultimo_briefing.json"):
        with open("DADOS/ultimo_briefing.json", "r", encoding="utf-8") as _f_init:
            _cards_init = json.load(_f_init)
            if isinstance(_cards_init, list):
                ULTIMO_BRIEFING_CARDS = _cards_init
except Exception:
    pass

def obter_ultimo_briefing() -> list[dict]:
    """Retorna os cards do último briefing executado, carregando do cache se necessário."""
    global ULTIMO_BRIEFING_CARDS
    if ULTIMO_BRIEFING_CARDS:
        return ULTIMO_BRIEFING_CARDS
    caminho = "DADOS/ultimo_briefing.json"
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    ULTIMO_BRIEFING_CARDS = dados
                    return ULTIMO_BRIEFING_CARDS
        except Exception as e:
            log.warning(f"[BRIEFING] Erro ao carregar DADOS/ultimo_briefing.json: {e}")
    return []

IMAGENS_FALLBACK = {
    "mundo": "https://images.unsplash.com/photo-1526778548025-fa2f459cd5c1?w=800&q=80",
    "economia": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
    "tecnologia": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "brasil": "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?w=800&q=80"
}

def carregar_cidade_config() -> str:
    caminho = "DADOS/news_config.json"
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados.get("cidade", "Passo Fundo")
        except Exception:
            pass
    return "Passo Fundo"

# ──────────────────────────────────────────────────────────
# 1. CARD DE CLIMA & METEOROLOGIA
# ──────────────────────────────────────────────────────────

async def obter_card_clima(cidade: str = None) -> dict:
    if not cidade:
        cidade = carregar_cidade_config()

    cidade_url = urllib.parse.quote_plus(cidade)
    url = f"https://wttr.in/{cidade_url}?format=j1"
    
    temp = "22"
    sensacao = "22"
    min_t = "16"
    max_t = "26"
    umidade = "65"
    vento = "12"
    condicao = "Tempo estável"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        async with httpx.AsyncClient(headers=headers, timeout=4.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                atual = data.get("current_condition", [{}])[0]
                temp = atual.get("temp_C", temp)
                sensacao = atual.get("FeelsLikeC", temp)
                umidade = atual.get("humidity", umidade)
                vento = atual.get("windspeedKmph", vento)
                
                # Descrição em português
                if "lang_pt" in atual and atual["lang_pt"]:
                    condicao = atual["lang_pt"][0].get("value", condicao)
                elif "weatherDesc" in atual and atual["weatherDesc"]:
                    condicao = atual["weatherDesc"][0].get("value", condicao)

                weather_days = data.get("weather", [])
                if weather_days:
                    min_t = weather_days[0].get("mintempC", min_t)
                    max_t = weather_days[0].get("maxtempC", max_t)
    except Exception as e:
        log.warning(f"[BRIEFING] Erro ao obter dados do clima: {e}")

    fala = (
        f"Em {cidade}, a temperatura atual é de {temp} graus com sensação térmica de {sensacao} graus. "
        f"A previsão para hoje indica mínima de {min_t} e máxima de {max_t} graus, "
        f"com umidade do ar em {umidade} por cento e ventos de {vento} quilômetros por hora. Condições de {condicao}."
    )

    return {
        "id": "card_clima",
        "tipo": "clima",
        "categoria": "METEOROLOGIA & SENSORES",
        "titulo": f"Previsão do Tempo // {cidade}",
        "cidade": cidade,
        "temp_atual": f"{temp}°C",
        "sensacao": f"{sensacao}°C",
        "min_max": f"Mín {min_t}°C / Máx {max_t}°C",
        "umidade": f"{umidade}%",
        "vento": f"{vento} km/h",
        "condicao": condicao,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 2. CARD DE AGENDA & LEMBRETES
# ──────────────────────────────────────────────────────────

async def obter_card_agenda() -> dict:
    pendentes = reminders_module.listar_lembretes_pendentes()
    itens = []

    # 1. Integração com eventos da agenda do Google Workspace
    try:
        from MODULOS.skills import google_mcp_module
        eventos_gcal = google_mcp_module.listar_eventos_google_calendar(max_results=4)
        for ev in eventos_gcal:
            itens.append({
                "id": f"gcal_{ev.get('id')}",
                "texto": f"📅 {ev.get('titulo')}",
                "horario": ev.get("horario") or "--:--",
                "origem": "google_calendar"
            })
    except Exception as e:
        log.warning(f"[BRIEFING] Erro ao integrar Google Calendar na agenda: {e}")

    # 2. Lembretes e tarefas locais
    for p in pendentes[:4]:
        itens.append({
            "id": p.get("id"),
            "texto": p.get("texto"),
            "horario": p.get("horario") or "--:--",
            "origem": "local"
        })

    itens = itens[:5]

    if itens:
        descricoes = []
        for it in itens:
            if it["horario"] and it["horario"] != "--:--":
                descricoes.append(f"{it['texto']} às {it['horario']}")
            else:
                descricoes.append(f"{it['texto']}")
        
        qtd = len(itens)
        if qtd == 1:
            fala = f"Na sua agenda de hoje, o senhor possui 1 compromisso registrado: {descricoes[0]}."
        else:
            fala = f"Na sua agenda de hoje, o senhor possui {qtd} compromissos registrados: " + "; ".join(descricoes) + "."
    else:
        fala = "Sua agenda está livre no momento, senhor. Não constam lembretes ou compromissos pendentes registrados para hoje."

    return {
        "id": "card_agenda",
        "tipo": "agenda",
        "categoria": "AGENDA & COMPROMISSOS",
        "titulo": "Lembretes & Tarefas do Dia",
        "itens": itens,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 3. CARD DE MERCADO FINANCEIRO & COTAÇÕES
# ──────────────────────────────────────────────────────────

async def obter_card_mercado() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    
    dolar_val, dolar_pct = "5.06", 0.15
    euro_val, euro_pct = "5.67", 0.41
    btc_val, btc_pct = "81050", -0.76
    ibov_pts, ibov_pct = "206500", -0.18
    sp_pts, sp_pct = "5860", 0.25

    try:
        async with httpx.AsyncClient(headers=headers, timeout=3.0) as client:
            res_cambio, res_ibov, res_sp = await asyncio.gather(
                client.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval=1d&range=1d"),
                client.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=1d"),
                return_exceptions=True
            )

            if isinstance(res_cambio, httpx.Response) and res_cambio.status_code == 200:
                dados = res_cambio.json()
                if "USDBRL" in dados:
                    dolar_val = f"{float(dados['USDBRL']['bid']):.2f}"
                    dolar_pct = float(dados['USDBRL']['pctChange'])
                if "EURBRL" in dados:
                    euro_val = f"{float(dados['EURBRL']['bid']):.2f}"
                    euro_pct = float(dados['EURBRL']['pctChange'])
                if "BTCUSD" in dados:
                    btc_val = f"{float(dados['BTCUSD']['bid']):,.0f}"
                    btc_pct = float(dados['BTCUSD']['pctChange'])

            if isinstance(res_ibov, httpx.Response) and res_ibov.status_code == 200:
                try:
                    meta = res_ibov.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    p = meta.get("regularMarketPrice")
                    pr = meta.get("chartPreviousClose")
                    if p and pr:
                        ibov_pts = f"{p:,.0f}"
                        ibov_pct = ((p - pr) / pr) * 100
                except Exception:
                    pass

            if isinstance(res_sp, httpx.Response) and res_sp.status_code == 200:
                try:
                    meta = res_sp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    p = meta.get("regularMarketPrice")
                    pr = meta.get("chartPreviousClose")
                    if p and pr:
                        sp_pts = f"{p:,.0f}"
                        sp_pct = ((p - pr) / pr) * 100
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"[BRIEFING] Erro ao obter dados do mercado financeiro: {e}")

    cotacoes = [
        {"nome": "Dólar Comercial", "simbolo": "USD/BRL", "valor": f"R$ {dolar_val}", "var": f"{dolar_pct:+.2f}%", "alta": dolar_pct >= 0},
        {"nome": "Euro Comercial", "simbolo": "EUR/BRL", "valor": f"R$ {euro_val}", "var": f"{euro_pct:+.2f}%", "alta": euro_pct >= 0},
        {"nome": "Bitcoin", "simbolo": "BTC/USD", "valor": f"US$ {btc_val}", "var": f"{btc_pct:+.2f}%", "alta": btc_pct >= 0},
        {"nome": "Ibovespa (B3)", "simbolo": "IBOV", "valor": f"{ibov_pts} pts", "var": f"{ibov_pct:+.2f}%", "alta": ibov_pct >= 0},
        {"nome": "S&P 500 (Wall St)", "simbolo": "S&P 500", "valor": f"{sp_pts} pts", "var": f"{sp_pct:+.2f}%", "alta": sp_pct >= 0}
    ]

    tendencia_dolar = "alta" if dolar_pct >= 0 else "queda"
    tendencia_ibov = "alta" if ibov_pct >= 0 else "queda"

    fala = (
        f"No mercado financeiro hoje, o dólar comercial opera em {tendencia_dolar} cotado a {dolar_val.replace('.', ',')} reais, "
        f"enquanto o euro está cotado a {euro_val.replace('.', ',')} reais. O bitcoin é negociado na faixa de {btc_val} dólares. "
        f"Na renda variável, o Ibovespa opera aos {ibov_pts} pontos e o índice americano S&P 500 aos {sp_pts} pontos."
    )

    return {
        "id": "card_mercado",
        "tipo": "mercado",
        "categoria": "MERCADO FINANCEIRO",
        "titulo": "Indicadores & Cotações Globais",
        "cotacoes": cotacoes,
        "fala": fala
    }

# ──────────────────────────────────────────────────────────
# 4. CARDS DE NOTÍCIAS ABRANGENTES COM IMAGEM REAL & NARRATIVA FLUIDA
# ──────────────────────────────────────────────────────────

def _imagem_eh_valida(url: str) -> bool:
    """Valida se a URL é de uma imagem real e não logos, favicons ou placeholders do Google News."""
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower().strip()
    termos_invalidos = [
        'googleusercontent.com', 'google.com', 'gstatic.com',
        'logo', 'favicon', 'icon', 'avatar', '1x1', 'pixel'
    ]
    if any(termo in url_lower for termo in termos_invalidos):
        return False
    return url_lower.startswith('http://') or url_lower.startswith('https://')

def _limpar_titulo_noticia(titulo: str) -> str:
    t = re.sub(r'\s+-\s+[^-]+$', '', titulo.strip())
    t = re.sub(r'\s*\|\s*[^|]+$', '', t.strip())
    return t.strip()

def _extrair_fonte(titulo: str, padrao: str = "Agência de Notícias") -> str:
    partes = titulo.strip().split(" - ")
    if len(partes) > 1 and len(partes[-1]) < 30:
        return partes[-1].strip()
    partes_pipe = titulo.strip().split(" | ")
    if len(partes_pipe) > 1 and len(partes_pipe[-1]) < 30:
        return partes_pipe[-1].strip()
    return padrao

def _limpar_html_resumo(texto: str) -> str:
    """Remove tags HTML, scripts, estilos e decodifica entidades para um resumo limpo de 2 linhas."""
    if not texto:
        return ""
    import html
    sem_scripts = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', texto, flags=re.DOTALL | re.IGNORECASE)
    sem_tags = re.sub(r'<[^>]+>', ' ', sem_scripts)
    texto_decod = html.unescape(sem_tags)
    limpo = re.sub(r'\s+', ' ', texto_decod).strip()
    limpo = re.sub(r'(Leia mais|Saiba mais|Confira|Veja mais).*$', '', limpo, flags=re.IGNORECASE).strip()
    return limpo

def _extrair_imagem_xml(item, desc_raw: str = "", content_raw: str = "") -> str | None:
    """Extrai a URL da foto real no XML buscando em media:content, media:thumbnail, enclosure e img src."""
    # 1. media:content (com e sem namespace)
    for tag in ('{http://search.yahoo.com/mrss/}content', 'media:content', 'content'):
        for el in item.findall(tag):
            u = el.attrib.get('url')
            if u and _imagem_eh_valida(u):
                return u

    # 2. media:thumbnail
    for tag in ('{http://search.yahoo.com/mrss/}thumbnail', 'media:thumbnail', 'thumbnail'):
        for el in item.findall(tag):
            u = el.attrib.get('url')
            if u and _imagem_eh_valida(u):
                return u

    # 3. enclosure
    for el in item.findall('enclosure'):
        u = el.attrib.get('url')
        if u and _imagem_eh_valida(u):
            return u

    # 4. tag <img> dentro do description ou content
    texto_html = f"{desc_raw} {content_raw}"
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', texto_html, re.IGNORECASE)
    for u in imgs:
        if _imagem_eh_valida(u):
            return u

    return None

async def _extrair_artigo_completo(client: httpx.AsyncClient, url: str) -> tuple[str | None, str]:
    """
    Baixa o HTML do link_artigo (timeout 3.5s) usando BeautifulSoup:
    - Extrai a og:image real da página (se disponível e válida).
    - Extrai todos os parágrafos <p> reais do corpo da matéria (filtrando parágrafos
      com mais de 45 caracteres e ignorando avisos de cookies/rodapé/redes sociais),
      juntando de 6 a 10 parágrafos em um conteudo_completo (separados por \n\n).
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None, ""

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
        resp = await client.get(url, headers=headers, timeout=3.5, follow_redirects=True)
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Extração de og:image real
            og_img = None
            meta_og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if meta_og and meta_og.get("content"):
                c = meta_og.get("content").strip()
                if _imagem_eh_valida(c):
                    og_img = c

            # 2. Remoção de ruídos de navegação, rodapé e anúncios
            for tag in soup(["script", "style", "nav", "footer", "aside", "noscript", "header", "form"]):
                tag.decompose()

            # 3. Extração dos parágrafos do corpo da matéria
            termos_ignorar = [
                "cookie", "privacidade", "termos de uso", "direitos reservados",
                "todos os direitos", "inscreva-se", "newsletter", "compartilhe",
                "whatsapp", "telegram", "siga o", "redes sociais", "leia também",
                "veja também", "foto:", "crédito:", "publicidade", "assine"
            ]

            paragrafos = []
            for p in soup.find_all("p"):
                texto_p = p.get_text(separator=" ", strip=True)
                texto_p = re.sub(r'\s+', ' ', texto_p).strip()
                if len(texto_p) > 45:
                    p_lower = texto_p.lower()
                    if not any(termo in p_lower for termo in termos_ignorar):
                        paragrafos.append(texto_p)
                        if len(paragrafos) >= 10:
                            break

            conteudo_completo = "\n\n".join(paragrafos)
            return og_img, conteudo_completo
    except Exception as e:
        log.debug(f"[BRIEFING] Erro ao extrair artigo completo de {url}: {e}")

    return None, ""

async def _buscar_imagem_pagina(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=2.5, follow_redirects=True)
        if resp.status_code == 200:
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match:
                img = match.group(1).strip()
                if _imagem_eh_valida(img):
                    return img
            match2 = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text, re.IGNORECASE)
            if match2:
                img = match2.group(1).strip()
                if _imagem_eh_valida(img):
                    return img
    except Exception:
        pass
    return None

async def _buscar_imagem_fallback(client: httpx.AsyncClient, titulo: str, link: str = None) -> str | None:
    """Busca imagem alternativa no og:image da página da matéria ou via DuckDuckGo Imagens."""
    if link:
        img_og = await _buscar_imagem_pagina(client, link)
        if img_og and _imagem_eh_valida(img_og):
            return img_og

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(keywords=titulo, region="br-pt", max_results=2))
            for r in results:
                img_u = r.get("image")
                if img_u and _imagem_eh_valida(img_u):
                    return img_u
    except Exception as e:
        log.debug(f"[BRIEFING] Erro no fallback de imagem DDGS: {e}")
    return None

async def _obter_noticia_categoria(client: httpx.AsyncClient, cat: str, feeds_url: list[str], rotulo: str, fonte_padrao: str, prefixo_fala: str) -> dict:
    fallback_img = IMAGENS_FALLBACK.get(cat, IMAGENS_FALLBACK["mundo"])

    for feed_url in feeds_url:
        try:
            resp = await client.get(feed_url, timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                items = root.findall('.//item')
                if items:
                    item = items[0]
                    tit_raw = item.find('title').text if item.find('title') is not None else ""
                    desc_raw = item.find('description').text if item.find('description') is not None else ""
                    link_artigo = item.find('link').text if item.find('link') is not None else ""

                    tit_limpo = _limpar_titulo_noticia(tit_raw)
                    fonte = _extrair_fonte(tit_raw, fonte_padrao)
                    resumo_rss = _limpar_html_resumo(desc_raw)

                    # 1. Extração profunda do artigo completo e imagem da página original
                    og_img_artigo, conteudo_completo = await _extrair_artigo_completo(client, link_artigo)

                    # 2. Imagem real: XML > og:image do artigo > busca DuckDuckGo > fallback temático
                    img = _extrair_imagem_xml(item, desc_raw)
                    if not img or not _imagem_eh_valida(img):
                        if og_img_artigo and _imagem_eh_valida(og_img_artigo):
                            img = og_img_artigo
                        else:
                            img = await _buscar_imagem_fallback(client, tit_limpo, link_artigo)

                    if not img or not _imagem_eh_valida(img):
                        img = fallback_img

                    # 3. Monta resumo completo e informativo de 2 a 3 frases (~280 a 350 caracteres)
                    base_texto = conteudo_completo if (conteudo_completo and len(conteudo_completo) > len(resumo_rss)) else resumo_rss
                    if not base_texto or len(base_texto) < 30:
                        base_texto = f"{tit_limpo}. As movimentações e apurações sobre o tema continuam em andamento em tempo real."

                    frases = [f.strip() for f in re.split(r'(?<=[.!?])\s+', base_texto) if len(f.strip()) > 15]
                    resumo_card = " ".join(frases[:3]).strip()
                    if len(resumo_card) > 360:
                        resumo_card = resumo_card[:350].rsplit(' ', 1)[0] + "..."
                    elif len(resumo_card) < 200 and len(frases) > 3:
                        resumo_card = " ".join(frases[:4]).strip()
                        if len(resumo_card) > 360:
                            resumo_card = resumo_card[:350].rsplit(' ', 1)[0] + "..."

                    # Se conteudo_completo não foi extraído da URL, garante ao menos o resumo
                    if not conteudo_completo:
                        conteudo_completo = resumo_card

                    # 4. Narrativa de fala jornalística fluida (2 a 3 frases completas, até ~320 caracteres)
                    frases_fala = []
                    for f in frases:
                        # Evita repetir o título na frase informativa
                        if f.lower() not in tit_limpo.lower() and len(f) > 20:
                            frases_fala.append(f)
                        if len(frases_fala) >= 2:
                            break

                    if frases_fala:
                        fala_base = f"{prefixo_fala}, {tit_limpo}. " + " ".join(frases_fala)
                    else:
                        fala_base = f"{prefixo_fala}, {tit_limpo}. As movimentações recentes trazem desdobramentos estratégicos que seguem sob acompanhamento contínuo."

                    if len(fala_base) > 330:
                        fala = fala_base[:320].rsplit(' ', 1)[0]
                        if not fala.endswith(('.', '!', '?')):
                            fala += '.'
                    else:
                        fala = fala_base
                        if not fala.endswith(('.', '!', '?')):
                            fala += '.'

                    return {
                        "id": f"card_noticia_{cat}",
                        "tipo": "noticia",
                        "categoria": rotulo,
                        "titulo": tit_limpo,
                        "resumo": resumo_card,
                        "conteudo_completo": conteudo_completo,
                        "link": link_artigo,
                        "fonte": fonte,
                        "imagem": img,
                        "fala": fala
                    }
        except Exception as e_feed:
            log.debug(f"[BRIEFING] Tentando próximo feed da categoria {cat}: {e_feed}")

    # Fallback estático de emergência caso nenhum feed responda
    return {
        "id": f"card_noticia_{cat}",
        "tipo": "noticia",
        "categoria": rotulo,
        "titulo": f"Atualizações em {cat.title()}",
        "resumo": "Sistemas de inteligência continuam monitorando as principais movimentações em tempo real com apuração estratégica dos fatos.",
        "conteudo_completo": "Os canais oficiais e agências internacionais continuam transmitindo atualizações em tempo real. Os sistemas neurais do Jarvis mantêm vigilância ativa sobre os desdobramentos deste setor.",
        "link": feeds_url[0] if feeds_url else "",
        "fonte": fonte_padrao,
        "imagem": fallback_img,
        "fala": f"{prefixo_fala}, os sistemas continuam monitorando as movimentações estratégicas em {cat.title()} para o senhor."
    }

async def obter_cards_noticias() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAssistant/1.0"}
    
    # Feeds diretos de portais que entregam imagens reais no XML e páginas abertas
    feeds_config = [
        (
            "mundo",
            ["https://feeds.bbci.co.uk/portuguese/rss.xml", "https://g1.globo.com/rss/g1/mundo/"],
            "RADAR // INTERNACIONAL & EUA",
            "BBC News Brasil",
            "No cenário global"
        ),
        (
            "economia",
            ["https://g1.globo.com/rss/g1/economia/", "https://www.infomoney.com.br/feed/"],
            "RADAR // ECONOMIA & MERCADOS",
            "G1 Economia",
            "No front econômico"
        ),
        (
            "tecnologia",
            ["https://g1.globo.com/rss/g1/tecnologia/", "https://rss.tecmundo.com.br/feed"],
            "RADAR // TECNOLOGIA & IA",
            "G1 Tecnologia",
            "No setor tecnológico"
        ),
        (
            "brasil",
            ["https://g1.globo.com/rss/g1/politica/", "https://feeds.bbci.co.uk/portuguese/rss.xml"],
            "RADAR // POLÍTICA & BRASIL",
            "G1 Política",
            "No panorama nacional"
        )
    ]

    async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
        tarefas = [
            _obter_noticia_categoria(client, cat, urls, rotulo, fonte, pref)
            for cat, urls, rotulo, fonte, pref in feeds_config
        ]
        cards = await asyncio.gather(*tarefas)
        return list(cards)

# ──────────────────────────────────────────────────────────
# 5. COREOGRAFIA SINCRONIZADA DO BRIEFING
# ──────────────────────────────────────────────────────────

async def executar_briefing_coreografado():
    """
    Executa a sequência completa de Briefing Matinal:
    Fase 1: Radar / Telemetria inicial com card central e fala introdutória.
    Fase 2: Desfile de cards (Clima, Agenda, Mercado, Notícias), sincronizando
            a fala de cada card com o foco central e posterior ancoragem no dock inferior.
    Fase 3: Encerramento elegante com encerramento de todos os cards no dock.
    """
    global BRIEFING_EM_ANDAMENTO
    if BRIEFING_EM_ANDAMENTO:
        log.warning("[BRIEFING] Briefing já está em andamento. Ignorando nova requisição.")
        return

    BRIEFING_EM_ANDAMENTO = True
    log.info("[BRIEFING] Iniciando coreografia do Briefing Matinal holográfico...")

    try:
        # Notifica início da coleta de dados
        await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.2, texto="Compilando telemetria matinal...", padrao="tarefa")

        # Coleta de todos os dados e cards em paralelo para velocidade máxima
        card_clima, card_agenda, card_mercado, cards_noticias = await asyncio.gather(
            obter_card_clima(),
            obter_card_agenda(),
            obter_card_mercado(),
            obter_cards_noticias()
        )

        cards_briefing = [card_clima, card_agenda, card_mercado] + cards_noticias
        global ULTIMO_BRIEFING_CARDS
        ULTIMO_BRIEFING_CARDS = list(cards_briefing)

        os.makedirs("DADOS", exist_ok=True)
        try:
            with open("DADOS/ultimo_briefing.json", "w", encoding="utf-8") as _f_save:
                json.dump(ULTIMO_BRIEFING_CARDS, _f_save, ensure_ascii=False, indent=2)
            log.info("[BRIEFING] Cards salvos com sucesso em DADOS/ultimo_briefing.json")
        except Exception as _e_save:
            log.warning(f"[BRIEFING] Erro ao salvar DADOS/ultimo_briefing.json: {_e_save}")

        # Monta resumo textual estruturado de todos os 7 cards e salva IMEDIATAMENTE na memória
        data_hora_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
        linhas_resumo = [
            f"[BRIEFING MATINAL CONSOLIDADO - {data_hora_str}]",
            f"1. CLIMA ({card_clima.get('cidade')}): {card_clima.get('fala')}",
            f"2. AGENDA: {card_agenda.get('fala')}",
            f"3. MERCADO FINANCEIRO: {card_mercado.get('fala')}"
        ]
        for idx, nc in enumerate(cards_noticias, start=4):
            cat_label = nc.get('categoria', 'NOTÍCIA').replace('RADAR // ', '')
            link_txt = f" | Link: {nc.get('link')}" if nc.get('link') else ""
            linhas_resumo.append(
                f"{idx}. {cat_label}: {nc.get('titulo')}{link_txt}\n"
                f"   Fonte: {nc.get('fonte')}\n"
                f"   Resumo: {nc.get('resumo')}\n"
                f"   Artigo: {nc.get('conteudo_completo', '')[:700]}"
            )

        resumo_completo_briefing = "\n\n".join(linhas_resumo)

        try:
            from MODULOS.memory import memory_short, memory_long
            memory_short.adicionar_mensagem("assistant", resumo_completo_briefing)
            memory_long.registrar_conversa_global("assistant", resumo_completo_briefing)
            log.info("[BRIEFING] Resumo consolidado do briefing registrado com sucesso no memory_short e memory_long!")
        except Exception as e_mem:
            log.error(f"[BRIEFING] Erro ao gravar briefing na memória: {e_mem}")

        etapas_radar = ["CLIMA", "AGENDA", "MERCADO", "MUNDO & EUA", "ECONOMIA", "TECNOLOGIA", "BRASIL"]

        # ── FASE 1: RADAR / TELEMETRIA INICIAL ──
        await enviar_evento_interface({
            "type": "briefing_start",
            "etapas": etapas_radar,
            "hora": datetime.now().strftime("%H:%M")
        })

        fala_intro = "Bom dia, senhor. Iniciando a telemetria matinal e consolidando os dados essenciais do seu dia."
        await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=fala_intro, padrao="falando")
        await voice_manager.falar("Jarvis", fala_intro, prioridade=1)

        await asyncio.sleep(0.3)
        while voice_manager.STATUS_FALANDO:
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.5)

        # ── FASE 2: DESFILE DE CARDS EM FOCO CENTRAL ──
        briefing_abortado = False
        for idx, card in enumerate(cards_briefing):
            if getattr(voice_manager, "ABORTAR_FALA", False):
                log.info("[BRIEFING] Briefing interrompido pelo usuário via ABORTAR_FALA.")
                briefing_abortado = True
                break

            log.info(f"[BRIEFING] Exibindo card {idx + 1}/{len(cards_briefing)}: {card.get('titulo')}")

            # 1. Envia evento para a interface focar esse card no centro da esfera
            await enviar_evento_interface({
                "type": "briefing_card_focus",
                "card": card,
                "indice": idx,
                "total": len(cards_briefing)
            })

            # 2. Fala o conteúdo específico desse card
            fala_card = card.get("fala", "")
            if fala_card:
                await atualizar_jarvis(cor_hex="#00e5ff", intensidade=0.8, texto=card.get("titulo", ""), padrao="falando")
                await voice_manager.falar("Jarvis", fala_card, prioridade=1)

                await asyncio.sleep(0.3)
                while voice_manager.STATUS_FALANDO:
                    if getattr(voice_manager, "ABORTAR_FALA", False):
                        briefing_abortado = True
                        break
                    await asyncio.sleep(0.1)

            if briefing_abortado or getattr(voice_manager, "ABORTAR_FALA", False):
                briefing_abortado = True
                break

            # Pausa de transição suave para apreciação visual do card antes do próximo
            await asyncio.sleep(0.6)

        # ── FASE 3: ENCERRAMENTO E ESTACIONAMENTO DOS CARDS ──
        await enviar_evento_interface({
            "type": "briefing_end",
            "total_cards": len(cards_briefing)
        })

        if not briefing_abortado and not getattr(voice_manager, "ABORTAR_FALA", False):
            fala_fim = "Esse é o panorama consolidado do momento, senhor. Hoje, mantenha o foco no essencial."
            await atualizar_jarvis(cor_hex="#00ffff", intensidade=0.6, texto=fala_fim, padrao="conversa")
            await voice_manager.falar("Jarvis", fala_fim, prioridade=1)

            await asyncio.sleep(0.3)
            while voice_manager.STATUS_FALANDO:
                if getattr(voice_manager, "ABORTAR_FALA", False):
                    break
                await asyncio.sleep(0.1)

        log.info("[BRIEFING] Briefing Matinal concluído/encerrado com sucesso.")

    except Exception as e:
        log.error(f"[BRIEFING] Erro durante o briefing coreografado: {e}")
        await atualizar_jarvis(cor_hex="#ff0055", intensidade=0.2, texto="Erro no briefing", padrao="alerta")
    finally:
        BRIEFING_EM_ANDAMENTO = False


async def responder_followup_briefing(pergunta: str) -> str:
    """
    Responde perguntas de aprofundamento do usuário sobre o Briefing Matinal.
    Identifica o card correspondente em ULTIMO_BRIEFING_CARDS, busca aprofundamento
    via conteúdo completo ou URL (usando obter_conteudo_url do mcp_client) e gera
    uma resposta profunda, precisa e elegante com o LLM.
    """
    global ULTIMO_BRIEFING_CARDS
    from MODULOS.skills import mcp_client
    from MODULOS.brain.selector import selector as brain_selector
    from MODULOS.memory import memory_short, memory_long
    import ollama

    pergunta_lower = pergunta.lower()

    # Se não temos cards gravados do briefing, recorre ao MCP/Web
    if not ULTIMO_BRIEFING_CARDS:
        log.info("[BRIEFING/FOLLOWUP] Nenhum card de briefing em cache. Delegando para WEB_MCP...")
        return await mcp_client.executar_comandos_mcp_ou_web(pergunta)

    # 1. Tenta identificar qual card o usuário está perguntando
    palavras_query = set(re.findall(r'\b\w{3,}\b', pergunta_lower))
    stopwords = {
        "jarvis", "fale", "mais", "sobre", "esse", "essa", "este", "esta", "assunto",
        "noticia", "notícia", "explique", "melhor", "detalhe", "conte", "qual",
        "quem", "como", "onde", "quando", "porque", "para", "com", "uma", "uns",
        "umas", "pelo", "pela", "pelas", "pelos", "voce", "você", "falou", "hoje",
        "governo", "disse", "bom", "dia", "favor"
    }
    termos_relevantes = [p for p in palavras_query if p not in stopwords]

    melhor_card = None
    melhor_score = 0

    for card in ULTIMO_BRIEFING_CARDS:
        card_texto = (
            f"{card.get('titulo', '')} {card.get('resumo', '')} "
            f"{card.get('categoria', '')} {card.get('tipo', '')} "
            f"{card.get('conteudo_completo', '')}"
        ).lower()

        score = 0
        for termo in termos_relevantes:
            if termo in card_texto:
                score += 2
        for termo in termos_relevantes:
            if termo in card.get('titulo', '').lower():
                score += 3

        if score > melhor_score:
            melhor_score = score
            melhor_card = card

    # Se a query menciona governo ou brasil ou economia e nenhum score bateu
    if not melhor_card or melhor_score == 0:
        if "governo" in pergunta_lower or "brasil" in pergunta_lower or "lei" in pergunta_lower:
            for card in ULTIMO_BRIEFING_CARDS:
                if card.get("id") in ("card_noticia_brasil", "card_noticia_economia"):
                    melhor_card = card
                    break

    # Se ainda não encontrou card específico, verifica lista de notícias
    noticias = [c for c in ULTIMO_BRIEFING_CARDS if c.get("tipo") == "noticia"]
    if not melhor_card and noticias:
        if any(k in pergunta_lower for k in ["quais", "todas", "qual é a notícia", "qual e a noticia", "quais as"]):
            titulos_noticias = [f"• {c.get('categoria', 'Radar')}: {c.get('titulo')}" for c in noticias]
            return (
                "Senhor, no Briefing Matinal de hoje destacamos as seguintes notícias:\n"
                + "\n".join(titulos_noticias) +
                "\n\nSobre qual destes temas o senhor gostaria que eu me aprofundasse?"
            )
        melhor_card = noticias[0]

    if not melhor_card:
        return await mcp_client.executar_comandos_mcp_ou_web(pergunta)

    # 2. Contexto do card selecionado
    titulo_card = melhor_card.get("titulo", "")
    fonte_card = melhor_card.get("fonte", "")
    link_card = melhor_card.get("link", "")
    artigo_texto = melhor_card.get("conteudo_completo") or melhor_card.get("resumo") or ""

    # Se o texto for curto e houver link original, faz fetch da URL para profundidade total
    if len(artigo_texto) < 250 and link_card:
        try:
            conteudo_extra = await mcp_client.obter_conteudo_url(link_card)
            if conteudo_extra and len(conteudo_extra) > 100:
                artigo_texto = conteudo_extra
        except Exception as e_fetch:
            log.debug(f"[BRIEFING/FOLLOWUP] Erro no fetch da URL {link_card}: {e_fetch}")

    # 3. Síntese neural profunda com LLM
    modelo, _ = brain_selector.escolher_melhor_modelo("CONVERSA")
    prompt_sistema = (
        "Você é o assistente Jarvis.\n"
        "O senhor solicitou um aprofundamento e detalhes adicionais sobre o seguinte tópico do Briefing Matinal:\n"
        f"Assunto/Título: {titulo_card}\n"
        f"Fonte: {fonte_card}\n"
        f"Link de referência: {link_card}\n"
        f"Informações completas e parágrafos do artigo:\n{artigo_texto}\n\n"
        "Instruções:\n"
        "1. Explique detalhadamente ao senhor o que está acontecendo, os motivos, números e desdobramentos.\n"
        "2. Seja claro, objetivo, seguro e elegante em português do Brasil.\n"
        "3. Sua resposta será falada em voz alta pelo TTS: não utilize listas com asteriscos (*), emojis exagerados ou markdown complexo, mantendo parágrafos fluidos e naturais."
    )

    mensagens = [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": pergunta}
    ]

    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: ollama.chat(model=modelo, messages=mensagens)
        )
        resposta = res.get("message", {}).get("content", "").strip()
        if resposta:
            # Registra no histórico de conversa
            memory_short.adicionar_mensagem("user", pergunta)
            memory_short.adicionar_mensagem("assistant", resposta)
            memory_long.registrar_conversa_global("assistant", resposta)
            return resposta
    except Exception as e:
        log.error(f"[BRIEFING/FOLLOWUP] Erro no LLM ao responder followup: {e}")

    # Resposta de fallback
    return f"Senhor, sobre '{titulo_card}': {artigo_texto[:350]}..."
