"""Langfuse (Etapa 9) — custo, latência e tokens por turno, visíveis.

`langfuse_client` é `None` sem as duas chaves configuradas (mesmo padrão de
`llm_client.client`/`groq_api_key`) — todo ponto de instrumentação em
`llm_client.py` já checa isso antes de abrir um span, então rodar sem conta
no Langfuse (dev local, CI) simplesmente não gera trace nenhuma, sem quebrar
nada."""

from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import Langfuse

from app.infra.settings import settings


def _build_client() -> Langfuse | None:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


langfuse_client = _build_client()


@contextmanager
def turno_span(*, personagem_id: int, usuario_id: int, turno: int) -> Iterator[None]:
    """Agrupa as (possivelmente várias — ADR-0007, ferramentas encadeadas)
    gerações de `llm_client._chamar_modelo` de um turno numa única trace,
    com `personagem_id`/`turno` como metadata — é isso que deixa custo por
    sessão (Etapa 9, Fase G) uma soma em vez de um cruzamento manual."""
    if langfuse_client is None:
        yield
        return
    with langfuse_client.start_as_current_observation(
        as_type="span",
        name="turno",
        metadata={"personagem_id": personagem_id, "usuario_id": usuario_id, "turno": turno},
    ):
        yield
