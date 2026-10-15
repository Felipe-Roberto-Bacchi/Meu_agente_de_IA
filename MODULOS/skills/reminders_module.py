"""
reminders_module.py
───────────────────
Gerenciador de Lembretes, Tarefas e Agenda Pessoal do Jarvis.
Persiste os itens em DADOS/lembretes.json e integra com comandos de voz e interface HUD.
"""

import os
import json
import uuid
import re
from datetime import datetime
from MODULOS.system.logger import log

LEMBRETES_FILE = "DADOS/lembretes.json"

def carregar_lembretes() -> list[dict]:
    """Carrega todos os lembretes persistidos."""
    if os.path.exists(LEMBRETES_FILE):
        try:
            with open(LEMBRETES_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    return dados
        except Exception as e:
            log.error(f"[LEMBRETES] Erro ao carregar {LEMBRETES_FILE}: {e}")
    return []

def salvar_lembretes(lista: list[dict]):
    """Persiste a lista de lembretes em DADOS/lembretes.json."""
    os.makedirs(os.path.dirname(LEMBRETES_FILE), exist_ok=True)
    try:
        with open(LEMBRETES_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"[LEMBRETES] Erro ao salvar {LEMBRETES_FILE}: {e}")

def extrair_horario_de_texto(texto: str) -> tuple[str, str]:
    """
    Tenta detectar menções de horário no texto (ex: 'às 14:30', 'às 15h', 'para as 9 horas').
    Retorna (texto_limpo, horario_encontrado).
    """
    horario = ""
    # Padrão: 'às 14:30', 'as 15h', 'às 10 horas', 'as 18'
    match = re.search(r'\b(?:às|as|para\s+as|para\s+às)\s+(\d{1,2}(?::\d{2})?)\s*(?:h|hrs|horas)?\b', texto, re.IGNORECASE)
    if match:
        horario = match.group(1)
        if ":" not in horario:
            horario = f"{int(horario):02d}:00"
        # Remove a menção do horário do texto do lembrete
        texto_limpo = re.sub(re.escape(match.group(0)), '', texto, flags=re.IGNORECASE).strip()
    else:
        texto_limpo = texto.strip()

    return texto_limpo, horario

def adicionar_lembrete(texto: str, horario: str = "") -> dict:
    """Adiciona um novo lembrete à agenda."""
    lembretes = carregar_lembretes()
    
    texto_processado = texto.strip()
    for prefixo in ["me lembre de", "me lembre a", "me lembre", "lembrar de", "lembrete de", "adicionar lembrete de", "adicionar lembrete para", "adicionar lembrete", "criar lembrete de", "criar lembrete"]:
        if texto_processado.lower().startswith(prefixo):
            texto_processado = texto_processado[len(prefixo):].strip()
            break

    texto_limpo, horario_detectado = extrair_horario_de_texto(texto_processado)
    horario_final = horario or horario_detectado

    novo_lembrete = {
        "id": f"rem_{uuid.uuid4().hex[:8]}",
        "texto": texto_limpo or texto,
        "horario": horario_final or "",
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "concluido": False
    }

    lembretes.append(novo_lembrete)
    salvar_lembretes(lembretes)
    log.info(f"[LEMBRETES] Novo lembrete adicionado: {novo_lembrete['texto']} (Horário: {novo_lembrete['horario']})")
    return novo_lembrete

def listar_lembretes_pendentes() -> list[dict]:
    """Retorna apenas os lembretes ainda não concluídos."""
    return [l for l in carregar_lembretes() if not l.get("concluido", False)]

def listar_todos_lembretes() -> list[dict]:
    """Retorna todos os lembretes cadastrados."""
    return carregar_lembretes()

def concluir_lembrete(rem_id: str) -> bool:
    """Marca um lembrete como concluído."""
    lembretes = carregar_lembretes()
    alterado = False
    for l in lembretes:
        if l.get("id") == rem_id or rem_id in l.get("texto", "").lower():
            l["concluido"] = True
            alterado = True
            break
    if alterado:
        salvar_lembretes(lembretes)
        log.info(f"[LEMBRETES] Lembrete {rem_id} concluído.")
        return True
    return False

def alternar_lembrete(rem_id: str) -> bool:
    """Inverte o estado de concluído de um lembrete."""
    lembretes = carregar_lembretes()
    for l in lembretes:
        if l.get("id") == rem_id:
            l["concluido"] = not l.get("concluido", False)
            salvar_lembretes(lembretes)
            return True
    return False

def remover_lembrete(rem_id: str) -> bool:
    """Remove definitivamente um lembrete pelo ID."""
    lembretes = carregar_lembretes()
    novos = [l for l in lembretes if l.get("id") != rem_id]
    if len(novos) != len(lembretes):
        salvar_lembretes(novos)
        log.info(f"[LEMBRETES] Lembrete {rem_id} removido.")
        return True
    return False

def processar_comando_voz(texto: str) -> str:
    """
    Processa solicitações e comandos em linguagem natural referentes à agenda.
    """
    t_lower = texto.lower()

    # 1. Consulta / Listagem unificada de agenda (Lembretes locais + Google Calendar)
    gatilhos_listar = [
        "quais são meus lembretes", "quais sao meus lembretes", "quais meus lembretes",
        "meus lembretes", "minha agenda", "listar lembretes", "compromissos de hoje",
        "o que tenho hoje", "lembretes de hoje", "dá uma olhada na minha agenda",
        "da uma olhada na minha agenda", "olhada na minha agenda", "tenho algum compromisso",
        "tenho compromisso", "compromissos", "agenda de hoje", "agenda"
    ]
    if any(g in t_lower for g in gatilhos_listar):
        pendentes = listar_lembretes_pendentes()

        eventos_google = []
        try:
            from MODULOS.skills import google_mcp_module
            eventos_google = google_mcp_module.listar_eventos_google_calendar(max_results=3)
        except Exception as e_gc:
            log.warning(f"[AGENDA] Falha ao consultar Google Calendar: {e_gc}")

        partes_fala = []
        if eventos_google:
            desc_g = [f"'{e['titulo']}' às {e['horario']}" for e in eventos_google]
            partes_fala.append("No seu Google Calendar constam: " + "; ".join(desc_g))

        if pendentes:
            desc_l = []
            for item in pendentes:
                if item.get("horario"):
                    desc_l.append(f"'{item['texto']}' às {item['horario']}")
                else:
                    desc_l.append(f"'{item['texto']}'")
            partes_fala.append("Nos lembretes locais constam: " + "; ".join(desc_l))

        if partes_fala:
            return "Senhor, verificando sua agenda: " + ". Além disso, ".join(partes_fala) + "."
        else:
            return "Sua agenda está livre no momento, senhor. Não constam compromissos no Google Calendar nem lembretes pendentes."

    # 2. Conclusão de lembrete
    if "concluir lembrete" in t_lower or "marcar lembrete" in t_lower or "finalizar lembrete" in t_lower:
        alvo = t_lower
        for stop in ["concluir lembrete de", "concluir lembrete", "marcar lembrete de", "marcar lembrete", "finalizar lembrete"]:
            alvo = alvo.replace(stop, "").strip()
        pendentes = listar_lembretes_pendentes()
        for p in pendentes:
            if alvo and alvo in p["texto"].lower():
                concluir_lembrete(p["id"])
                return f"Lembrete '{p['texto']}' marcado como concluído, senhor."
        if pendentes:
            concluir_lembrete(pendentes[0]["id"])
            return f"Primeiro lembrete pendente, '{pendentes[0]['texto']}', marcado como concluído."
        return "Não encontrei nenhum lembrete pendente para concluir, senhor."

    # 3. Adição de lembrete
    novo = adicionar_lembrete(texto)
    if novo.get("horario"):
        return f"Lembrete anotado na sua agenda para às {novo['horario']}: {novo['texto']}."
    return f"Lembrete anotado na sua agenda, senhor: {novo['texto']}."
