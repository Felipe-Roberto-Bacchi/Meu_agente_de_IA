"""
google_mcp_module.py
────────────────────
Integração com o ecossistema Google Workspace (Google Calendar e Google Drive)
utilizando autenticação oficial OAuth2 via Google API Client.
Permite listar/criar eventos na agenda Google e buscar arquivos no Google Drive.
"""

import os
import json
import datetime
from datetime import timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from MODULOS.system.logger import log
from MODULOS.skills import reminders_module

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.readonly'
]

CREDS_FILE = "DADOS/google_credentials.json"
TOKEN_FILE = "DADOS/google_token.json"


def obter_credenciais_google() -> Optional[Credentials]:
    """
    Carrega e valida as credenciais OAuth2 do Google a partir do TOKEN_FILE.
    Se o token estiver expirado e tiver refresh token, renova automaticamente.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            log.warning(f"[GOOGLE] Erro ao carregar {TOKEN_FILE}: {e}")

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
                token_f.write(creds.to_json())
            log.info("[GOOGLE] Token de acesso renovado com sucesso.")
        except Exception as e:
            log.warning(f"[GOOGLE] Falha ao renovar token OAuth: {e}")
            creds = None

    return creds if (creds and creds.valid) else None


def obter_status_google_auth() -> dict:
    """Retorna o status atual da integração com o Google Workspace."""
    configurado = os.path.exists(CREDS_FILE)
    creds = obter_credenciais_google()
    autenticado = creds is not None

    if autenticado:
        mensagem = "Conta Google conectada e autenticada com sucesso."
    elif configurado:
        mensagem = "Arquivo de credenciais presente. Clique para autenticar no navegador."
    else:
        mensagem = "Credenciais não configuradas. Coloque o arquivo google_credentials.json na pasta DADOS/."

    return {
        "configurado": configurado,
        "autenticado": autenticado,
        "mensagem": mensagem
    }


def iniciar_fluxo_autenticacao_google() -> dict:
    """
    Inicia o fluxo de autorização OAuth2 abrindo o navegador do usuário.
    Gera e salva o token em DADOS/google_token.json.
    """
    if not os.path.exists(CREDS_FILE):
        return {
            "sucesso": False,
            "mensagem": "Arquivo DADOS/google_credentials.json não encontrado. Obtenha as credenciais OAuth no Google Cloud Console."
        }

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, prompt='consent')
        with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
            token_f.write(creds.to_json())
        log.info("[GOOGLE] Autenticação OAuth2 realizada com sucesso!")
        return {
            "sucesso": True,
            "mensagem": "Autenticação concluída! O Jarvis agora tem acesso ao seu Google Calendar e Google Drive."
        }
    except Exception as e:
        log.error(f"[GOOGLE] Erro no fluxo OAuth2: {e}")
        return {
            "sucesso": False,
            "mensagem": f"Erro durante a autenticação Google: {str(e)}"
        }


# ──────────────────────────────────────────────────────────
# 1. GOOGLE CALENDAR
# ──────────────────────────────────────────────────────────

def listar_eventos_google_calendar(max_results: int = 5) -> list[dict]:
    """
    Busca os próximos eventos reais da agenda Google do usuário.
    Retorna uma lista estruturada de eventos.
    """
    creds = obter_credenciais_google()
    if not creds:
        log.info("[GOOGLE/CALENDAR] Usuário não autenticado no Google.")
        return []

    try:
        service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
        agora = datetime.datetime.now(timezone.utc).isoformat()
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=agora,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        items = events_result.get('items', [])
        eventos = []

        for item in items:
            inicio = item.get('start', {}).get('dateTime') or item.get('start', {}).get('date', '')
            fim = item.get('end', {}).get('dateTime') or item.get('end', {}).get('date', '')
            titulo = item.get('summary', 'Sem Título')

            horario_formatado = "--:--"
            if "T" in inicio:
                try:
                    dt = datetime.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
                    horario_formatado = dt.strftime("%H:%M")
                except Exception:
                    pass

            eventos.append({
                "id": item.get('id'),
                "titulo": titulo,
                "inicio": inicio,
                "fim": fim,
                "horario": horario_formatado,
                "link": item.get('htmlLink', ''),
                "origem": "google_calendar"
            })

        log.info(f"[GOOGLE/CALENDAR] {len(eventos)} eventos obtidos da agenda.")
        return eventos

    except Exception as e:
        log.error(f"[GOOGLE/CALENDAR] Erro ao listar eventos: {e}")
        return []


def criar_evento_google_calendar(titulo: str, data_hora_iso: str = None, duracao_min: int = 60) -> dict:
    """
    Cria um novo evento no Google Agenda do usuário.
    Se a conta Google não estiver conectada, salva no reminders_module como fallback local.
    """
    creds = obter_credenciais_google()
    
    # Se não tiver hora informada, define para daqui a 1 hora
    if not data_hora_iso:
        dt_inicio = datetime.datetime.now() + datetime.timedelta(hours=1)
    else:
        try:
            dt_inicio = datetime.datetime.fromisoformat(data_hora_iso)
        except Exception:
            dt_inicio = datetime.datetime.now() + datetime.timedelta(hours=1)

    dt_fim = dt_inicio + datetime.timedelta(minutes=duracao_min)
    horario_str = dt_inicio.strftime("%H:%M")

    # Salva sempre nos lembretes locais como redundância
    lembrete_local = reminders_module.adicionar_lembrete(titulo, horario=horario_str)

    if not creds:
        log.info(f"[GOOGLE/CALENDAR] Sem conta Google conectada. Evento salvo nos lembretes locais.")
        return {
            "sucesso": True,
            "origem": "local_fallback",
            "titulo": titulo,
            "horario": horario_str,
            "mensagem": f"Evento '{titulo}' agendado nos lembretes locais para às {horario_str} (conecte a conta Google para sincronizar com sua agenda online)."
        }

    try:
        service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
        evento_body = {
            'summary': titulo,
            'description': f'Criado automaticamente pelo Jarvis Neural Assistant em {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}.',
            'start': {
                'dateTime': dt_inicio.astimezone().isoformat(),
            },
            'end': {
                'dateTime': dt_fim.astimezone().isoformat(),
            },
        }

        created_event = service.events().insert(calendarId='primary', body=evento_body).execute()
        link = created_event.get('htmlLink', '')
        log.info(f"[GOOGLE/CALENDAR] Evento '{titulo}' criado com sucesso no Google Calendar.")

        return {
            "sucesso": True,
            "origem": "google_calendar",
            "id": created_event.get('id'),
            "titulo": titulo,
            "horario": horario_str,
            "link": link,
            "mensagem": f"Evento '{titulo}' agendado no seu Google Calendar para às {horario_str} com sucesso, senhor."
        }
    except Exception as e:
        log.error(f"[GOOGLE/CALENDAR] Falha ao criar evento no Google Calendar: {e}")
        return {
            "sucesso": True,
            "origem": "local_fallback",
            "titulo": titulo,
            "horario": horario_str,
            "mensagem": f"Evento salvo nos lembretes locais para às {horario_str}, senhor (houve uma instabilidade na API do Google Calendar)."
        }


# ──────────────────────────────────────────────────────────
# 2. GOOGLE DRIVE
# ──────────────────────────────────────────────────────────

def buscar_arquivos_google_drive(termo: str = "", max_results: int = 6) -> list[dict]:
    """
    Busca arquivos no Google Drive.
    Se o termo for genérico ou de teste, lista os arquivos mais recentes sem filtro restritivo de nome.
    Se houver nome específico de arquivo, limpa a query e filtra com 'name contains'.
    """
    creds = obter_credenciais_google()
    if not creds:
        log.info("[GOOGLE/DRIVE] Usuário não autenticado no Google.")
        return []

    try:
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        
        t_clean = termo.strip().lower() if termo else ""
        termos_genericos = {
            "teste", "testar", "acessar", "acesso", "aleatórios", "aleatorios",
            "aleatorio", "aleatório", "alguns", "listar", "liste", "meus", "meu",
            "recentes", "recente", "tudo", "quais", "arquivos", "arquivo",
            "documentos", "documento", "pasta", "drive", "google", "no drive",
            "no google drive", "por favor", "mim", "para", "pra", "de", "do", "da",
            "que", "estão", "estao", "no", "na", "nos", "nas", "tem", "há", "ha",
            "tiver", "estiver", "minha", "minhas", "conta", "me", "mostre",
            "mostrar", "veja", "ver", "dá", "da", "uma", "olhada", "tenta", "tente"
        }

        # Limpa pontuações e extrai palavras
        import re
        t_filtrado = re.sub(
            r"\b(jarvis|faz um teste|fazer teste|teste para mim|teste pra mim|tenta acessar|tente acessar|tenta entrar|acessar o|acessar meu|liste alguns|listar alguns|arquivos aleatórios|arquivos aleatorios|que estão no|que estao no|que estão|que estao|no google drive|no drive|google drive|drive|arquivos|arquivo|documentos|documento|por favor)\b",
            " ",
            t_clean,
            flags=re.IGNORECASE
        )
        palavras_relevantes = [p for p in re.sub(r"[^\w\s]", " ", t_filtrado).split() if p and p not in termos_genericos]

        termo_alvo = " ".join(palavras_relevantes).strip()
        if not palavras_relevantes or len(termo_alvo) <= 2:
            # Query sem restrição de nome para trazer arquivos recentes reais
            q = "trashed = false"
            log.info("[GOOGLE/DRIVE] Busca genérica ou listagem recente detectada. Listando arquivos recentes.")
        else:
            termo_escapado = termo_alvo.replace("'", "\\'")
            q = f"name contains '{termo_escapado}' and trashed = false"
            log.info(f"[GOOGLE/DRIVE] Filtrando arquivos por termo específico: '{termo_escapado}'")

        results = service.files().list(
            q=q,
            pageSize=max_results,
            orderBy="modifiedTime desc",
            fields="files(id, name, mimeType, webViewLink, modifiedTime, size)"
        ).execute()

        files = results.get('files', [])
        arquivos = []

        for f in files:
            file_id = f.get('id')
            mime = f.get('mimeType', '')
            conteudo_snippet = ""

            # Se for Google Docs, exporta como plain text para ler o conteúdo
            if mime == 'application/vnd.google-apps.document':
                try:
                    doc_bytes = service.files().export(fileId=file_id, mimeType='text/plain').execute()
                    texto_doc = doc_bytes.decode('utf-8', errors='ignore')
                    conteudo_snippet = texto_doc[:300].strip().replace('\n', ' ')
                except Exception:
                    pass

            arquivos.append({
                "id": file_id,
                "nome": f.get('name'),
                "tipo": mime,
                "link": f.get('webViewLink', ''),
                "modificado": f.get('modifiedTime', ''),
                "snippet": conteudo_snippet
            })

        log.info(f"[GOOGLE/DRIVE] {len(arquivos)} arquivo(s) localizado(s).")
        return arquivos

    except Exception as e:
        log.error(f"[GOOGLE/DRIVE] Erro ao buscar arquivos: {e}")
        return []
