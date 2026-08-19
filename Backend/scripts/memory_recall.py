"""Mede recall@k da memória de longo prazo (PLANO_MESTRE.md, Etapa 5): num
conjunto fixo de eventos sintéticos com uma consulta -> id esperado
conhecidos, compara (a) busca densa pura contra (b) busca híbrida (BM25 +
densa, fundidas por RRF, com decaimento por recência).

Ao contrário de scripts/tool_call_accuracy.py, roda 100% offline —
embeddings via `fastembed` (modelo local, sem chamada de rede depois do
primeiro download) — por isso pode rodar aqui e, futuramente, virar um
teste real (ver tests/test_hybrid_search.py, que já cobre o mecanismo com
embeddings falsos; este script usa o modelo de verdade).

Uso: `uv run python scripts/memory_recall.py`
"""

import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra import embeddings  # noqa: E402
from app.services import hybrid_search  # noqa: E402
from app.services.hybrid_search import Documento  # noqa: E402


@dataclass
class EventoFixo:
    id: int
    texto: str
    turno: int


EVENTOS = [
    EventoFixo(1, "O taverneiro Gundren serve cerveja e reclama dos impostos da vila.", turno=2),
    EventoFixo(2, "O herói insulta o taverneiro Gundren na frente de todos.", turno=5),
    EventoFixo(3, "Um goblin ataca da sombra com uma adaga enferrujada.", turno=8),
    EventoFixo(4, "O ferreiro Halia forja uma nova espada para o herói.", turno=12),
    EventoFixo(5, "Chuva forte cai sobre o telhado da estalagem durante a noite.", turno=15),
    EventoFixo(6, "O herói promete ao ferreiro Halia trazer minério da mina.", turno=18),
    EventoFixo(7, "Um lobo solitário uiva ao longe, na Floresta das Sombras.", turno=22),
    EventoFixo(8, "O herói encontra um mapa rasgado apontando para uma masmorra.", turno=27),
    EventoFixo(9, "O taverneiro Gundren se recusa a servir o herói, ainda ofendido.", turno=31),
    EventoFixo(10, "O herói entrega o minério prometido ao ferreiro Halia.", turno=35),
    EventoFixo(11, "Um esqueleto guarda a entrada da masmorra com uma lança quebrada.", turno=40),
    EventoFixo(12, "O clima muda: neblina densa cobre a Vila de Phandalin.", turno=44),
    EventoFixo(13, "O herói se desculpa com o taverneiro Gundren, oferecendo ouro.", turno=48),
    EventoFixo(14, "O ferreiro Halia entrega a espada prometida, mais afiada que antes.", turno=52),
    EventoFixo(15, "O herói mata o goblin da sombra com um golpe certeiro.", turno=55),
    # Par adversarial (ADR-0010): um nome próprio raro contra um distrator
    # semanticamente parecido, sem o nome. Embedding denso tende a
    # confundir "alguém tocando música" — nome próprio fora do vocabulário
    # do modelo vira subtoken genérico; BM25 acerta o nome exato de cara.
    EventoFixo(16, "O bardo Xanthrel canta uma balada sombria sobre dragões na taverna.", turno=58),
    EventoFixo(17, "Um músico desconhecido toca alaúde perto da fogueira do acampamento.", turno=60),
]

# query -> id do evento que uma busca "boa" deveria trazer entre os top-k.
CONSULTAS = {
    "o que aconteceu com o taverneiro Gundren?": 13,  # o evento mais recente e mais relevante sobre ele
    "o herói prometeu algo ao ferreiro Halia?": 6,
    "o mapa da masmorra": 8,
    "o goblin da sombra": 15,
    "clima e neblina na vila": 12,
    "o que o Xanthrel estava fazendo?": 16,
}

K = 1


def _recall_em_k(ranking_por_consulta: dict[str, list[int]]) -> float:
    acertos = sum(1 for consulta, ids in ranking_por_consulta.items() if CONSULTAS[consulta] in ids)
    return acertos / len(CONSULTAS)


def rodar() -> None:
    documentos = [
        Documento(id=e.id, texto=e.texto, embedding=embeddings.embed_um(e.texto), turno=e.turno) for e in EVENTOS
    ]
    turno_atual = max(e.turno for e in EVENTOS) + 1

    denso_apenas: dict[str, list[int]] = {}
    hibrido: dict[str, list[int]] = {}

    for consulta in CONSULTAS:
        query_embedding = embeddings.embed_um(consulta)
        ranking_denso = hybrid_search.busca_densa(query_embedding, documentos)[:K]
        denso_apenas[consulta] = ranking_denso

        encontrados = hybrid_search.buscar(consulta, documentos, turno_atual=turno_atual, k=K)
        hibrido[consulta] = [d.id for d in encontrados]

        esperado = CONSULTAS[consulta]
        print(f"\nConsulta: {consulta!r} (esperado: id={esperado})")
        print(f"  denso apenas : {ranking_denso}  {'OK' if esperado in ranking_denso else 'MISS'}")
        print(f"  híbrido      : {hibrido[consulta]}  {'OK' if esperado in hibrido[consulta] else 'MISS'}")

    print(f"\nrecall@{K} denso apenas : {_recall_em_k(denso_apenas):.0%}")
    print(f"recall@{K} híbrido      : {_recall_em_k(hibrido):.0%}")


if __name__ == "__main__":
    rodar()
