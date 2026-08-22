from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.domain.auth import LoginRequest, RegistrarRequest
from app.infra.db import Usuario, get_db
from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.services.auth import (
    NOME_COOKIE_OAUTH_STATE,
    NOME_COOKIE_SESSAO,
    construir_url_autorizacao_google,
    criar_cookie_oauth_state,
    criar_cookie_sessao,
    get_current_user,
    google_disponivel,
    hash_senha,
    obter_ou_criar_usuario_google,
    trocar_code_por_userinfo,
    validar_cookie_oauth_state,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_TTL_COOKIE_SESSAO_SEGUNDOS = 30 * 24 * 60 * 60
_TTL_COOKIE_STATE_SEGUNDOS = 10 * 60


def _setar_cookie_sessao(response: Response, usuario_id: int) -> None:
    response.set_cookie(
        key=NOME_COOKIE_SESSAO,
        value=criar_cookie_sessao(usuario_id),
        max_age=_TTL_COOKIE_SESSAO_SEGUNDOS,
        httponly=True,
        samesite="lax",
    )


@router.get("/opcoes")
def opcoes() -> dict:
    """O front usa isto pra decidir se mostra o botão "Entrar com Google" —
    sem `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` configurados, o fluxo
    OAuth não tem como funcionar (ver ADR-0014)."""
    return {"google_disponivel": google_disponivel()}


@router.post("/registrar", status_code=201)
@limiter.limit("10/minute")
def registrar(request: Request, req: RegistrarRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.query(Usuario).filter(Usuario.email == req.email).first() is not None:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    usuario = Usuario(email=req.email, senha_hash=hash_senha(req.senha))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _setar_cookie_sessao(response, usuario.id)
    return {"email": usuario.email}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    usuario = db.query(Usuario).filter(Usuario.email == req.email).first()
    # Mensagem genérica em qualquer um dos três casos (e-mail não existe,
    # conta é só-Google sem senha, senha errada) — não é este endpoint que
    # revela qual dos três aconteceu.
    erro = HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    if usuario is None or usuario.senha_hash is None:
        raise erro
    if not verificar_senha(req.senha, usuario.senha_hash):
        raise erro
    _setar_cookie_sessao(response, usuario.id)
    return {"email": usuario.email}


@router.post("/sair")
def sair(response: Response) -> dict:
    response.delete_cookie(NOME_COOKIE_SESSAO)
    return {"detail": "Sessão encerrada."}


@router.get("/eu")
def eu(current_user: Usuario = Depends(get_current_user)) -> dict:
    return {"email": current_user.email}


@router.get("/google/iniciar")
def google_iniciar() -> RedirectResponse:
    if not google_disponivel():
        raise HTTPException(status_code=503, detail="Login com Google não está configurado neste servidor.")
    state, cookie_state = criar_cookie_oauth_state()
    resposta = RedirectResponse(url=construir_url_autorizacao_google(state))
    resposta.set_cookie(
        key=NOME_COOKIE_OAUTH_STATE,
        value=cookie_state,
        max_age=_TTL_COOKIE_STATE_SEGUNDOS,
        httponly=True,
        samesite="lax",
    )
    return resposta


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    oauth_state: str | None = Cookie(default=None, alias=NOME_COOKIE_OAUTH_STATE),
) -> RedirectResponse:
    if not validar_cookie_oauth_state(state, oauth_state):
        raise HTTPException(status_code=400, detail="Pedido de login com Google inválido ou expirado.")

    userinfo = trocar_code_por_userinfo(code)
    usuario = obter_ou_criar_usuario_google(db, google_sub=userinfo["sub"], email=userinfo["email"])

    resposta = RedirectResponse(url=settings.frontend_url)
    resposta.delete_cookie(NOME_COOKIE_OAUTH_STATE)
    resposta.set_cookie(
        key=NOME_COOKIE_SESSAO,
        value=criar_cookie_sessao(usuario.id),
        max_age=_TTL_COOKIE_SESSAO_SEGUNDOS,
        httponly=True,
        samesite="lax",
    )
    return resposta
