"""
memory_long.py
──────────────
Memória de longo prazo do Jarvis usando ChromaDB.

Dois bancos vetoriais separados:
  chroma_fatos/     → fatos permanentes chave/valor (nome, preferências, etc.)
  chroma_historico/ → histórico de conversas passadas

Busca semântica: "como me chamo" encontra "nome = Felipe" sem precisar
da palavra exata — o ChromaDB entende o significado.
"""

import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import uuid

# ─────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────

# Embedding local via sentence-transformers (roda na CPU, sem internet)
_EMB = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_client_fatos     = None
_client_historico = None
_col_fatos        = None
_col_historico    = None


def inicializar_banco():
    """Cria/abre os dois bancos ChromaDB. Chame uma vez no boot."""
    global _client_fatos, _client_historico, _col_fatos, _col_historico

    # Banco de fatos permanentes
    _client_fatos = chromadb.PersistentClient(path="DADOS/chroma_fatos")
    _col_fatos = _client_fatos.get_or_create_collection(
        name="fatos",
        embedding_function=_EMB,
        metadata={"hnsw:space": "cosine"}
    )

    # Banco de histórico de conversas
    _client_historico = chromadb.PersistentClient(path="DADOS/chroma_historico")
    _col_historico = _client_historico.get_or_create_collection(
        name="historico",
        embedding_function=_EMB,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"[MEMORIA] Fatos: {_col_fatos.count()} entradas | "
          f"Histórico: {_col_historico.count()} entradas")


def _garantir_init():
    """Inicializa automaticamente se ainda não foi feito."""
    if _col_fatos is None or _col_historico is None:
        inicializar_banco()


# ─────────────────────────────────────────
#  FATOS — memória semântica permanente
# ─────────────────────────────────────────

def salvar_memoria(chave: str, valor: str) -> str:
    """
    Salva ou atualiza um fato.
    O documento indexado é "chave: valor" para busca semântica rica.
    """
    _garantir_init()
    chave = chave.strip().lower()
    valor = valor.strip()

    # ChromaDB usa upsert por ID — usa a chave como ID para permitir update
    doc_id = f"fato_{chave.replace(' ', '_')}"
    documento = f"{chave}: {valor}"

    _col_fatos.upsert(
        ids=[doc_id],
        documents=[documento],
        metadatas=[{
            "chave": chave,
            "valor": valor,
            "atualizado": datetime.now().isoformat()
        }]
    )
    return f"Entendido, senhor. Gravei que '{chave}' é '{valor}'."


def buscar_memoria(consulta: str, n=3) -> str | None:
    """
    Busca semântica — retorna os fatos mais relevantes para a consulta.
    Funciona mesmo com palavras diferentes (ex: 'nome' encontra 'como me chamo').
    """
    _garantir_init()
    if _col_fatos.count() == 0:
        return None

    resultados = _col_fatos.query(
        query_texts=[consulta],
        n_results=min(n, _col_fatos.count())
    )

    docs = resultados.get("documents", [[]])[0]
    metas = resultados.get("metadatas", [[]])[0]

    if not docs:
        return None

    # Formata os resultados encontrados
    linhas = [f"- {m['chave']}: {m['valor']}" for m in metas]
    return "\n".join(linhas)


def apagar_memoria(chave: str) -> str:
    """Remove um fato pelo nome da chave."""
    _garantir_init()
    doc_id = f"fato_{chave.strip().lower().replace(' ', '_')}"
    try:
        _col_fatos.delete(ids=[doc_id])
        return f"Memória sobre '{chave}' apagada, senhor."
    except Exception as e:
        return f"Não encontrei nada sobre '{chave}' para apagar."


def listar_fatos(n=20) -> list[dict]:
    """Retorna os N fatos mais recentes (para debug ou interface)."""
    _garantir_init()
    if _col_fatos.count() == 0:
        return []
    resultado = _col_fatos.get(limit=n, include=["metadatas"])
    return resultado.get("metadatas", [])


# ─────────────────────────────────────────
#  HISTÓRICO — conversas passadas
# ─────────────────────────────────────────

# Histórico ilimitado — o ChromaDB gerencia o armazenamento de forma eficiente


def registrar_conversa_global(papel: str, mensagem: str):
    """Salva uma mensagem no histórico vetorial (sem limite de entradas)."""
    _garantir_init()
    if not mensagem or not mensagem.strip():
        return

    doc_id = str(uuid.uuid4())
    _col_historico.add(
        ids=[doc_id],
        documents=[mensagem],
        metadatas=[{
            "papel": papel,
            "timestamp": datetime.now().isoformat(),
            "ts_unix": int(datetime.now().timestamp())
        }]
    )


def buscar_historico_relevante(consulta: str, n=3, max_meses=24) -> list[dict]:
    """
    Busca em cascata mensal:
      1. Tenta achar resultados no mês atual.
      2. Se não achar nada, recua um mês e tenta de novo.
      3. Continua recuando até 'max_meses' meses no passado.
    Assim o Jarvis sempre prioriza contexto recente, mas nunca perde
    conversas antigas sobre assuntos que não aparecem todo mês.
    """
    _garantir_init()
    if _col_historico.count() == 0:
        return []

    agora = datetime.now()

    for meses_atras in range(max_meses):
        # Calcula o início e fim do mês-alvo
        mes_alvo = agora.month - meses_atras
        ano_alvo = agora.year
        while mes_alvo <= 0:
            mes_alvo += 12
            ano_alvo -= 1

        # Calcula o início e fim do mês-alvo em Unix epoch (int)
        inicio_unix = int(datetime(ano_alvo, mes_alvo, 1).timestamp())
        if mes_alvo == 12:
            fim_unix = int(datetime(ano_alvo + 1, 1, 1).timestamp())
        else:
            fim_unix = int(datetime(ano_alvo, mes_alvo + 1, 1).timestamp())

        try:
            resultado = _col_historico.query(
                query_texts=[consulta],
                n_results=min(n, _col_historico.count()),
                where={"$and": [
                    {"ts_unix": {"$gte": inicio_unix}},
                    {"ts_unix": {"$lt": fim_unix}}
                ]}
            )

            docs  = resultado.get("documents",  [[]])[0]
            metas = resultado.get("metadatas",  [[]])[0]

            if docs:
                from MODULOS.system.logger import log
                label = "mês atual" if meses_atras == 0 else f"{meses_atras} mês(es) atrás"
                log.debug(f"[MEMÓRIA] Histórico encontrado em: {label} ({ano_alvo}/{mes_alvo:02d})")
                return [
                    {"papel": m["papel"], "mensagem": d, "timestamp": m["timestamp"]}
                    for d, m in zip(docs, metas)
                ]
        except Exception:
            # ChromaDB não suporta filtro por where sem entradas no período — ignora e continua
            continue

    return []  # Não achou nada em nenhum mês


def montar_contexto_longo(consulta: str) -> str:
    """
    Monta o bloco de contexto para injetar no system prompt.
    Combina fatos relevantes + histórico relevante.
    Retorna string vazia se não houver nada relevante.
    """
    _garantir_init()
    partes = []

    fatos = buscar_memoria(consulta, n=4)
    if fatos:
        partes.append(f"O que você sabe sobre o senhor:\n{fatos}")

    historico = buscar_historico_relevante(consulta, n=3)
    if historico:
        linhas = [f"  [{h['papel']}]: {h['mensagem']}" for h in historico]
        partes.append("Conversas anteriores relevantes:\n" + "\n".join(linhas))

    return "\n\n".join(partes)
