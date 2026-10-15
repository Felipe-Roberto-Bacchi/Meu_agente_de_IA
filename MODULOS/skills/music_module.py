"""
music_module.py
───────────────
Media Hub Unificado do Jarvis: Suporte a YouTube Music/Audio Streaming,
Músicas Locais Offline do Computador e Controle Nativo do Spotify.
Gerencia estado de reprodução, sincronização via WebSocket para o HUD e comandos de voz.
"""

import os
import sys
import json
import random
import asyncio
import urllib.parse
import webbrowser
import ctypes
from datetime import datetime

import yt_dlp
from MODULOS.system.logger import log
from MODULOS.system.comunicacao_visual import enviar_evento_interface

# Teclas virtuais de mídia do Windows para controle de hardware / Spotify Desktop
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

def simular_tecla_midia(vk_code: int):
    """Dispara tecla virtual de mídia via API Win32 User32."""
    try:
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0) # Key up
    except Exception as e:
        log.warning(f"[MUSICA] Falha ao simular tecla de mídia Win32 ({hex(vk_code)}): {e}")

# Estado Global do Player sincronizado com o Mini-Player do HUD
ESTADO_PLAYER = {
    "fonte": "youtube",        # "youtube" | "local" | "spotify"
    "tocando": False,
    "titulo": "Nenhuma mídia ativa",
    "artista": "Jarvis Media Hub",
    "capa": "",
    "duracao": "0:00",
    "duracao_segundos": 0,
    "progresso_segundos": 0,
    "stream_url": "",
    "webpage_url": "",
    "volume": 80,
    "caminho": ""
}

PLAYLIST_LOCAL: list[str] = []
INDICE_PLAYLIST_LOCAL = 0

def formatar_segundos(segundos: int | float | None) -> str:
    if not segundos or segundos <= 0:
        return "0:00"
    s = int(segundos)
    m = s // 60
    s_rest = s % 60
    return f"{m}:{s_rest:02d}"

# ──────────────────────────────────────────────────────────
# 1. YOUTUBE MUSIC & AUDIO STREAMING (yt_dlp)
# ──────────────────────────────────────────────────────────

async def tocar_youtube(termo: str) -> dict:
    """
    Busca termo no YouTube via yt_dlp, extrai stream direto de áudio e metadados,
    atualiza o ESTADO_PLAYER e notifica o HUD.
    """
    global ESTADO_PLAYER
    log.info(f"[MUSICA/YOUTUBE] Buscando áudio para: '{termo}'")

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'socket_timeout': 12
    }

    def _extrair():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch1:{termo}", download=False)

    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _extrair)

        if not info:
            raise ValueError("Nenhum resultado retornado pelo YouTube.")

        if 'entries' in info and info['entries']:
            entry = info['entries'][0]
        else:
            entry = info

        titulo = entry.get('title', termo)
        artista = entry.get('uploader') or entry.get('channel') or "YouTube"
        capa = entry.get('thumbnail') or "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80"
        duracao_segundos = entry.get('duration', 0)
        duracao_str = formatar_segundos(duracao_segundos)
        stream_url = entry.get('url', '')
        webpage_url = entry.get('webpage_url', f"https://www.youtube.com/watch?v={entry.get('id', '')}")

        ESTADO_PLAYER.update({
            "fonte": "youtube",
            "tocando": True,
            "titulo": titulo,
            "artista": artista,
            "capa": capa,
            "duracao": duracao_str,
            "duracao_segundos": duracao_segundos,
            "progresso_segundos": 0,
            "stream_url": stream_url,
            "webpage_url": webpage_url,
            "caminho": ""
        })

        await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
        log.info(f"[MUSICA/YOUTUBE] Faixa carregada: '{titulo}' ({duracao_str})")
        return ESTADO_PLAYER

    except Exception as e:
        log.error(f"[MUSICA/YOUTUBE] Erro ao buscar áudio do YouTube para '{termo}': {e}")
        return {"erro": str(e)}

# ──────────────────────────────────────────────────────────
# 2. MÚSICAS LOCAIS OFFLINE DO COMPUTADOR
# ──────────────────────────────────────────────────────────

PASTA_MUSICAS_LOCAIS = os.path.abspath("MUSICAS_LOCAIS")
os.makedirs(PASTA_MUSICAS_LOCAIS, exist_ok=True)
PEDIDO_MUSICA_PENDENTE: str | None = None

def obter_pastas_musica() -> list[str]:
    """Obtém pastas para varredura de arquivos locais."""
    pastas = [
        PASTA_MUSICAS_LOCAIS,
        os.path.expanduser("~/Music"),
        "C:\\Users\\felip\\Music"
    ]
    cfg_path = "DADOS/music_config.json"
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                custom = cfg.get("pastas_locais", [])
                for p in custom:
                    if p and os.path.exists(p) and p not in pastas:
                        pastas.append(p)
        except Exception:
            pass
    return [p for p in pastas if os.path.exists(p)]

def escanear_arquivos_locais() -> list[str]:
    """Varre pastas em busca de extensões de áudio suportadas."""
    extensoes = ('.mp3', '.wav', '.flac', '.ogg', '.m4a', '.opus', '.webm')
    arquivos = []
    pastas = obter_pastas_musica()
    for pasta in pastas:
        for root, _, files in os.walk(pasta):
            for file in files:
                if file.lower().endswith(extensoes):
                    arquivos.append(os.path.join(root, file))
    return arquivos

def formatar_titulo_local(caminho: str) -> str:
    """Extrai e limpa o título do arquivo local, removendo sufixos de ID do YouTube como [lbehxlFIlpc]."""
    import re
    nome_base = os.path.splitext(os.path.basename(caminho))[0]
    nome_limpo = re.sub(r"\s*\[[a-zA-Z0-9_\-]{6,16}\]", "", nome_base).strip()
    return nome_limpo if nome_limpo else nome_base

async def tocar_local(termo: str = "") -> dict:
    """
    Toca uma música offline local do computador ou monta playlist aleatória.
    """
    global ESTADO_PLAYER, PLAYLIST_LOCAL, INDICE_PLAYLIST_LOCAL
    arquivos = escanear_arquivos_locais()

    if not arquivos:
        log.warning("[MUSICA/LOCAL] Nenhum arquivo de áudio encontrado nas pastas de música do PC.")
        return {
            "erro": "Nenhuma música offline encontrada nas pastas de música.",
            "mensagem": "Não encontrei arquivos de áudio em sua pasta Músicas, senhor."
        }

    caminho_escolhido = None
    termo_limpo = termo.strip().lower()

    if termo_limpo and termo_limpo not in ["minhas músicas", "minhas musicas", "música offline", "musica offline", "aleatório", "aleatorio", "offline"]:
        # Busca exata ou substring
        for arq in arquivos:
            nome_arq = os.path.splitext(os.path.basename(arq))[0].lower()
            if termo_limpo in nome_arq:
                caminho_escolhido = arq
                break
        
        # Se não achou por substring direta, busca por palavras-chave
        if not caminho_escolhido:
            palavras = [p for p in termo_limpo.split() if len(p) > 2]
            for arq in arquivos:
                nome_arq = os.path.splitext(os.path.basename(arq))[0].lower()
                if any(w in nome_arq for w in palavras):
                    caminho_escolhido = arq
                    break

    if not caminho_escolhido:
        # Modo shuffle da biblioteca
        PLAYLIST_LOCAL = list(arquivos)
        random.shuffle(PLAYLIST_LOCAL)
        INDICE_PLAYLIST_LOCAL = 0
        caminho_escolhido = PLAYLIST_LOCAL[0]
    else:
        PLAYLIST_LOCAL = [caminho_escolhido]
        INDICE_PLAYLIST_LOCAL = 0

    url_stream = f"/api/music/stream?path={urllib.parse.quote(caminho_escolhido)}"
    titulo_formatado = formatar_titulo_local(caminho_escolhido)

    ESTADO_PLAYER.update({
        "fonte": "local",
        "tocando": True,
        "titulo": titulo_formatado,
        "artista": "Mídia Local (PC)",
        "capa": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80",
        "duracao": "--:--",
        "duracao_segundos": 0,
        "progresso_segundos": 0,
        "stream_url": url_stream,
        "webpage_url": "",
        "caminho": caminho_escolhido
    })

    await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
    log.info(f"[MUSICA/LOCAL] Reproduzindo arquivo local: '{titulo_formatado}'")
    return ESTADO_PLAYER

# ──────────────────────────────────────────────────────────
# 3. CONTROLE NATIVO DO SPOTIFY (Desktop URI & Win32 Media Keys)
# ──────────────────────────────────────────────────────────

async def controlar_spotify(acao_ou_musica: str) -> dict:
    """
    Controla o Spotify Desktop via URI de busca e/ou teclas de mídia do Windows.
    Suporta spotipy caso credenciais existam em DADOS/spotify_config.json.
    """
    global ESTADO_PLAYER
    termo = acao_ou_musica.strip()
    termo_lower = termo.lower()

    # Verifica se há credenciais da API do Spotify
    config_spotipy = None
    if os.path.exists("DADOS/spotify_config.json"):
        try:
            with open("DADOS/spotify_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("SPOTIPY_CLIENT_ID") and cfg.get("SPOTIPY_CLIENT_SECRET"):
                    config_spotipy = cfg
        except Exception:
            pass

    if config_spotipy:
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=config_spotipy["SPOTIPY_CLIENT_ID"],
                client_secret=config_spotipy["SPOTIPY_CLIENT_SECRET"],
                redirect_uri=config_spotipy.get("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback"),
                scope="user-modify-playback-state,user-read-playback-state"
            ))
            if termo_lower in ["pause", "pausar"]:
                sp.pause_playback()
                ESTADO_PLAYER["tocando"] = False
            elif termo_lower in ["next", "proxima", "próxima"]:
                sp.next_track()
                ESTADO_PLAYER["tocando"] = True
            elif termo_lower in ["prev", "anterior"]:
                sp.previous_track()
                ESTADO_PLAYER["tocando"] = True
            elif termo:
                sp.start_playback(uris=[f"spotify:track:{termo}"])
                ESTADO_PLAYER.update({"tocando": True, "titulo": termo, "fonte": "spotify"})
            await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
            return ESTADO_PLAYER
        except Exception as e_spot:
            log.warning(f"[MUSICA/SPOTIFY] API Spotipy não respondeu ({e_spot}). Alternando para controle de Desktop...")

    # Fallback Nativo Instantâneo: Desktop URI + Teclas Win32
    if termo_lower in ["pause", "pausar", "parar"]:
        simular_tecla_midia(VK_MEDIA_PLAY_PAUSE)
        ESTADO_PLAYER["tocando"] = False
        ESTADO_PLAYER["fonte"] = "spotify"
    elif termo_lower in ["play", "continuar", "retomar", "despausar"]:
        simular_tecla_midia(VK_MEDIA_PLAY_PAUSE)
        ESTADO_PLAYER["tocando"] = True
        ESTADO_PLAYER["fonte"] = "spotify"
    elif termo_lower in ["next", "proxima", "próxima", "pular"]:
        simular_tecla_midia(VK_MEDIA_NEXT_TRACK)
        ESTADO_PLAYER["tocando"] = True
        ESTADO_PLAYER["fonte"] = "spotify"
    elif termo_lower in ["prev", "anterior", "voltar"]:
        simular_tecla_midia(VK_MEDIA_PREV_TRACK)
        ESTADO_PLAYER["tocando"] = True
        ESTADO_PLAYER["fonte"] = "spotify"
    else:
        # Abrir/buscar música no Spotify Desktop
        termo_busca = termo
        for prefix in ["tocar no spotify", "toque no spotify", "toca no spotify", "no spotify", "tocar", "toque", "toca"]:
            if termo_busca.lower().startswith(prefix):
                termo_busca = termo_busca[len(prefix):].strip()
        termo_busca = termo_busca.strip(' "\'')

        spotify_uri = f"spotify:search:{urllib.parse.quote(termo_busca)}" if termo_busca else "spotify:"
        try:
            # Abre o cliente nativo do Spotify Desktop
            os.system(f'start {spotify_uri}')
            log.info(f"[MUSICA/SPOTIFY] Abrindo URI no Spotify Desktop: {spotify_uri}")
        except Exception as e:
            webbrowser.open(spotify_uri)

        # Aguarda breve momento e dá Play caso necessário
        await asyncio.sleep(1.2)
        simular_tecla_midia(VK_MEDIA_PLAY_PAUSE)

        ESTADO_PLAYER.update({
            "fonte": "spotify",
            "tocando": True,
            "titulo": termo_busca if termo_busca else "Spotify Desktop",
            "artista": "Spotify",
            "capa": "https://images.unsplash.com/photo-1614680376593-902f749f7ffc?w=400&q=80",
            "duracao": "--:--",
            "duracao_segundos": 0,
            "progresso_segundos": 0,
            "stream_url": "", # Reproduzido pelo app do Spotify
            "webpage_url": f"https://open.spotify.com/search/{urllib.parse.quote(termo_busca)}",
            "caminho": ""
        })

    await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
    return ESTADO_PLAYER

# ──────────────────────────────────────────────────────────
# 4. CONTROLES GLOBAIS DE REPRODUÇÃO
# ──────────────────────────────────────────────────────────

async def pausar() -> dict:
    global ESTADO_PLAYER
    if ESTADO_PLAYER["fonte"] == "spotify":
        simular_tecla_midia(VK_MEDIA_PLAY_PAUSE)
    ESTADO_PLAYER["tocando"] = False
    await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
    return ESTADO_PLAYER

async def continuar() -> dict:
    global ESTADO_PLAYER
    if ESTADO_PLAYER["fonte"] == "spotify":
        simular_tecla_midia(VK_MEDIA_PLAY_PAUSE)
    ESTADO_PLAYER["tocando"] = True
    await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
    return ESTADO_PLAYER

async def proxima() -> dict:
    global ESTADO_PLAYER, PLAYLIST_LOCAL, INDICE_PLAYLIST_LOCAL
    if ESTADO_PLAYER["fonte"] == "spotify":
        simular_tecla_midia(VK_MEDIA_NEXT_TRACK)
        ESTADO_PLAYER["tocando"] = True
        await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
        return ESTADO_PLAYER
    elif ESTADO_PLAYER["fonte"] == "local" and PLAYLIST_LOCAL:
        INDICE_PLAYLIST_LOCAL = (INDICE_PLAYLIST_LOCAL + 1) % len(PLAYLIST_LOCAL)
        arq = PLAYLIST_LOCAL[INDICE_PLAYLIST_LOCAL]
        titulo_limpo = formatar_titulo_local(arq)
        ESTADO_PLAYER.update({
            "titulo": titulo_limpo,
            "stream_url": f"/api/music/stream?path={urllib.parse.quote(arq)}",
            "caminho": arq,
            "tocando": True
        })
        await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
        return ESTADO_PLAYER
    return ESTADO_PLAYER

async def anterior() -> dict:
    global ESTADO_PLAYER, PLAYLIST_LOCAL, INDICE_PLAYLIST_LOCAL
    if ESTADO_PLAYER["fonte"] == "spotify":
        simular_tecla_midia(VK_MEDIA_PREV_TRACK)
        ESTADO_PLAYER["tocando"] = True
        await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
        return ESTADO_PLAYER
    elif ESTADO_PLAYER["fonte"] == "local" and PLAYLIST_LOCAL:
        INDICE_PLAYLIST_LOCAL = (INDICE_PLAYLIST_LOCAL - 1) % len(PLAYLIST_LOCAL)
        arq = PLAYLIST_LOCAL[INDICE_PLAYLIST_LOCAL]
        titulo_limpo = formatar_titulo_local(arq)
        ESTADO_PLAYER.update({
            "titulo": titulo_limpo,
            "stream_url": f"/api/music/stream?path={urllib.parse.quote(arq)}",
            "caminho": arq,
            "tocando": True
        })
        await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
        return ESTADO_PLAYER
    return ESTADO_PLAYER

async def definir_volume(vol: int) -> dict:
    global ESTADO_PLAYER
    vol_clamped = max(0, min(100, int(vol)))
    ESTADO_PLAYER["volume"] = vol_clamped
    await enviar_evento_interface({"type": "music_update", "track": ESTADO_PLAYER})
    return ESTADO_PLAYER

def obter_status() -> dict:
    return dict(ESTADO_PLAYER)

# ──────────────────────────────────────────────────────────
PLAYLIST_STARK = [
    "AC/DC Back in Black",
    "AC/DC Shoot to Thrill",
    "Black Sabbath Iron Man",
    "Led Zeppelin Immigrant Song",
    "The Rolling Stones Paint It Black",
    "Queen Don't Stop Me Now",
    "Guns N' Roses Sweet Child O' Mine",
    "AC/DC Highway to Hell",
    "ZZ Top La Grange",
    "Kavinsky Nightcall"
]

def _limpar_query_musica(texto: str) -> str:
    """
    Remove frases acessórias, saudações e comandos de teste,
    extraindo estritamente o nome da música / artista.
    Se o termo ficar vazio, escolhe uma música da playlist estilo Tony Stark.
    """
    import re
    t = texto.lower().strip()

    expressoes_remover = [
        r"\bjarvis\b",
        r"\bteste o sistema de m[úu]sica\b",
        r"\bteste de m[úu]sica\b",
        r"\bteste o sistema\b",
        r"\bteste\b",
        r"\btoco\b",
        r"\btoque\b",
        r"\btocar\b",
        r"\btoca\b",
        r"\bcoloque\b",
        r"\bcoloca\b",
        r"\bbote\b",
        r"\bbota\b",
        r"\breproduza\b",
        r"\breproduzir\b",
        r"\bsintonize\b",
        r"\bsintonizar\b",
        r"\bhá alguma\b",
        r"\bha alguma\b",
        r"\bhá\b",
        r"\bha\b",
        r"\btem alguma\b",
        r"\btem\b",
        r"\baí\b",
        r"\bai\b",
        r"\bpra mim\b",
        r"\bpara mim\b",
        r"\bpor favor\b",
        r"\bpor gentileza\b",
        r"\bno youtube\b",
        r"\bno spotify\b",
        r"\bno pc\b",
        r"\bdo pc\b",
        r"\bno computador\b",
        r"\bdo computador\b",
        r"\buma\b",
        r"\balguma\b",
        r"\bqualquer\b",
        r"\ba m[úu]sica de\b",
        r"\ba m[úu]sica do\b",
        r"\ba m[úu]sica da\b",
        r"\ba m[úu]sica\b",
        r"\ba musica\b",
        r"\bo som de\b",
        r"\bo som do\b",
        r"\bo som da\b",
    ]

    for pat in expressoes_remover:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    # Remove pontuações residuais
    t = re.sub(r"[^\w\s\-\&]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if t in ["música", "musica", ""]:
        escolha = random.choice(PLAYLIST_STARK)
        log.info(f"[MUSICA] Query genérica. Modo Tony Stark ativado: '{escolha}'")
        return escolha

    return t

# ──────────────────────────────────────────────────────────
# 5. PROCESSADOR DE COMANDOS DE VOZ DO JARVIS
# ──────────────────────────────────────────────────────────

async def processar_comando_musica(comando: str) -> str:
    """
    Interpreta o comando de voz em português e executa a ação multimídia correspondente.
    Retorna a fala de resposta elegante e objetiva do Jarvis para o TTS.
    """
    global PEDIDO_MUSICA_PENDENTE
    cmd = comando.lower().strip()
    log.info(f"[MUSICA] Processando comando de voz: '{comando}'")

    # 0. Se há um pedido anterior pendente aguardando escolha de plataforma ("YouTube ou Spotify?")
    if PEDIDO_MUSICA_PENDENTE:
        musica_alvo = PEDIDO_MUSICA_PENDENTE
        if any(k in cmd for k in ["spotify", "no spotify", "pelo spotify"]):
            PEDIDO_MUSICA_PENDENTE = None
            await controlar_spotify(musica_alvo)
            return f"Iniciando '{musica_alvo}' no Spotify, senhor."
        elif any(k in cmd for k in ["local", "locais", "offline", "computador", "pc", "minhas", "nas locais"]):
            PEDIDO_MUSICA_PENDENTE = None
            res = await tocar_local(musica_alvo)
            if "erro" in res:
                res_yt = await tocar_youtube(musica_alvo)
                return f"Não encontrei '{musica_alvo}' no seu computador, senhor. Iniciando diretamente pelo YouTube."
            return f"Reproduzindo sua biblioteca offline: '{res.get('titulo')}'."
        elif any(k in cmd for k in ["youtube", "yt", "no youtube", "pelo youtube", "tanto faz", "qualquer", "pode ser", "sim"]):
            PEDIDO_MUSICA_PENDENTE = None
            res = await tocar_youtube(musica_alvo)
            if "erro" in res:
                return f"Senhor, tive uma instabilidade ao conectar com o YouTube: {res['erro']}."
            return f"Sintonizando '{res.get('titulo')}' no YouTube Music."

    # 1. Comandos de Pausa e Parada
    if any(k in cmd for k in ["pausar música", "pausar musica", "pausa a música", "pausa a musica", "pause a música", "pause a musica", "pausar", "pause", "parar música", "parar musica", "pare a música", "pare a musica", "silenciar"]):
        await pausar()
        return "Música pausada, senhor."

    # 2. Comandos de Retomada
    if any(k in cmd for k in ["continuar música", "continuar musica", "retomar música", "retomar musica", "despausar", "continuar", "retomar"]):
        await continuar()
        return "Retomando a reprodução de áudio, senhor."

    # 3. Próxima Faixa
    if any(k in cmd for k in ["próxima música", "proxima musica", "próxima faixa", "proxima faixa", "pular música", "pular musica", "próxima", "proxima", "pular"]):
        await proxima()
        return f"Avançando para a próxima faixa no {ESTADO_PLAYER.get('fonte', 'player').upper()}."

    # 4. Faixa Anterior
    if any(k in cmd for k in ["música anterior", "musica anterior", "faixa anterior", "voltar música", "voltar musica", "anterior"]):
        await anterior()
        return f"Retornando à faixa anterior no {ESTADO_PLAYER.get('fonte', 'player').upper()}."

    # 5. Controle de Volume
    if "aumentar volume" in cmd or "aumenta o volume" in cmd:
        novo_vol = min(100, ESTADO_PLAYER["volume"] + 20)
        await definir_volume(novo_vol)
        return f"Volume ajustado para {novo_vol} por cento."

    if "diminuir volume" in cmd or "abaixar volume" in cmd or "baixa o volume" in cmd:
        novo_vol = max(0, ESTADO_PLAYER["volume"] - 20)
        await definir_volume(novo_vol)
        return f"Volume reduzido para {novo_vol} por cento."

    # 6. Spotify Explícito
    if "spotify" in cmd:
        PEDIDO_MUSICA_PENDENTE = None
        termo = _limpar_query_musica(cmd)
        await controlar_spotify(termo)
        if termo and termo not in PLAYLIST_STARK:
            return f"Iniciando '{termo}' no Spotify, senhor."
        return "Abrindo o Spotify Desktop, senhor."

    # 7. Músicas Locais Offline Explícito
    if any(k in cmd for k in ["música offline", "musica offline", "minhas músicas", "minhas musicas", "música local", "musica local", "músicas do pc", "musicas do pc", "offline"]):
        PEDIDO_MUSICA_PENDENTE = None
        termo = _limpar_query_musica(cmd)
        res = await tocar_local(termo)
        if "erro" in res:
            res_yt = await tocar_youtube(termo)
            return f"Não encontrei músicas no seu PC, senhor. Iniciando '{res_yt.get('titulo')}' diretamente pelo YouTube."
        return f"Reproduzindo sua biblioteca offline: '{res.get('titulo')}'."

    # 8. YouTube Explícito
    if any(k in cmd for k in ["no youtube", "pelo youtube", "no yt"]):
        PEDIDO_MUSICA_PENDENTE = None
        termo = _limpar_query_musica(cmd)
        res = await tocar_youtube(termo)
        if "erro" in res:
            return f"Senhor, tive uma instabilidade ao conectar com o YouTube: {res['erro']}."
        return f"Sintonizando '{res.get('titulo')}' no YouTube Music."

    # 9. Pedido Geral de Música sem plataforma especificada: Pergunta qual plataforma usar
    termo = _limpar_query_musica(cmd)
    PEDIDO_MUSICA_PENDENTE = termo
    log.info(f"[MUSICA] Pedido pendente registrado: '{termo}'. Solicitando escolha de plataforma.")
    return f"Senhor, deseja que eu reproduza {termo} pelo YouTube, pelo Spotify ou a partir das suas músicas locais?"
