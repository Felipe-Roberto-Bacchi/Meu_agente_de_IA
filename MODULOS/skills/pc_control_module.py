"""
pc_control_module.py
────────────────────
Mordomo de Sistema Operacional Windows & Controle de PC para o Jarvis.
- Controle do Volume Master do Sistema Windows via PyCaw.
- Leitura, análise e resumo inteligente da Área de Transferência (Clipboard) via Pyperclip + LLM.
- Criação e organização de notas rápidas no Vault do Obsidian.
"""

import os
import re
import datetime
from typing import Optional

import pyperclip
from pycaw.pycaw import AudioUtilities
from MODULOS.system.logger import log

# ──────────────────────────────────────────────────────────
# 1. CONTROLE DE VOLUME DO SISTEMA WINDOWS (PYCAW)
# ──────────────────────────────────────────────────────────

def _obter_endpoint_volume():
    """Retorna o endpoint de controle de volume dos alto-falantes padrão."""
    try:
        speakers = AudioUtilities.GetSpeakers()
        if hasattr(speakers, 'EndpointVolume'):
            return speakers.EndpointVolume
        return None
    except Exception as e:
        log.error(f"[PC_CONTROL] Erro ao obter endpoint de volume PyCaw: {e}")
        return None


def obter_volume_sistema() -> int:
    """Retorna o volume master atual do Windows (0 a 100)."""
    try:
        ep = _obter_endpoint_volume()
        if ep:
            scalar = ep.GetMasterVolumeLevelScalar()
            return int(round(scalar * 100))
    except Exception as e:
        log.warning(f"[PC_CONTROL] Falha ao ler volume: {e}")
    return 50


def definir_volume_sistema(pct: int) -> str:
    """Define o volume master do Windows para uma porcentagem exata (0 a 100)."""
    try:
        ep = _obter_endpoint_volume()
        if not ep:
            return "Não foi possível acessar o dispositivo de áudio do sistema, senhor."

        pct_clamped = max(0, min(100, int(pct)))
        scalar = pct_clamped / 100.0

        # Se estava mutado, desmuta automaticamente ao alterar volume
        if ep.GetMute():
            ep.SetMute(0, None)

        ep.SetMasterVolumeLevelScalar(scalar, None)
        log.info(f"[PC_CONTROL] Volume master do sistema ajustado para {pct_clamped}%.")
        return f"Volume do sistema ajustado para {pct_clamped} por cento, senhor."
    except Exception as e:
        log.error(f"[PC_CONTROL] Erro ao definir volume: {e}")
        return "Tive um erro ao tentar alterar o volume do Windows, senhor."


def ajustar_volume_sistema(delta: int) -> str:
    """Aumenta ou diminui o volume master do sistema pelo delta especificado."""
    vol_atual = obter_volume_sistema()
    novo_vol = max(0, min(100, vol_atual + delta))
    return definir_volume_sistema(novo_vol)


def mutar_som_pc(mutar: Optional[bool] = None) -> str:
    """Muta, desmuta ou alterna o som master do sistema."""
    try:
        ep = _obter_endpoint_volume()
        if not ep:
            return "Não foi possível acessar os drivers de áudio do sistema."

        if mutar is None:
            estado_atual = ep.GetMute()
            novo_estado = 0 if estado_atual else 1
        else:
            novo_estado = 1 if mutar else 0

        ep.SetMute(novo_estado, None)
        status_txt = "mutado" if novo_estado else "desmutado"
        log.info(f"[PC_CONTROL] Áudio do sistema {status_txt}.")
        return f"Áudio do sistema {status_txt}, senhor."
    except Exception as e:
        log.error(f"[PC_CONTROL] Erro ao mutar áudio: {e}")
        return "Erro ao alterar o estado de mudo do computador."


# ──────────────────────────────────────────────────────────
# 2. RESUMO E ANÁLISE DA ÁREA DE TRANSFERÊNCIA (CLIPBOARD)
# ──────────────────────────────────────────────────────────

async def processar_clipboard(comando: str = "") -> str:
    """
    Lê o texto atualmente copiado na área de transferência (Ctrl+C).
    Se for curto, relata diretamente. Se for longo, sintetiza usando o LLM.
    """
    try:
        texto_copiado = pyperclip.paste()
    except Exception as e:
        log.error(f"[PC_CONTROL] Erro ao acessar clipboard: {e}")
        return "Não consegui acessar sua área de transferência no momento, senhor."

    if not texto_copiado or not texto_copiado.strip():
        return "Sua área de transferência está vazia no momento, senhor. Copie algum texto com Ctrl+C primeiro."

    texto_copiado = texto_copiado.strip()
    qtd_palavras = len(texto_copiado.split())
    log.info(f"[PC_CONTROL] Clipboard capturado: {qtd_palavras} palavras ({len(texto_copiado)} caracteres).")

    # Se for bem curto (até 150 caracteres), responde diretamente
    if len(texto_copiado) <= 150 and "\n" not in texto_copiado:
        return f'O texto copiado na sua área de transferência é: "{texto_copiado}".'

    # Se for texto longo ou código, solicita síntese ao LLM do Jarvis
    from MODULOS.brain.core.client_llm import consultar_llm

    prompt_analise = f"""Você é o Jarvis. O usuário pediu para analisar ou resumir o texto que ele acabou de copiar na Área de Transferência do computador.
Comando do usuário: "{comando}"
Texto copiado ({len(texto_copiado)} caracteres):
\"\"\"
{texto_copiado[:3500]}
\"\"\"

Instruções:
- Forneça uma resposta direta, elegante e concisa (máximo 2 a 3 frases faladas).
- Se for um código, explique o que ele faz em uma frase.
- Se for um artigo ou notícia, sintetize o ponto central e o resultado principal.
- Não use markdown excessivo (será falado via TTS). Seja o assistente inteligente Tony Stark.
"""

    resposta_llm = await consultar_llm(prompt_analise, max_tokens=180)
    if resposta_llm and resposta_llm.strip():
        return resposta_llm.strip()

    return f"O texto copiado possui {qtd_palavras} palavras. Trata-se de: {texto_copiado[:180]}..."


# ──────────────────────────────────────────────────────────
# 3. NOTAS RÁPIDAS NO OBSIDIAN VAULT
# ──────────────────────────────────────────────────────────

def _localizar_diretorio_obsidian() -> str:
    """
    Localiza o diretório do Obsidian Vault do usuário.
    Tenta variável de ambiente, pastas comuns no usuário ou fallback em DADOS/Obsidian_Vault.
    """
    env_vault = os.environ.get("OBSIDIAN_VAULT")
    if env_vault and os.path.isdir(env_vault):
        return env_vault

    user_home = os.path.expanduser("~")
    possiveis = [
        os.path.join(user_home, "Documents", "Obsidian Vault"),
        os.path.join(user_home, "Documentos", "Obsidian Vault"),
        os.path.join(user_home, "Obsidian"),
        os.path.join(os.getcwd(), "DADOS", "Obsidian_Vault")
    ]

    for p in possiveis:
        if os.path.isdir(p):
            return p

    # Cria pasta padrão se nenhuma existir
    padrao = os.path.join(os.getcwd(), "DADOS", "Obsidian_Vault")
    os.makedirs(padrao, exist_ok=True)
    return padrao


def salvar_nota_obsidian(titulo: str, conteudo: str) -> str:
    """
    Cria uma nova nota em formato Markdown no Vault do Obsidian com frontmatter.
    """
    diretorio = _localizar_diretorio_obsidian()
    agora = datetime.datetime.now()
    timestamp_str = agora.strftime("%Y-%m-%d %H:%M")
    data_arquivo = agora.strftime("%Y%m%d_%H%M%S")

    # Sanitiza título para nome de arquivo
    titulo_sanitizado = re.sub(r'[\\/*?:"<>|]', "", titulo).strip()
    if not titulo_sanitizado:
        titulo_sanitizado = f"Nota_{data_arquivo}"

    nome_arquivo = f"{titulo_sanitizado}.md"
    caminho_completo = os.path.join(diretorio, nome_arquivo)

    conteudo_md = f"""---
title: "{titulo}"
created: "{timestamp_str}"
tags:
  - jarvis
  - nota_rapida
---

# {titulo}

{conteudo}

---
*Nota registrada automaticamente pelo Jarvis Neural Assistant em {timestamp_str}*
"""

    try:
        with open(caminho_completo, "w", encoding="utf-8") as f:
            f.write(conteudo_md)
        log.info(f"[PC_CONTROL] Nota salva no Obsidian: {caminho_completo}")
        return f"Nota '{titulo}' gravada com sucesso no seu Vault do Obsidian, senhor."
    except Exception as e:
        log.error(f"[PC_CONTROL] Erro ao salvar nota Obsidian: {e}")
        return f"Não foi possível salvar a nota no Obsidian devido a um erro de gravação: {str(e)}"


# ──────────────────────────────────────────────────────────
# 4. PROCESSADOR GERAL DE COMANDOS DE CONTROLE DO PC
# ──────────────────────────────────────────────────────────

async def processar_comando_pc(comando: str) -> str:
    """
    Roteador e executor de comandos de controle do PC e mordomo de sistema.
    """
    cmd = comando.lower().strip()
    log.info(f"[PC_CONTROL] Processando comando: '{comando}'")

    # 1. Volume específico (ex: "volume em 60%", "colocar volume em 80")
    match_pct = re.search(r"volume\s*(?:em|para|no)?\s*(\d+)(?:\s*%)?", cmd)
    if match_pct:
        val = int(match_pct.group(1))
        return definir_volume_sistema(val)

    # 2. Aumentar volume
    if any(k in cmd for k in ["aumentar volume", "aumenta o volume", "mais alto", "sobe o volume", "aumenta o som"]):
        return ajustar_volume_sistema(+15)

    # 3. Abaixar volume
    if any(k in cmd for k in ["abaixar volume", "diminuir volume", "baixa o volume", "mais baixo", "abaixa o som"]):
        return ajustar_volume_sistema(-15)

    # 4. Mutar som do PC
    if any(k in cmd for k in ["mutar som do pc", "mutar pc", "mutar som", "muta o pc", "silenciar o pc", "silenciar o som", "mudo no pc"]):
        return mutar_som_pc(True)

    # 5. Desmutar som do PC
    if any(k in cmd for k in ["desmutar som do pc", "desmutar pc", "desmuta o som", "desmutar o som", "desmutar o pc", "tirar do mudo"]):
        return mutar_som_pc(False)

    # 6. Clipboard / Área de Transferência
    if any(k in cmd for k in ["copiei", "texto copiado", "área de transferência", "area de transferencia", "clipboard", "o que está copiado"]):
        return await processar_clipboard(comando)

    # 7. Obsidian / Notas
    if any(k in cmd for k in ["obsidian", "salve como nota", "salva como nota", "criar nota", "anote isso", "anota isso"]):
        # Extrai o conteúdo a ser anotado
        texto_nota = comando
        for p in ["jarvis", "salve isso como nota no obsidian", "salva como nota no obsidian", "salve no obsidian", "salva no obsidian", "criar nota no obsidian", "anote no obsidian", "anota no obsidian", "obsidian", "anote isso", "anota isso", "por favor"]:
            texto_nota = re.sub(rf"\b{p}\b", "", texto_nota, flags=re.IGNORECASE)
        texto_nota = texto_nota.strip(' :,."\'')
        
        # Se após limpeza ficou vazio, anota o conteúdo da área de transferência!
        if not texto_nota:
            try:
                clip = pyperclip.paste().strip()
                if clip:
                    return salvar_nota_obsidian("Nota da Área de Transferência", clip)
            except Exception:
                pass
            return "Senhor, o que você gostaria que eu registrasse na nota do Obsidian?"

        titulo_nota = texto_nota[:35] + ("..." if len(texto_nota) > 35 else "")
        return salvar_nota_obsidian(titulo_nota, texto_nota)

    return "Comando de controle de sistema processado, senhor."
