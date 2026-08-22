"""Login por senha e/ou Google (Etapa 8, ADR-0014).

Três peças, com responsabilidades separadas:
- **Senha**: PBKDF2-HMAC-SHA256 com salt aleatório (`hash_senha`/`verificar_senha`)
  — não `bcrypt`/`argon2` porque não deu para instalar nada nesta sessão (sem
  rede); PBKDF2 é aprovado pelo NIST e já vem na `hashlib` da stdlib.
- **Google OAuth**: authorization code flow — troca o `code` por um
  `access_token`, e usa esse token pra perguntar ao próprio Google "quem é
  essa conta" (`userinfo`). Nunca decodifica/valida o `id_token` (JWT)
  localmente: perguntar à API do Google via HTTPS já é a fonte da verdade,
  e evita reimplementar verificação de assinatura RS256 e busca de chaves
  públicas (JWKS) à mão.
- **Cookie de sessão**: idêntico ao desenhado antes da troca de magic link
  por senha — HMAC-SHA256 assinado à mão, sem tabela própria. O mecanismo
  de sessão não muda com o mecanismo de login.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infra.db import Usuario, get_db
from app.infra.settings import settings

logger = logging.getLogger(__name__)

NOME_COOKIE_SESSAO = "sessao"
NOME_COOKIE_OAUTH_STATE = "oauth_state"
_TTL_COOKIE = timedelta(days=30)
_TTL_OAUTH_STATE = timedelta(minutes=10)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _agora() -> datetime:
    # SQLite (via SQLAlchemy) guarda DateTime sem timezone — comparar um
    # datetime "aware" (datetime.now(UTC)) contra um valor lido do banco
    # levantaria TypeError. Tudo neste módulo é UTC "naive" de propósito,
    # por consistência com o que volta das queries.
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Senha
# ---------------------------------------------------------------------------

_PBKDF2_ITERACOES = 260_000  # mesma ordem de grandeza recomendada pelo Django (2024)


def hash_senha(senha: str) -> str:
    salt = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERACOES)
    return f"pbkdf2_sha256${_PBKDF2_ITERACOES}${salt}${derivado.hex()}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, iteracoes_str, salt, hash_esperado = hash_armazenado.split("$")
    except ValueError:
        return False
    if algoritmo != "pbkdf2_sha256":
        return False
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), int(iteracoes_str))
    return hmac.compare_digest(derivado.hex(), hash_esperado)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


def google_disponivel() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def construir_url_autorizacao_google(state: str) -> str:
    params = {
        "client_id": settings.google_client_id or "",
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{httpx.QueryParams(params)}"


def trocar_code_por_userinfo(code: str) -> dict:
    """Troca o `code` do redirect por um `access_token`, e usa esse token
    pra perguntar ao Google quem é o dono da conta. Levanta `HTTPException`
    com uma mensagem já pronta pro jogador em qualquer etapa que falhar —
    não deixa o erro cru do Google vazar pra resposta."""
    resp_token = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10.0,
    )
    if resp_token.status_code >= 400:
        logger.error(
            "Falha ao trocar code por token no Google (status %s): %s",
            resp_token.status_code,
            resp_token.text,
        )
        raise HTTPException(status_code=400, detail="Não deu para confirmar o login com o Google.")

    access_token = resp_token.json().get("access_token")
    resp_userinfo = httpx.get(
        GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10.0
    )
    if resp_userinfo.status_code >= 400:
        raise HTTPException(status_code=400, detail="Não deu para confirmar o login com o Google.")

    dados = resp_userinfo.json()
    if not dados.get("email_verified", True):
        # O próprio Google já filtra a maioria dos casos, mas um e-mail não
        # verificado não deveria conseguir criar/entrar numa conta aqui.
        raise HTTPException(status_code=400, detail="O e-mail dessa conta Google não está verificado.")
    return dados


def obter_ou_criar_usuario_google(db: Session, google_sub: str, email: str) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.google_sub == google_sub).first()
    if usuario is not None:
        return usuario

    # Já existe conta com esse e-mail (criada por senha) — vincula o Google
    # a ela em vez de criar uma segunda conta pro mesmo e-mail.
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is not None:
        usuario.google_sub = google_sub
    else:
        usuario = Usuario(email=email, google_sub=google_sub)
        db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


# ---------------------------------------------------------------------------
# Cookies (sessão e state do OAuth) — HMAC-SHA256 assinado à mão. Um
# serializer dedicado (`itsdangerous`) faria a mesma coisa; não deu para
# instalar nesta sessão (sem rede). Ver ADR-0014.
# ---------------------------------------------------------------------------


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64_decode(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(payload: dict) -> str:
    corpo = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    assinatura = hmac.new(settings.session_secret.encode("utf-8"), corpo.encode("ascii"), hashlib.sha256).digest()
    return f"{corpo}.{_b64(assinatura)}"


def _verificar(valor: str) -> dict | None:
    try:
        corpo, assinatura = valor.split(".", 1)
    except ValueError:
        return None
    esperada = hmac.new(settings.session_secret.encode("utf-8"), corpo.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64(esperada), assinatura):
        return None
    try:
        return json.loads(_b64_decode(corpo))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def criar_cookie_sessao(usuario_id: int) -> str:
    return _assinar({"usuario_id": usuario_id, "emitido_em": _agora().isoformat()})


def _ler_cookie_sessao(valor: str) -> int | None:
    dados = _verificar(valor)
    if dados is None:
        return None
    usuario_id, emitido_em_str = dados.get("usuario_id"), dados.get("emitido_em")
    if not isinstance(usuario_id, int) or not isinstance(emitido_em_str, str):
        return None
    try:
        emitido_em = datetime.fromisoformat(emitido_em_str)
    except ValueError:
        return None
    if _agora() - emitido_em > _TTL_COOKIE:
        return None
    return usuario_id


def criar_cookie_oauth_state() -> tuple[str, str]:
    """Devolve `(state, cookie_assinado)` — `state` vai na URL do Google,
    `cookie_assinado` guarda o mesmo valor num cookie de curta duração, pra
    o callback conferir que o pedido realmente começou aqui (defesa contra
    CSRF: sem isso, alguém poderia mandar a vítima direto pro `/callback`
    com um `code` do próprio atacante)."""
    state = secrets.token_urlsafe(24)
    cookie = _assinar({"state": state, "emitido_em": _agora().isoformat()})
    return state, cookie


def validar_cookie_oauth_state(state_recebido: str, cookie: str | None) -> bool:
    if cookie is None:
        return False
    dados = _verificar(cookie)
    if dados is None:
        return False
    emitido_em_str = dados.get("emitido_em")
    if not isinstance(emitido_em_str, str):
        return False
    try:
        emitido_em = datetime.fromisoformat(emitido_em_str)
    except ValueError:
        return False
    if _agora() - emitido_em > _TTL_OAUTH_STATE:
        return False
    return hmac.compare_digest(str(dados.get("state")), state_recebido)


def get_current_user(
    db: Session = Depends(get_db),
    sessao: str | None = Cookie(default=None, alias=NOME_COOKIE_SESSAO),
) -> Usuario:
    """Dependência de autorização — 401 sempre que não há como identificar
    quem está pedindo."""
    if sessao is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    usuario_id = _ler_cookie_sessao(sessao)
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return usuario
