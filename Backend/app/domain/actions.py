"""Comandos do controle de jogo; nunca expõem ferramentas administrativas do narrador."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GameAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=150)
    acao: Literal[
        "atacar", "defender", "esquivar", "investir", "esconder_se", "fugir",
        "usar_habilidade", "interagir", "descansar", "usar_item", "resistir",
    ]
    turno_esperado: int = Field(ge=1)
    alvo: str | None = Field(default=None, max_length=120)
    habilidade: str | None = Field(default=None, max_length=80)
    interacao: str | None = Field(default=None, max_length=80)
    item: str | None = Field(default=None, max_length=120)
    tipo: Literal["curto", "longo"] = "curto"
