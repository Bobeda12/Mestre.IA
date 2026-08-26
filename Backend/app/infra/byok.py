"""BYOK — "traga sua própria chave" (Etapa 15). `ChaveUsuario` agrupa as
variantes de `chamar_fn`/`embed_fn` ligadas à chave que o jogador mandou no
header `X-Gemini-Key` (nunca persistida — só vive como closure de
`functools.partial` durante o request/BackgroundTask que a recebeu).

Extraído de `routers/game.py` (rodada de conserto) para ter um segundo
consumidor: `routers/character.py` e `routers/personagens.py` não liam esse
header nenhuma vez, então "trouxe minha chave" não cobria criar personagem,
gerar epitáfio nem exportar a crônica — só os turnos de jogo."""

import functools
from collections.abc import Callable
from typing import Any

from app.infra import embeddings, llm_client
from app.infra.settings import settings

# Modelo usado pro resumo rolante quando ligado à chave do jogador
# (`chamar_com_chave_usuario`), no mesmo tier barato de
# `settings.modelo_barato` ("gemini:gemini-3.5-flash-lite"), só que sem o
# prefixo "provedor:" (que `chamar_com_chave_usuario` já fixa em "gemini").
MODELO_BARATO_BYOK = settings.modelo_barato.rsplit(":", 1)[-1]


class ChaveUsuario:
    """Quando `chave` é `None` ou vazia, todos os campos ficam `None` e
    quem consome usa o próprio default (cadeia/chave do servidor)."""

    def __init__(self, chave: str | None) -> None:
        # String vazia não conta como "trouxe a própria chave" — um header
        # `X-Gemini-Key: ` (vazio) não deveria isentar o teto diário nem
        # tentar autenticar no Gemini com nada.
        self.presente = bool(chave)
        self.chamar_fn: Callable[..., Any] | None = None
        self.chamar_fn_stream: Callable[..., Any] | None = None
        self.chamar_fn_barato: Callable[..., Any] | None = None
        self.embed_fn: Callable[[str], list[float]] | None = None
        if self.presente:
            assert chave is not None
            self.chamar_fn = functools.partial(llm_client.chamar_com_chave_usuario, api_key=chave)
            self.chamar_fn_stream = functools.partial(llm_client.chamar_stream_com_chave_usuario, api_key=chave)
            self.chamar_fn_barato = functools.partial(
                llm_client.chamar_com_chave_usuario, api_key=chave, modelo=MODELO_BARATO_BYOK
            )
            self.embed_fn = functools.partial(embeddings.embed_um, api_key=chave)
