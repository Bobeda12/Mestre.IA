from fastapi import APIRouter, Depends, Header, HTTPException

from app.domain.oraculo import (
    OraculoHistoriaRequest,
    OraculoHistoriaResponse,
    OraculoOrigemRequest,
    OraculoOrigemResponse,
)
from app.infra.byok import ChaveUsuario
from app.infra.db import Usuario
from app.infra.llm_client import ErroMestre
from app.services import oraculo
from app.services.auth import get_current_verified_user

router = APIRouter(tags=["oraculo"])


@router.post("/oraculo_origem", response_model=OraculoOrigemResponse)
def oraculo_origem(
    pedido: OraculoOrigemRequest,
    current_user: Usuario = Depends(get_current_verified_user),
    chave_usuario: str | None = Header(default=None, alias="X-Gemini-Key"),
) -> dict:
    chave = ChaveUsuario(chave_usuario)
    try:
        return oraculo.sugerir_origem(pedido.conceito, chamar_fn=chave.chamar_fn)
    except ErroMestre as e:
        raise HTTPException(status_code=502, detail=e.mensagem) from e


@router.post("/oraculo_origem/historia", response_model=OraculoHistoriaResponse)
def oraculo_historia(
    pedido: OraculoHistoriaRequest,
    current_user: Usuario = Depends(get_current_verified_user),
    chave_usuario: str | None = Header(default=None, alias="X-Gemini-Key"),
) -> dict:
    chave = ChaveUsuario(chave_usuario)
    try:
        return oraculo.escrever_historia(
            pedido.conceito, pedido.raca, pedido.classe, pedido.perguntas, pedido.respostas,
            chamar_fn=chave.chamar_fn,
        )
    except ErroMestre as e:
        raise HTTPException(status_code=502, detail=e.mensagem) from e
