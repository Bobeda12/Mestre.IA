"""Modelos Pydantic do estado do jogo — a "verdade" do sistema, tipada.

Antes da Etapa 2, `world_state`, `combat_state` e `quest_log` (Backend/api.py)
eram dicionários soltos, passados de função em função sem forma garantida.
Aqui eles ganham um formato explícito; a forma do JSON gravado no banco e
devolvido pela API não muda (ver domain/state.py usado pelos routers)."""

from typing import Literal

from pydantic import BaseModel


class Inimigo(BaseModel):
    nome: str
    hp: int
    max_hp: int
    ca: int
    # Preenchidos a partir de data/monsters.json na criação (Etapa 3, ver
    # services/combat.py) — o "Inimigo genérico hp:10" morreu aqui.
    bonus_ataque: int = 0
    dano_dado: str = "1d4"
    nome_ataque: str = ""


class CombatState(BaseModel):
    ativo: bool = False
    inimigos: list[Inimigo] = []
    # Testes de morte (herói a 0 PV) — ver services/combat.py:turno_morte.
    sucessos_morte: int = 0
    falhas_morte: int = 0
    resultado: Literal["vitoria", "morte", "estabilizado"] | None = None
    # Ordem de iniciativa (Etapa 7) — índices em `inimigos`, com -1
    # representando o herói, ordenados do maior pro menor resultado de
    # `rules_engine.rolar_iniciativa`. Calculada uma vez em
    # `combat.iniciar_combate`; `combat.turno_inimigos` ataca nessa ordem
    # em vez de todos de uma vez. `turno_atual` é o índice dentro desta
    # lista — HUD do frontend usa pra destacar de quem é a vez; não trava a
    # resolução (o backend ainda resolve o herói e depois a rodada de
    # inimigos inteira numa única chamada, um turno = uma mensagem).
    ordem_iniciativa: list[int] = []
    turno_atual: int = 0


class WorldState(BaseModel):
    local: str = ""
    clima: str = ""
    turno: int = 1


class QuestLog(BaseModel):
    nome_missao: str = ""
    objetivo_missao: str = ""
