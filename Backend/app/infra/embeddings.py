"""Cliente de embeddings via API do Gemini (`gemini-embedding-001`) — ver
ADR-0023. Antes rodava local via `fastembed`/ONNX Runtime: ~520 MB
residentes assim que o modelo carregava, incompatível com qualquer free
tier de hospedagem em 2026 (todos com teto de 512 MB). Trocado por uma
chamada de rede, mesma interface pública (`embed`, `embed_um`) — os
consumidores (services/hybrid_search.py, services/memory.py,
services/rag_regras.py) recebem `embed_fn` como parâmetro injetável, sem
mudança nenhuma no contrato deles.

REST puro via `httpx` (já é dependência do projeto), não o SDK
`openai`/`google-genai`: a camada de compatibilidade OpenAI do Gemini não
documenta com clareza o suporte a `outputDimensionality` — o endpoint
nativo (`:embedContent`) documenta o contrato exato, sem ambiguidade.

Falha (sem chave configurada, rate limit, timeout, erro do servidor) nunca
derruba o turno: degrada para um vetor de zeros, que `hybrid_search._cosseno`
já trata como "sem similaridade nenhuma" — o documento afetado ainda é
recuperável por busca léxica (BM25), só perde o sinal denso."""

from __future__ import annotations

import logging
import math

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.infra.settings import settings

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-embedding-001"
# Um dos três valores recomendados pela doc (128-3072, recomendados
# 768/1536/3072) — o dobro da dimensão do modelo local anterior (384),
# ainda pequeno para guardar como JSON (services/db.py:EventoMemoria.embedding).
EMBED_DIM = 768
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:embedContent"
_VETOR_ZERO = [0.0] * EMBED_DIM


def _erro_transitorio(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception(_erro_transitorio),
    reraise=True,
)
def _chamar_api(texto: str) -> list[float]:
    resp = httpx.post(
        _URL,
        headers={"x-goog-api-key": settings.gemini_api_key or "", "Content-Type": "application/json"},
        json={
            "content": {"parts": [{"text": texto}]},
            # Achado ao vivo (Etapa 14, testando contra a API de verdade,
            # não só a doc): a doc atual descreve `taskType`/
            # `outputDimensionality` no topo do corpo como deprecados a
            # favor de um bloco aninhado `embedContentConfig` — mas contra
            # esta API (v1beta) o bloco aninhado é aceito (200 OK) e
            # SILENCIOSAMENTE IGNORADO: a resposta vem sempre com 3072
            # dimensões, sem erro nenhum que denunciasse isso. Os campos no
            # topo (a forma "deprecada") são os que realmente valem hoje.
            "taskType": "RETRIEVAL_DOCUMENT",
            "outputDimensionality": EMBED_DIM,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    valores = resp.json()["embedding"]["values"]
    # outputDimensionality != 3072 exige normalização manual (doc da API) —
    # o modelo já entrega o vetor de 3072 normalizado e só trunca depois;
    # truncar sem renormalizar deixa a norma < 1, o que distorce a
    # similaridade de cosseno se comparado a um vetor à parte não truncado.
    norma = math.sqrt(sum(x * x for x in valores))
    return valores if norma == 0 else [x / norma for x in valores]


def embed(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY não configurada — embeddings degradados para busca só léxica (BM25).")
        return [_VETOR_ZERO for _ in textos]
    resultado = []
    for texto in textos:
        try:
            resultado.append(_chamar_api(texto))
        except Exception:
            logger.warning(
                "Falha ao chamar a API de embeddings — degradando este texto para vetor zero.", exc_info=True
            )
            resultado.append(_VETOR_ZERO)
    return resultado


def embed_um(texto: str) -> list[float]:
    return embed([texto])[0]
