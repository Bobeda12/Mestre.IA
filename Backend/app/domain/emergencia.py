"""Contratos abertos de ficção; os limites numéricos pertencem ao motor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Registro(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")


class Pista(Registro):
    alvo: str = Field(min_length=1, max_length=100)
    texto: str = Field(min_length=1, max_length=300)


class Particularidade(Registro):
    local: str = ""
    alvo: str = Field(min_length=1, max_length=100)
    regra: str = Field(min_length=1, max_length=500)
    pista: str = Field(min_length=1, max_length=300)
    publica: bool = False
    pistas: list[Pista] = Field(default_factory=list, max_length=4)
    pistas_descobertas: list[str] = Field(default_factory=list)


class Acontecimento(Registro):
    turno: int
    local: str
    acao: str
    descricao: str
    sucesso: bool | None = None


class Consequencia(Registro):
    substitui: str = Field(default="", max_length=60)
    origem: str = Field(min_length=1, max_length=60)
    agente: str = Field(min_length=1, max_length=60)
    motivo: str = Field(min_length=1, max_length=400)
    iniciativa: str = Field(min_length=1, max_length=500)
    sinal: str = Field(min_length=1, max_length=300)
    local: str = Field(min_length=1, max_length=100)
    apos_minutos: int = Field(default=60, ge=10, le=1440)
    vence_em: int = 0
    estado: Literal["pendente", "disponivel", "encerrada"] = "pendente"


class Efeito(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["condicao", "remover_condicao", "relacao", "informacao", "encerrar_consequencia", "revelar", "pista"]
    alvo: str = Field(min_length=1, max_length=100)
    texto: str = Field(default="", max_length=400)
    valor: Literal[-1, 0, 1] = 0


class Intencao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intencao: str = Field(min_length=1, max_length=400)
    alvo: str = Field(min_length=1, max_length=100)
    abordagem: str = Field(min_length=1, max_length=500)
    atributo: Literal["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"]
    dificuldade: Literal["simples", "arriscada", "dificil"] = "arriscada"
    fundamento: str = Field(min_length=1, max_length=500)
    meio: str = Field(default="", max_length=100)
    particularidades: list[str] = Field(default_factory=list, max_length=4)
    sucesso: list[Efeito] = Field(min_length=1, max_length=3)
    falha: list[Efeito] = Field(min_length=1, max_length=2)


class Aprendizado(Registro):
    local: str = ""
    nome: str = Field(min_length=1, max_length=80)
    descricao: str = Field(min_length=1, max_length=300)
    origens: list[str] = Field(min_length=2, max_length=4)
    atributo: Literal["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"]
    alvo: str = Field(min_length=1, max_length=100)
    ativo: bool = False
