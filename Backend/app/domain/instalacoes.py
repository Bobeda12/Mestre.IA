"""Melhorias conquistadas no mundo, com efeitos definidos pelo motor."""

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.emergencia import Registro

AtributoPreparacao = Literal["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"]


class Instalacao(Registro):
    projeto: str = Field(min_length=1, max_length=60)
    condicao: str = Field(min_length=1, max_length=60)
    nome: str = Field(min_length=1, max_length=100)
    descricao: str = Field(min_length=1, max_length=400)
    tipo: Literal["abrigo", "oficina"]
    atributo: AtributoPreparacao = "inteligencia"
    local: str = ""
    alvo: str = ""
    evidencia: str = ""
    ativa: bool = False


class Preparacao(BaseModel):
    instalacao: str
    nome: str
    atributo: AtributoPreparacao
    expira_em: int
