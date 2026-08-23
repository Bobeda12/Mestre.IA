"""RAG sobre a bíblia do mestre (Etapa 5). Até aqui, `narrator.montar_contexto`
despejava `regras.get_biblia()` inteira em todo turno — barato porque o
arquivo é pequeno hoje, mas é exatamente o padrão que não escala (e o que o
PLANO_MESTRE.md pede para medir). A bíblia é quebrada em seções pelos
próprios cabeçalhos `[EM CAIXA ALTA]` que ela já usa.

Nem toda seção é "regra consultável": a lei da verossimilhança, a voz do
mestre (Etapa 11, B-9), os momentos de alto impacto e o protocolo de
arbitragem definem COMO narrar em qualquer cena, não uma regra específica
de uma situação — ficam sempre presentes.
`COMBATE TÁTICO E LETAL`, `SISTEMA DE CONSEQUÊNCIA SOCIAL` e `GESTÃO DE
TEMPO E CLIMA` são situacionais: só entram quando relevantes para a ação do
turno, via a mesma busca híbrida de services/memory.py (ver ADR-0010)."""

import re
from collections.abc import Callable

from app.infra import embeddings
from app.infra.data_manager import regras
from app.services import hybrid_search

_CABECALHO = re.compile(r"^\[([^\]]+)\]\s*$", re.MULTILINE)
_TITULO = re.compile(r"^\[([^\]]+)\]")

# Diretrizes de COMO narrar, não regras de uma situação específica — ficam
# sempre no contexto. O resto da bíblia é o corpus consultável por RAG.
_SECOES_SEMPRE = {
    "DIRETRIZ PRIMEIRA: A LEI DA VEROSSIMILHANÇA",
    "A VOZ DO MESTRE",
    "MOMENTOS DE ALTO IMPACTO",
    "PROTOCOLO DE ARBITRAGEM",
}

_secoes_cache: list[str] | None = None
_documentos_cache: dict[int, list[hybrid_search.Documento]] = {}


def _dividir_em_secoes(texto: str) -> list[str]:
    partes = _CABECALHO.split(texto)
    # re.split com grupo de captura intercala: ['', titulo1, corpo1, titulo2, corpo2, ...]
    return [f"[{titulo}]{corpo}".strip() for titulo, corpo in zip(partes[1::2], partes[2::2], strict=True)]


def _titulo(secao: str) -> str:
    m = _TITULO.match(secao)
    return m.group(1) if m else ""


def _secoes() -> list[str]:
    global _secoes_cache
    if _secoes_cache is None:
        _secoes_cache = _dividir_em_secoes(regras.get_biblia())
    return _secoes_cache


def _sempre() -> list[str]:
    return [s for s in _secoes() if _titulo(s) in _SECOES_SEMPRE]


def _consultaveis() -> list[str]:
    return [s for s in _secoes() if _titulo(s) not in _SECOES_SEMPRE]


def _documentos(embed_fn: Callable[[str], list[float]] | None = None) -> list[hybrid_search.Documento]:
    embed_fn = embed_fn or embeddings.embed_um
    consultaveis = _consultaveis()
    chave = id(embed_fn)
    cache = _documentos_cache.get(chave)
    if cache is None or len(cache) != len(consultaveis):
        cache = [
            hybrid_search.Documento(id=i, texto=secao, embedding=embed_fn(secao))
            for i, secao in enumerate(consultaveis)
        ]
        _documentos_cache[chave] = cache
    return cache


def regras_relevantes(
    query: str, k: int = 2, embed_fn: Callable[[str], list[float]] | None = None
) -> list[str]:
    """Sempre inclui as diretrizes de narração; acrescenta as `k` seções
    situacionais mais relevantes para `query`. Se a bíblia não tiver seções
    reconhecíveis (arquivo ausente/malformado, ver DataManager._load_text),
    cai para o texto inteiro — degradação igual à de antes desta etapa."""
    embed_fn = embed_fn or embeddings.embed_um
    sempre = _sempre()
    consultaveis = _consultaveis()
    if not consultaveis:
        texto = regras.get_biblia()
        return sempre or ([texto] if texto else [])

    documentos = _documentos(embed_fn)
    encontrados = hybrid_search.buscar(query, documentos, turno_atual=None, k=k, embed_fn=embed_fn)
    return sempre + [d.texto for d in encontrados]
