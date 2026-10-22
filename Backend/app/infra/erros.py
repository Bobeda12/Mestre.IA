"""Alerta de erros não tratados (Sentry). Sem `SENTRY_DSN`, não faz nada."""

import sentry_sdk

from app.infra.settings import settings


def iniciar_alerta_de_erros() -> bool:
    """Liga o Sentry quando há DSN. Devolve se ligou.

    O texto que o jogador escreve é privado: `send_default_pii=False` tira
    cookies e IP, e `max_request_body_size="never"` impede o corpo do pedido
    (a ação do jogador) de ir junto com o erro. Sem traces: aqui o Sentry só
    avisa que algo quebrou; custo e latência por turno já estão no Langfuse.
    """
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
    )
    return True
