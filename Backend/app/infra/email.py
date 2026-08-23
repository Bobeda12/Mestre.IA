"""Envio de e-mail (Etapa 10, A-2) — só a confirmação de conta, por ora.
Mesmo padrão condicional do Google (`services/auth.google_disponivel`) e
do Langfuse (`infra/tracing.py`): sem nenhum método configurado, a função
loga o link em vez de falhar — dev continua funcionando sem conta nenhuma.

Dois métodos, nessa ordem de prioridade:
1. **SMTP do Gmail** (`smtp_email`/`smtp_senha_app`) — autentica como uma
   conta Gmail de verdade via "senha de app". A reputação de entrega é da
   conta, não de um provedor de e-mail transacional compartilhado — é
   assim que se evita cair em spam sem precisar verificar um domínio
   próprio (que tem custo).
2. **Resend** (`resend_api_key`) — mantido como alternativa; o remetente
   de teste (`onboarding@resend.dev`) funciona sem domínio verificado, mas
   cai em spam com frequência por ser compartilhado entre milhares de
   contas, sem SPF/DKIM alinhado a este projeto especificamente."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

import resend

from app.infra.settings import settings

logger = logging.getLogger(__name__)

_ASSUNTO_CONFIRMACAO = "Confirme seu e-mail no Mestre.IA"

# Deliberadamente simples — nada de botão grande, card ou cor de marca
# (Etapa 10, achado ao vivo): um e-mail parecido com "card de marketing",
# vindo de uma conta nova, é exatamente o padrão que o filtro de spam do
# Gmail mais desconfia. Texto corrido com um link normal, como uma pessoa
# escreveria, tem taxa de entrega melhor até a conta construir reputação
# própria (o que só acontece com tempo/uso, não tem atalho técnico).
_HTML_CONFIRMACAO = """\
<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#1a1a1a;">
  <p>Oi!</p>
  <p>Confirme seu e-mail para continuar jogando o Mestre.IA:</p>
  <p><a href="{link}">{link}</a></p>
  <p>O link vale por 24 horas.</p>
  <p>Se você não criou essa conta, pode ignorar esta mensagem.</p>
</div>
"""

_TEXTO_CONFIRMACAO = (
    "Oi!\n\n"
    "Confirme seu e-mail para continuar jogando o Mestre.IA:\n\n{link}\n\n"
    "O link vale por 24 horas.\n\n"
    "Se você não criou essa conta, pode ignorar esta mensagem."
)


def _enviar_via_smtp(destinatario: str, link: str, email_remetente: str, senha_app: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = _ASSUNTO_CONFIRMACAO
    msg["From"] = f"Mestre.IA <{email_remetente}>"
    msg["To"] = destinatario
    # `Date`/`Message-ID` não saem sozinhos do `smtplib` — só o servidor de
    # relay às vezes preenche, e a ausência deles é mais um sinal que
    # classificador de spam usa (e-mail "de verdade" sempre tem os dois).
    # Domínio do Message-ID é o do remetente, não um genérico — RFC 5322.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=email_remetente.split("@")[-1])
    # Texto puro primeiro, HTML depois — clientes de e-mail usam a ÚLTIMA
    # parte que conseguem renderizar, texto puro é o fallback (RFC 2046).
    msg.attach(MIMEText(_TEXTO_CONFIRMACAO.format(link=link), "plain"))
    msg.attach(MIMEText(_HTML_CONFIRMACAO.format(link=link), "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_porta) as servidor:
        servidor.starttls()
        servidor.login(email_remetente, senha_app)
        servidor.send_message(msg)


def _enviar_via_resend(destinatario: str, link: str) -> None:
    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [destinatario],
            "subject": _ASSUNTO_CONFIRMACAO,
            "html": _HTML_CONFIRMACAO.format(link=link),
            "text": _TEXTO_CONFIRMACAO.format(link=link),
        }
    )


def enviar_email_confirmacao(destinatario: str, link: str) -> None:
    if settings.smtp_email and settings.smtp_senha_app:
        _enviar_via_smtp(destinatario, link, settings.smtp_email, settings.smtp_senha_app)
    elif settings.resend_api_key:
        _enviar_via_resend(destinatario, link)
    else:
        logger.info("[dev] link de confirmação para %s: %s", destinatario, link)
