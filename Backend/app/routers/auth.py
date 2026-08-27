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
    criar_token_registro_pendente,
    criar_token_reivindicacao_pendente,
    get_current_user,
    google_disponivel,
    hash_senha,
    obter_ou_criar_usuario_google,
    trocar_code_por_userinfo,
    validar_cookie_oauth_state,
    validar_token_registro_pendente,
    validar_token_reivindicacao_pendente,
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


@router.post("/registrar", status_code=200)
@limiter.limit("10/minute")
def registrar(request: Request, req: RegistrarRequest, db: Session = Depends(get_db)) -> dict:
    """Registro sem estado: nada é gravado no banco aqui. O e-mail e o hash
    da senha viajam dentro do próprio token do link de confirmação — só
    `/auth/confirmar` cria o `Usuario`, quando (e se) o link for clicado.
    Reenviar o e-mail é só chamar esta rota de novo com os mesmos dados: como
    nada foi persistido, não esbarra na checagem de duplicidade acima."""
    if db.query(Usuario).filter(Usuario.email == req.email).first() is not None:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    token = criar_token_registro_pendente(req.email, hash_senha(req.senha))
    link = f"{settings.confirmacao_email_url}?token={token}"
    enviar_email_confirmacao(req.email, link)
    return {"email": req.email}


@router.post("/convidado", status_code=201)
@limiter.limit("5/10 minute")
def convidado(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Etapa 10 (A-1) — joga sem e-mail. `Usuario.email` já é opcional (ver
    ADR-0014); convidado é só um `Usuario` sem e-mail nem senha. Rate limit
    por IP (5 a cada 10 min — antes de `_ip_do_cliente` existir, isto era
    1/10min e valia pro site inteiro, não por pessoa; ver `rate_limit.py`),
    senão o endpoint vira fábrica de contas descartáveis."""
    usuario = Usuario()
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _setar_cookie_sessao(response, usuario.id)
    return {"email": usuario.email}


@router.post("/reivindicar", status_code=200)
@limiter.limit("10/minute")
def reivindicar(
    request: Request,
    req: ReivindicarRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Etapa 10 (A-1) — o convidado vira uma conta de verdade, no mesmo
    `usuario_id`: os heróis dele não mudam de dono, só o `Usuario` ganha
    e-mail e senha. Registro sem estado (igual `/registrar`): nada muda no
    banco aqui, o `usuario_id` + e-mail + hash da senha viajam no token do
    link, e só `/auth/confirmar` faz o UPDATE."""
    if current_user.email is not None:
        raise HTTPException(status_code=400, detail="Esta conta já tem um e-mail.")
    if db.query(Usuario).filter(Usuario.email == req.email).first() is not None:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    token = criar_token_reivindicacao_pendente(current_user.id, req.email, hash_senha(req.senha))
    link = f"{settings.confirmacao_email_url}?token={token}"
    enviar_email_confirmacao(req.email, link)
    return {"email": req.email}


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


def _redirect_confirmado(sucesso: bool) -> RedirectResponse:
    valor = "1" if sucesso else "0"
    return RedirectResponse(url=f"{settings.frontend_url}/entrar?confirmado={valor}")


@router.get("/confirmar")
def confirmar(token: str, db: Session = Depends(get_db)) -> RedirectResponse:
    """Etapa 10 (A-2) — link clicado direto do e-mail, fora do SPA: por isso
    devolve um redirect pro front, não JSON. `?confirmado=1/0` deixa o front
    decidir o que mostrar, sem precisar de uma rota própria só para essa
    tela. Registro sem estado: é aqui, e só aqui, que o `Usuario` é
    gravado/atualizado — antes disso não existe conta nenhuma no banco. Seta
    o cookie de sessão na resposta (igual `google_callback` já faz) porque
    ninguém tem sessão até este ponto: nem quem registrou, nem quem clicou
    no link, podem ser abas ou dispositivos diferentes."""
    registro = validar_token_registro_pendente(token)
    if registro is not None:
        email, senha_hash = registro
        if db.query(Usuario).filter(Usuario.email == email).first() is not None:
            # Corrida: o e-mail foi usado por outra conta entre o clique no
            # "criar conta" e o clique no link (ex.: dois links do mesmo
            # reenvio confirmados em sequência).
            return _redirect_confirmado(sucesso=False)
        usuario = Usuario(email=email, senha_hash=senha_hash, email_verificado=True)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        resposta = _redirect_confirmado(sucesso=True)
        _setar_cookie_sessao(resposta, usuario.id)
        return resposta

    reivindicacao = validar_token_reivindicacao_pendente(token)
    if reivindicacao is not None:
        usuario_id, email, senha_hash = reivindicacao
        usuario = db.get(Usuario, usuario_id)
        if (
            usuario is None
            or usuario.email is not None
            or db.query(Usuario).filter(Usuario.email == email).first() is not None
        ):
            return _redirect_confirmado(sucesso=False)
        usuario.email = email
        usuario.senha_hash = senha_hash
        usuario.email_verificado = True
        db.commit()
        resposta = _redirect_confirmado(sucesso=True)
        _setar_cookie_sessao(resposta, usuario.id)
        return resposta

    return _redirect_confirmado(sucesso=False)


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
