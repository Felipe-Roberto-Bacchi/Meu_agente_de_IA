import os
import pyautogui
import ollama
from PIL import Image
from MODULOS.system.logger import log
from MODULOS.voice import voice_manager

MODELO_VISAO = "moondream"
MODELO_TRADUTOR = "llama3.2:3b"

def _garantir_modelo_visao(modelo: str = MODELO_VISAO) -> bool:
    """Verifica se o modelo de visão está baixado no Ollama; se não, faz pull automático."""
    try:
        lista = ollama.list()
        modelos_existentes = []
        if hasattr(lista, 'models'):
            modelos_existentes = [m.model for m in lista.models]
        elif isinstance(lista, dict) and 'models' in lista:
            modelos_existentes = [m.get('name', m.get('model', '')) for m in lista['models']]
        
        if not any(modelo in m for m in modelos_existentes):
            log.info(f"[VISAO] Modelo '{modelo}' não encontrado localmente. Baixando via Ollama...")
            print(f"[VISAO] Baixando modelo de visão '{modelo}' no Ollama... Por favor, aguarde.")
            ollama.pull(modelo)
            log.info(f"[VISAO] Download do modelo '{modelo}' concluído com sucesso.")
        return True
    except Exception as e:
        log.warning(f"[VISAO] Erro ao verificar/baixar modelo no Ollama: {e}")
        return False

def _adaptar_para_jarvis_pt(resposta_visao: str) -> str:
    """
    Traduz e adapta a descrição da tela (muitas vezes em inglês pelo Moondream)
    para o português do Brasil no estilo elegante e conciso do Jarvis.
    """
    if not resposta_visao or not resposta_visao.strip():
        return "Não consegui identificar detalhes claros na sua tela no momento, senhor."

    prompt = (
        f"Traduza e adapte esta descrição da tela do usuário para o português do Brasil "
        f"no estilo elegante do Jarvis (máximo 2 frases): {resposta_visao.strip()}"
    )

    try:
        res = ollama.chat(
            model=MODELO_TRADUTOR,
            messages=[{'role': 'user', 'content': prompt}],
            options={"temperature": 0.3}
        )
        texto = res['message']['content'].strip()
        return texto.strip('\"\'')
    except Exception as e:
        log.warning(f"[VISAO] Falha ao adaptar resposta com {MODELO_TRADUTOR}: {e}")
        return resposta_visao

def _capturar_screenshot():
    """Tenta capturar o screenshot via pyautogui com fallback para Pillow."""
    try:
        return pyautogui.screenshot()
    except Exception as e:
        log.warning(f"[VISAO] Falha ao capturar tela (possível tela bloqueada): {e}")
        return None

def analisar_tela(pergunta_usuario: str) -> str:
    """
    Captura a tela, redimensiona para otimização de VRAM e inferência rápida,
    processa no modelo de visão do Ollama e retorna descrição elegante em português.
    """
    log.info("[VISAO] Capturando tela...")
    print("[VISAO] Jarvis abrindo os olhos... Tirando print da tela.")

    # Bloqueia a gravação do microfone durante a captura e inferência de visão
    voice_manager.STATUS_FALANDO = True

    image_path = "temp_screen.jpg"

    try:
        # 1. Garante que o modelo de visão esteja disponível
        _garantir_modelo_visao(MODELO_VISAO)

        # 2. Captura a tela e otimiza resolução com Pillow (5x mais rápido e leve em VRAM)
        screenshot = _capturar_screenshot()
        if screenshot is None:
            return "Senhor, a tela parece estar bloqueada ou inacessível para captura no momento."

        screenshot.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        if screenshot.mode in ("RGBA", "P"):
            screenshot = screenshot.convert("RGB")

        screenshot.save(image_path, "JPEG", quality=80, optimize=True)

        log.info("[VISAO] Processando imagem no modelo...")

        # 3. Executa a inferência de visão no Ollama
        prompt_visao = (
            f"Responda de forma curta e direta. "
            f"Com base na imagem da tela, descreva ou responda: {pergunta_usuario}"
        )
        res = ollama.chat(
            model=MODELO_VISAO,
            messages=[
                {
                    'role': 'user',
                    'content': prompt_visao,
                    'images': [image_path]
                }
            ]
        )
        resposta_bruta = res['message']['content'].strip()

        # 4. Traduz e adapta para estilo Jarvis
        resposta_final = _adaptar_para_jarvis_pt(resposta_bruta)
        return resposta_final

    except Exception as e:
        log.error(f"[VISAO] Erro ao analisar tela: {e}")
        return f"Senhor, tive uma falha ao processar a visão: {e}"

    finally:
        # Garante a remoção do arquivo temporário
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
