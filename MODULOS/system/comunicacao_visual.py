import httpx

async def atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao=None):
    payload = {"cor": cor_hex, "intensidade": intensidade, "texto": texto}
    if padrao:
        payload["padrao"] = padrao
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/update", json=payload, timeout=0.5)
    except Exception:
        pass
