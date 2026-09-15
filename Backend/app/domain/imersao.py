"""Conteúdo autoral da campanha; sem cenas ou soluções pré-escritas."""

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.emergencia import Registro


class MomentoPessoal(Registro):
    npc: str = Field(min_length=1, max_length=60)
    origem: str = Field(min_length=1, max_length=60)
    gesto: str = Field(min_length=1, max_length=400)
    convite: str = Field(default="", max_length=200)
    local: str = ""
    turno: int = 0


class MarcaJornada(Registro):
    origem: str = Field(min_length=1, max_length=60)
    nome: str = Field(min_length=1, max_length=80)
    significado: str = Field(min_length=1, max_length=400)
    tipo: Literal["apelido", "vinculo", "objeto", "feito"]
    alvo: str = Field(min_length=1, max_length=100)
    local: str = ""
    turno: int = 0


class Oportunidade(Registro):
    alvo: str = Field(min_length=1, max_length=100)
    percepcao: str = Field(min_length=1, max_length=300)
    risco: str = Field(default="", max_length=200)
    local: str = ""
    expira_turno: int = 0


class Ritmo(BaseModel):
    tensao_seguida: int = 0
    ultima_vitoria: int = -100
    ultimo_descanso: int = -100
    ultimo_momento: int = -100
    ultima_acao: str = ""
