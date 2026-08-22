from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.domain.auth import LoginRequest, RegistrarRequest, ReivindicarRequest
from app.infra.db import Usuario, get_db
from app.infra.email import enviar_email_confirmacao
from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.services.auth import (
    NOME_COOKIE_OAUTH_STATE,
    NOME_COOKIE_SESSAO,
    construir_url_autorizacao_google,
    criar_cookie_oauth_state,
    criar_cookie_sessao,
    criar_token_confirmacao,
    get_current_user,
    google_disponivel,
    hash_senha,
    obter_ou_criar_usuario_google,
    trocar_code_por_userinfo,
    validar_cookie_oauth_state,
    validar_token_confirmacao,
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


def _disparar_confirmacao(usuario_id: int, email: str) -> None:
    token = criar_token_confirmacao(usuario_id)
    link = f"{settings.confirmacao_email_url}?token={token}"
    enviar_email_confirmacao(email, link)


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
    _disparar_confirmacao(usuario.id, usuario.email)
    return {"email": usuario.email}


@router.post("/convidado", status_code=201)
@limiter.limit("1/10 minute")
def convidado(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Etapa 10 (A-1) — joga sem e-mail. `Usuario.email` já é opcional (ver
    ADR-0014); convidado é só um `Usuario` sem e-mail nem senha. Rate limit
    apertado (1 por IP a cada 10 min), senão o endpoint vira fábrica de
    contas descartáveis."""
    usuario = Usuario()
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _setar_cookie_sessao(response, usuario.id)
    return {"email": usuario.email}


@router.post("/reivindicar", status_code=200)
def reivindicar(
    req: ReivindicarRequest,
    response: Response,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Etapa 10 (A-1) — o convidado vira uma conta de verdade, no mesmo
    `usuario_id`: os heróis dele não mudam de dono, só o `Usuario` ganha
    e-mail e senha. É uma linha de UPDATE, não um usuário novo."""
    if current_user.email is not None:
        raise HTTPException(status_code=400, detail="Esta conta já tem um e-mail.")
    if db.query(Usuario).filter(Usuario.email == req.email).first() is not None:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    current_user.email = req.email
    current_user.senha_hash = hash_senha(req.senha)
    db.commit()
    _setar_cookie_sessao(response, current_user.id)
    _disparar_confirmacao(current_user.id, current_user.email)
    return {"email": current_user.email}


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
    return {"email": current_user.email, "email_verificado": current_user.email_verificado}


@router.get("/confirmar")
def confirmar(token: str, db: Session = Depends(get_db)) -> RedirectResponse:
    """Etapa 10 (A-2) — link clicado direto do e-mail, fora do SPA: por
    isso devolve um redirect pro front, não JSON. `?confirmado=1/0` deixa
    o front decidir o que mostrar, sem precisar de uma rota própria só
    para essa tela."""
    usuario_id = validar_token_confirmacao(token)
    if usuario_id is None:
        return RedirectResponse(url=f"{settings.frontend_url}/entrar?confirmado=0")
    usuario = db.get(Usuario, usuario_id)
    if usuario is not None:
        usuario.email_verificado = True
        db.commit()
    return RedirectResponse(url=f"{settings.frontend_url}/entrar?confirmado=1")


@router.post("/confirmar/reenviar")
@limiter.limit("3/hour")
def reenviar_confirmacao(request: Request, current_user: Usuario = Depends(get_current_user)) -> dict:
    if current_user.email is None:
        raise HTTPException(status_code=400, detail="Esta conta não tem e-mail para confirmar.")
    if current_user.email_verificado:
        return {"status": "já confirmado"}
    _disparar_confirmacao(current_user.id, current_user.email)
    return {"status": "reenviado"}


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
