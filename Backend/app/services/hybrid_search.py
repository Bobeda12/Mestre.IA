"""Busca híbrida — BM25 (léxica) + similaridade de cosseno (densa), fundidas
por Reciprocal Rank Fusion (RRF) e, quando fizer sentido, penalizadas por
recência. É o motor reaproveitado por dois consumidores (Etapa 5):
`services/memory.py` (memória de longo prazo) e `services/rag_regras.py`
(RAG sobre a bíblia do mestre). Ver ADR-0010 para o porquê de vetor puro não
bastar sozinho — nomes próprios (de NPC, de local) são exatamente o caso em
que a busca léxica acerta e a densa erra."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.infra import embeddings

_TOKEN = re.compile(r"\w+", re.UNICODE)

# BM25 pondera um termo pela raridade dele no corpus (IDF) — sem filtrar
# preposição/artigo, um corpus pequeno (poucas seções de regra, poucos
# eventos de memória) deixa uma palavra comum como "com" pesar mais que um
# termo de conteúdo genuíno só porque calhou de aparecer numa seção e não
# nas outras. Lista fixa e curta: o domínio (português, textos curtos) não
# muda a ponto de justificar uma biblioteca de NLP só para isto.
_STOPWORDS = {
    "o", "a", "os", "as", "de", "da", "do", "das", "dos", "e", "é", "em",
    "um", "uma", "uns", "umas", "se", "que", "não", "para", "com", "na",
    "no", "nas", "nos", "ao", "aos", "à", "às", "por", "como", "mas", "ou",
    "seu", "sua", "seus", "suas", "isso", "isto", "ele", "ela",
}


@dataclass
class Documento:
    id: int
    texto: str
    embedding: list[float]
    turno: int | None = None


def _tokenizar(texto: str) -> list[str]:
    # `\w+` em vez de `str.split()`: sem isso, "adaga." e "adaga" nunca
    # batem no BM25 (correspondência é por token exato) — pontuação colada
    # à última palavra da frase é a norma em prosa, não exceção.
    return [t for t in _TOKEN.findall(texto.lower()) if t not in _STOPWORDS]


def busca_lexica(query: str, documentos: list[Documento]) -> list[int]:
    """Devolve os ids ordenados por relevância léxica (BM25). Não lança para
    corpus vazio — a lista de documentos de um personagem novo é vazia.

    Devolve `[]` (não uma ordem arbitrária) quando nenhum termo da query
    aparece em nenhum documento — BM25Okapi ainda devolve um vetor de
    scores todos em zero nesse caso, e ordenar zeros produz uma "vitória"
    do primeiro documento da lista só por causa da ordem de entrada, não de
    relevância nenhuma. Sem esse corte, essa ordem falsa entra na fusão RRF
    como se fosse um sinal de verdade e pode vencer o ranking denso
    genuíno (visto na prática: uma consulta sobre chuva ficando atrás da
    seção de combate, só porque nenhuma palavra da query batia literalmente
    em seção nenhuma — ver ADR-0010)."""
    if not documentos:
        return []
    bm25 = BM25Okapi([_tokenizar(d.texto) for d in documentos])
    scores = bm25.get_scores(_tokenizar(query))
    if max(scores, default=0) <= 0:
        return []
    ordenados = sorted(range(len(documentos)), key=lambda i: scores[i], reverse=True)
    return [documentos[i].id for i in ordenados]


def _cosseno(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        # Etapa 14 (ADR-0023) — eventos gravados antes da troca do modelo
        # local de embedding (384 dim) para a API do Gemini (768 dim) ainda
        # têm o vetor antigo. Dimensões diferentes nunca são comparáveis;
        # tratar como "sem similaridade" (em vez de deixar o zip() abaixo
        # levantar ValueError) degrada esse documento para busca só léxica,
        # sem derrubar a busca inteira.
        return 0.0
    produto = sum(x * y for x, y in zip(a, b, strict=True))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return produto / (norma_a * norma_b)


def busca_densa(query_embedding: list[float], documentos: list[Documento]) -> list[int]:
    pontuados = [(d.id, _cosseno(query_embedding, d.embedding)) for d in documentos]
    pontuados.sort(key=lambda par: par[1], reverse=True)
    return [id_ for id_, _ in pontuados]


def fusao_rrf(ranqueamentos: list[list[int]], k: int = 10) -> dict[int, float]:
    """Reciprocal Rank Fusion: cada lista contribui `1/(k + posição)` para o
    id — um documento bem colocado em qualquer uma das buscas sobe no
    resultado final, sem precisar normalizar as escalas de score bem
    diferentes do BM25 (não limitado) e do cosseno (-1..1).

    `k=10`, não o `k=60` "clássico" do paper original (Cormack et al.,
    pensado para milhares de resultados por lista): aqui as listas têm
    poucas dezenas de documentos (eventos de memória de uma partida,
    seções da bíblia) — um `k` grande demais achata a diferença de score
    entre a 1ª e a 3ª posição a ponto de o decaimento por recência dominar
    tudo sozinho (visto na prática rodando scripts/memory_recall.py)."""
    scores: dict[int, float] = {}
    for ranking in ranqueamentos:
        for posicao, id_ in enumerate(ranking):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + posicao + 1)
    return scores


def decaimento_recencia(
    scores: dict[int, float],
    documentos: list[Documento],
    turno_atual: int,
    meia_vida: int = 40,
    piso: float = 0.5,
) -> dict[int, float]:
    """Multiplica o score por um fator que cai pela metade a cada
    `meia_vida` turnos de distância — o que aconteceu há 3 turnos pesa mais
    que há 80 — mas nunca abaixo de `piso`: recência é um desempate, não um
    veto. Sem o piso, um evento muito antigo mas exatamente relevante
    (a única memória que realmente responde à pergunta) perde de um evento
    recente e irrelevante só por ser recente — o oposto do que "memória"
    deveria fazer (visto na prática rodando scripts/memory_recall.py, antes
    do piso existir: as 3 memórias mais recentes venciam toda consulta)."""
    por_id = {d.id: d for d in documentos}
    ajustado: dict[int, float] = {}
    for id_, score in scores.items():
        doc = por_id.get(id_)
        if doc is None or doc.turno is None:
            ajustado[id_] = score
            continue
        distancia = max(0, turno_atual - doc.turno)
        fator = piso + (1 - piso) * 0.5 ** (distancia / meia_vida)
        ajustado[id_] = score * fator
    return ajustado


def buscar(
    query: str,
    documentos: list[Documento],
    turno_atual: int | None = None,
    k: int = 5,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> list[Documento]:
    """Orquestra os quatro passos: léxica, densa, fusão RRF e (se
    `turno_atual` for informado) decaimento por recência. `embed_fn` é
    injetável para os testes usarem um embedding determinístico em vez de
    carregar o modelo real (ver tests/test_hybrid_search.py) — o padrão só
    é resolvido dentro da função (não no cabeçalho) para que um
    `monkeypatch.setattr(embeddings, "embed_um", ...)` em conftest.py
    também valha para quem chama `buscar` sem passar `embed_fn`."""
    if not documentos:
        return []
    embed_fn = embed_fn or embeddings.embed_um
    ranking_lexico = busca_lexica(query, documentos)
    ranking_denso = busca_densa(embed_fn(query), documentos)
    scores = fusao_rrf([ranking_lexico, ranking_denso])
    if turno_atual is not None:
        scores = decaimento_recencia(scores, documentos, turno_atual)

    ordenados = sorted(scores.items(), key=lambda par: par[1], reverse=True)
    por_id = {d.id: d for d in documentos}
    return [por_id[id_] for id_, _ in ordenados[:k]]
