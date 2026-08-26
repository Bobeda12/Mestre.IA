"""Rodada de conserto — o jogador só descobria uma chave Gemini inválida no
meio de uma cena (`chamar_com_chave_usuario` falhando num turno de verdade).
Uma rota dedicada e barata (`GET /models`, sem gerar texto) deixa
`MenuConfiguracao.tsx` validar a chave assim que ela é colada."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.infra.db import Usuario
from app.infra.llm_client import ErroMestre, validar_chave_usuario
from app.services.auth import get_current_user

router = APIRouter(prefix="/byok", tags=["byok"])


class ValidarChaveRequest(BaseModel):
    chave: str


@router.post("/validar")
def validar_chave(req: ValidarChaveRequest, current_user: Usuario = Depends(get_current_user)) -> dict:
    if not req.chave.strip():
        raise HTTPException(status_code=400, detail="Chave vazia.")
    try:
        validar_chave_usuario(req.chave.strip())
    except ErroMestre as e:
        raise HTTPException(status_code=422, detail=e.mensagem) from e
    return {"valida": True}
