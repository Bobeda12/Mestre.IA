"""Memória em três camadas (Etapa 5, PLANO_MESTRE.md §6/Etapa 5):

- **Curto prazo:** `contexto_recente` — slice cru das últimas mensagens
  (existe desde a Etapa 1, sem mudança).
- **Médio prazo:** `atualizar_resumo_rolante` — a cada K turnos, comprime o
  que saiu da janela curta em campos estruturados (domain/memoria.py).
- **Longo prazo:** `registrar_evento` + `memorias_relevantes` — eventos
  persistidos em `EventoMemoria` e recuperados por busca híbrida
  (services/hybrid_search.py), sempre filtrados por `personagem_id`."""

import json
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.domain.memoria import ResumoRolante
from app.infra import embeddings, llm_client
from app.infra.db import EventoMemoria, Personagem
from app.infra.llm_client import ErroMestre
from app.infra.settings import settings
from app.services import hybrid_search


def contexto_recente(historico: list[dict], n: int = 4) -> list[dict]:
    return list(historico)[-n:]


def registrar_evento(
    db: Session,
    personagem_id: int,
    turno: int,
    tipo: str,
    texto: str,
    personagens: list[str] | None = None,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> EventoMemoria:
    embed_fn = embed_fn or embeddings.embed_um
    evento = EventoMemoria(
        personagem_id=personagem_id,
        turno=turno,
        tipo=tipo,
        texto=texto,
        personagens_citados=personagens or [],
        embedding=embed_fn(texto),
    )
    db.add(evento)
    db.commit()
    return evento


def memorias_relevantes(
    db: Session,
    personagem_id: int,
    query: str,
    turno_atual: int,
    k: int = 4,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> list[str]:
    """Busca híbrida sobre os eventos do personagem — nunca de outro (o
    filtro por `personagem_id` acontece na query, antes de qualquer busca,
    para memória nunca vazar entre personagens/sessões)."""
    embed_fn = embed_fn or embeddings.embed_um
    eventos = db.query(EventoMemoria).filter(EventoMemoria.personagem_id == personagem_id).all()
    documentos = [
        hybrid_search.Documento(id=e.id, texto=e.texto, embedding=e.embedding, turno=e.turno) for e in eventos
    ]
    encontrados = hybrid_search.buscar(query, documentos, turno_atual=turno_atual, k=k, embed_fn=embed_fn)
    return [d.texto for d in encontrados]


_PROMPT_RESUMO = """Você resume eventos de uma sessão de RPG em campos estruturados, em português.

Resumo acumulado até agora (JSON): {resumo_atual}

Novos eventos desta janela, em ordem:
{eventos}

Responda APENAS com um JSON de quatro listas de frases curtas — só o que é
NOVO nesta janela (não repita o que já está no resumo acumulado acima):
{{"fatos_estabelecidos": [...], "npcs_conhecidos": [...], "promessas_feitas": [...], "mudancas_no_mundo": [...]}}
"""


def _mesclar(antigos: list[str], novos: list[str]) -> list[str]:
    vistos = set(antigos)
    extras = [item for item in novos if item not in vistos]
    return antigos + extras


def atualizar_resumo_rolante(heroi: Personagem, k_turnos: int = 8) -> bool:
    """Quando `k_turnos` turnos (pares user+assistant) saíram da janela
    curta desde o último checkpoint, comprime essa fatia num resumo
    estruturado, usando o modelo mais barato da cadeia de fallback
    (services/memory.py não precisa da qualidade do modelo principal para
    isto). Muta `heroi.resumo_rolante`/`heroi.turno_resumido_ate` in place
    — quem chama ainda precisa que o objeto seja commitado (mesmo padrão de
    reatribuição de coluna JSON do resto do projeto, ver Lição 03).

    Devolve se o resumo foi atualizado; uma falha do modelo (ErroMestre,
    JSON inválido) não derruba o turno — o resumo antigo continua valendo,
    e a próxima chamada tenta de novo com uma janela maior."""
    historico = list(heroi.historico_chat)
    pendentes = len(historico) - heroi.turno_resumido_ate
    if pendentes < k_turnos * 2:
        return False

    fatia = historico[heroi.turno_resumido_ate : heroi.turno_resumido_ate + k_turnos * 2]
    eventos_texto = "\n".join(f"- {m['role']}: {m['content']}" for m in fatia if m.get("content"))
    resumo_atual = ResumoRolante.model_validate(heroi.resumo_rolante or {})

    prompt = _PROMPT_RESUMO.format(resumo_atual=resumo_atual.model_dump_json(), eventos=eventos_texto)
    try:
        resp = llm_client.chamar_modelo_unico(
            settings.modelos_fallback[-1],
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        novo = json.loads(resp.choices[0].message.content)
        resumo_novo = ResumoRolante.model_validate(novo)
    except (ErroMestre, json.JSONDecodeError, AttributeError, TypeError):
        return False

    heroi.resumo_rolante = ResumoRolante(
        fatos_estabelecidos=_mesclar(resumo_atual.fatos_estabelecidos, resumo_novo.fatos_estabelecidos),
        npcs_conhecidos=_mesclar(resumo_atual.npcs_conhecidos, resumo_novo.npcs_conhecidos),
        promessas_feitas=_mesclar(resumo_atual.promessas_feitas, resumo_novo.promessas_feitas),
        mudancas_no_mundo=_mesclar(resumo_atual.mudancas_no_mundo, resumo_novo.mudancas_no_mundo),
    ).model_dump()
    heroi.turno_resumido_ate += k_turnos * 2
    return True
