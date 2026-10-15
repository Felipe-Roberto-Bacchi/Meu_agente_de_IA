import httpx

_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=0.5)
    return _client

async def atualizar_jarvis(cor_hex="#00ffff", intensidade=0.1, texto="", padrao=None):
    payload = {"cor": cor_hex, "intensidade": intensidade, "texto": texto}
    if padrao:
        payload["padrao"] = padrao
    try:
        client = _get_client()
        await client.post("http://localhost:8000/update", json=payload)
    except Exception:
        pass

async def enviar_evento_interface(dados: dict):
    try:
        client = _get_client()
        await client.post("http://localhost:8000/update", json=dados)
    except Exception:
        pass

