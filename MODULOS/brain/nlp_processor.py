from rapidfuzz import utils

# Dicionário focado em corrigir o que o Whisper ouve errado
DICIONARIO_CORRECAO = {
    "aprei": "abrir", "abri": "abrir", "abre": "abrir", "apear": "abrir",
    "painel amd": "radeonsofiwre", "adrenalina": "radeonsofiwre",
    "fúzeo": "fusion", "ópera": "opera", "fogo no fox": "firefox",
    "cepeu": "cpu", "gepeu": "gpu", "code": "qual", "quanto": "qual",
    "rano": "ram", "pirâmide": "hardware"
}

def processar_intencao(comando_voz):
    # 1. Normalização e Correção Fonética
    palavras = comando_voz.lower().split()
    for i, p in enumerate(palavras):
        if p in DICIONARIO_CORRECAO: 
            palavras[i] = DICIONARIO_CORRECAO[p]
    
    texto = " ".join(palavras)

    # --- FILTRO DE SEGURANÇA: MEMÓRIA DE FATO ---
    # Se o senhor estiver mandando "guardar", "lembrar" ou "esquecer", 
    # forçamos a rota de CONVERSA para o main.py tratar como SQL.
    gatilhos_sql = ["guarde", "salve", "anote", "lembre", "grave", "recorde"]
    if any(x in texto for x in gatilhos_sql):
        return "CONVERSA", texto

    # 2. Gatilhos de HARDWARE (Melhorado para não ser "guloso")
    palavras_hw_diretas = ["temperatura", "status", "hardware", "cpu", "gpu", "vram", "processador"]
    
    # Ele só entra em Hardware pela palavra "memória" se houver contexto de monitoramento
    contexto_monitor = ["uso", "quanto", "status", "porcentagem", "tá", "esta"]
    pediu_hardware = any(x in texto for x in palavras_hw_diretas)
    pediu_ram = "ram" in texto or ("memória" in texto and any(m in texto for m in contexto_monitor))

    if pediu_hardware or pediu_ram:
        foco = "tudo"
        if "cpu" in texto or "processador" in texto: foco = "cpu"
        elif "gpu" in texto or "placa" in texto: foco = "gpu"
        elif "ram" in texto or "memória" in texto: foco = "ram"
        return "HARDWARE", foco

    # 3. Gatilhos de ABRIR_APP
    gatilhos_abrir = ["abrir", "iniciar", "executar", "lançar", "abre", "start"]
    if any(x in texto for x in gatilhos_abrir):
        alvo = utils.default_process(texto)
        termos_limpeza = gatilhos_abrir + ["o ", "a ", "por favor", "meu", "minha"]
        for v in termos_limpeza:
            alvo = alvo.replace(v, "")
        return "ABRIR_APP", alvo.strip()

    # 4. Gatilhos de VISÃO
    palavras_visao = ["olha", "vê", "tela", "mostra", "analisa"]
    if any(x in texto for x in palavras_visao):
        return "VISAO", texto

    # 5. CONVERSA (Padrão)
    return "CONVERSA", texto
