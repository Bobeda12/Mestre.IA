"""Envio de e-mail via Resend (Etapa 10, A-2) — só a confirmação de conta,
por ora. Mesmo padrão condicional do Google (`services/auth.google_disponivel`)
e do Langfuse (`infra/tracing.py`): sem `RESEND_API_KEY` configurada, a
função loga o link em vez de falhar — dev continua funcionando sem conta
nenhuma, e é assim que o autor confirma o próprio e-mail em ambiente local."""

import logging

import resend

from app.infra.settings import settings

logger = logging.getLogger(__name__)


def enviar_email_confirmacao(destinatario: str, link: str) -> None:
    if not settings.resend_api_key:
        logger.info("[dev] link de confirmação para %s: %s", destinatario, link)
        return
    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [destinatario],
            "subject": "Confirme seu e-mail — Mestre.IA",
            "html": (
                "<p>Confirme seu e-mail para continuar jogando Mestre.IA:</p>"
                f'<p><a href="{link}">{link}</a></p>'
                "<p>O link vale por 24 horas.</p>"
            ),
        }
    )
