"""Envio de e-mail (Etapa 10, A-2) — só a confirmação de conta, por ora.
Mesmo padrão condicional do Google (`services/auth.google_disponivel`) e
do Langfuse (`infra/tracing.py`): sem nenhum método configurado, a função
loga o link em vez de falhar — dev continua funcionando sem conta nenhuma.

Três métodos, nessa ordem de prioridade:
0. **API do Gmail** (`gmail_refresh_token`) — HTTPS, porta 443. É o único que
   funciona no Render grátis, que bloqueia as portas SMTP. Sai da mesma conta
   Gmail, então mantém a boa entrega do método abaixo.
1. **SMTP do Gmail** (`smtp_email`/`smtp_senha_app`) — autentica como uma
   conta Gmail de verdade via "senha de app". A reputação de entrega é da
   conta, não de um provedor de e-mail transacional compartilhado — é
   assim que se evita cair em spam sem precisar verificar um domínio
   próprio (que tem custo).
2. **Resend** (`resend_api_key`) — mantido como alternativa; o remetente
   de teste (`onboarding@resend.dev`) funciona sem domínio verificado, mas
   cai em spam com frequência por ser compartilhado entre milhares de
   contas, sem SPF/DKIM alinhado a este projeto especificamente."""

import base64
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

import httpx
import resend

from app.infra.settings import settings

logger = logging.getLogger(__name__)

_ASSUNTO_CONFIRMACAO = "Confirme seu e-mail no Mestre.IA"

# Visual do jogo (pergaminho e dourado sobre fundo escuro), feito para e-mail:
# tabelas, CSS inline e nenhuma imagem (clientes bloqueiam imagens e fontes da
# web). A cor de fundo vai em `bgcolor` além do CSS, porque alguns clientes
# ignoram o `background`. Há sempre o link por extenso e uma versão em texto
# puro, que ajudam tanto a entrega quanto quem não vê HTML.
_HTML_CONFIRMACAO = """<!doctype html>
<html lang="pt-BR">
<body style="margin:0;padding:0;background:#0f0e0b;" bgcolor="#0f0e0b">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">
    Falta um passo para a sua aventura começar. O link vale por 24 horas.
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#0f0e0b"
         style="background:#0f0e0b;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0" bgcolor="#1a1712"
             style="max-width:520px;width:100%;background:#1a1712;border:2px solid #c5a059;">
        <tr><td align="center" style="padding:32px 32px 8px 32px;">
          <div style="font-family:Georgia,'Times New Roman',serif;font-size:13px;letter-spacing:4px;
                      color:#c5a059;">&mdash;&nbsp; RPG NARRADO POR IA &nbsp;&mdash;</div>
          <div style="font-family:Georgia,'Times New Roman',serif;font-size:34px;font-weight:bold;
                      color:#f3ead6;margin-top:10px;letter-spacing:2px;">
            MESTRE<span style="color:#c5a059;">.IA</span>
          </div>
        </td></tr>
        <tr><td style="padding:8px 32px;"><div style="height:2px;background:#4a3b2a;"></div></td></tr>
        <tr><td style="padding:16px 32px 8px 32px;font-family:Georgia,'Times New Roman',serif;
                       font-size:17px;line-height:1.6;color:#d4c5a9;">
          <p style="margin:0 0 14px 0;color:#f3ead6;font-size:20px;">Falta um passo para a sua aventura começar.</p>
          <p style="margin:0;">Confirme seu e-mail para guardar seus heróis e continuar de onde parou.</p>
        </td></tr>
        <tr><td align="center" style="padding:24px 32px;">
          <a href="{link}" target="_blank"
             style="display:inline-block;background:#c5a059;color:#0f0e0b;text-decoration:none;
                    font-family:Georgia,'Times New Roman',serif;font-size:16px;font-weight:bold;
                    letter-spacing:1px;padding:14px 32px;border:2px solid #f3ead6;">
            CONFIRMAR MEU E-MAIL
          </a>
        </td></tr>
        <tr><td style="padding:0 32px 8px 32px;font-family:Georgia,'Times New Roman',serif;
                       font-size:13px;line-height:1.6;color:#9c8f77;">
          O link vale por 24 horas. Se o botão não funcionar, copie e cole este endereço no navegador:
          <div style="margin-top:8px;word-break:break-all;color:#c5a059;font-size:12px;">{link}</div>
        </td></tr>
        <tr><td style="padding:24px 32px 32px 32px;font-family:Georgia,'Times New Roman',serif;
                       font-size:12px;line-height:1.6;color:#7d725f;">
          Você recebeu esta mensagem porque alguém criou uma conta no Mestre.IA com este e-mail.
          Se não foi você, pode ignorar: nada acontece sem o clique.<br>
          Mestre.IA é um projeto independente, em fase de testes.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

_TEXTO_CONFIRMACAO = (
    "MESTRE.IA\n\n"
    "Falta um passo para a sua aventura começar.\n\n"
    "Confirme seu e-mail para guardar seus heróis e continuar de onde parou:\n\n{link}\n\n"
    "O link vale por 24 horas.\n\n"
    "Você recebeu esta mensagem porque alguém criou uma conta no Mestre.IA com este e-mail. "
    "Se não foi você, pode ignorar: nada acontece sem o clique.\n\n"
    "Mestre.IA é um projeto independente, em fase de testes."
)


# Todo método de rede tem tempo limite: sem ele, uma porta bloqueada deixava o
# cadastro pendurado para sempre (achado ao vivo no lançamento, ver diário 0062).
_TEMPO_LIMITE_S = 15


class ErroEnvioEmail(Exception):
    """O e-mail não saiu (rede, credencial, cota). O router transforma em 503."""


def _montar_mensagem(destinatario: str, link: str, email_remetente: str) -> MIMEMultipart:
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
    return msg


def _enviar_via_gmail_api(destinatario: str, link: str, remetente: str, refresh_token: str) -> None:
    token = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=_TEMPO_LIMITE_S,
    )
    token.raise_for_status()
    msg = _montar_mensagem(destinatario, link, remetente)
    bruto = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    resposta = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
        json={"raw": bruto},
        timeout=_TEMPO_LIMITE_S,
    )
    resposta.raise_for_status()


def _enviar_via_smtp(destinatario: str, link: str, email_remetente: str, senha_app: str) -> None:
    msg = _montar_mensagem(destinatario, link, email_remetente)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=_TEMPO_LIMITE_S) as servidor:
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
    try:
        if settings.gmail_refresh_token and settings.gmail_remetente:
            _enviar_via_gmail_api(destinatario, link, settings.gmail_remetente, settings.gmail_refresh_token)
        elif settings.smtp_email and settings.smtp_senha_app:
            _enviar_via_smtp(destinatario, link, settings.smtp_email, settings.smtp_senha_app)
        elif settings.resend_api_key:
            _enviar_via_resend(destinatario, link)
        else:
            logger.info("[dev] link de confirmação para %s: %s", destinatario, link)
    except httpx.HTTPStatusError as erro:
        # O motivo de verdade vem no corpo (ex.: `invalid_grant`, `invalid_client`);
        # só o "400 Bad Request" não diz se o erro é do token ou do cliente OAuth.
        # O corpo de erro do Google não traz segredos.
        logger.error(
            "falha ao enviar e-mail de confirmação: %s: %s | resposta: %s",
            type(erro).__name__,
            erro,
            erro.response.text[:300],
        )
        raise ErroEnvioEmail(str(erro)) from erro
    except Exception as erro:
        logger.error("falha ao enviar e-mail de confirmação: %s: %s", type(erro).__name__, erro)
        raise ErroEnvioEmail(str(erro)) from erro
