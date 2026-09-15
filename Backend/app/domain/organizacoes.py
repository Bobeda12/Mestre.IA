"""Grupos da campanha, compostos por pessoas já encontradas."""

from pydantic import Field

from app.domain.emergencia import Registro


class Organizacao(Registro):
    nome: str = Field(min_length=1, max_length=100)
    proposito: str = Field(min_length=1, max_length=400)
    principio: str = Field(min_length=1, max_length=300)
    membros: list[str] = Field(min_length=1, max_length=5)
    local: str = ""
