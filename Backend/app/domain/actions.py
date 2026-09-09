"""Comandos do controle de jogo; nunca expõem ferramentas administrativas do narrador."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GameAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=150)
    acao: Literal[
        "atacar", "defender", "esquivar", "investir", "esconder_se", "fugir",
        "usar_habilidade", "interagir", "descansar", "usar_item", "resistir",
        "agir_no_mundo", "intervir_conflito", "definir_objetivo", "escolher_especializacao",
        "equipar", "desequipar", "comerciar", "atacar_com_aliado", "escolher_nivel", "encerrar_arco",
    ]
    turno_esperado: int = Field(ge=1)
    alvo: str | None = Field(default=None, max_length=120)
    habilidade: str | None = Field(default=None, max_length=80)
    interacao: str | None = Field(default=None, max_length=80)
    item: str | None = Field(default=None, max_length=120)
    tipo: Literal["curto", "longo"] = "curto"
    operacao: str = Field(default="examinar", max_length=40)
    meio: str | None = Field(default=None, max_length=120)
    proposta: str = Field(default="", max_length=500)
    marco: Literal["3", "7"] = "3"
    escolha: Literal["explorador", "diplomata", "combatente"] = "explorador"
    # Fase 0 do plano "jogo completo" (08/09/2026) — texto humano do botão
    # clicado ("Atacar Goblin", "Examinar Registro"); vira a fala do jogador
    # no histórico em vez do id cru da ação. Só apresentação: a ação que o
    # juiz resolve continua sendo `acao` + argumentos.
    rotulo: str | None = Field(default=None, max_length=80)
    slot: Literal["arma", "armadura", "escudo"] | None = None
    aliado: str | None = Field(default=None, max_length=80)
    # Fase 3 (ADR-0034) — escolha de nível pela interface.
    nivel_escolha: int | None = Field(default=None, ge=1, le=20)
    tipo_escolha: Literal["atributo", "talento", "especializacao"] | None = None
    opcao: str | None = Field(default=None, max_length=40)
