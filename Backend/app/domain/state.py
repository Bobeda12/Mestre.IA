"""Modelos Pydantic do estado do jogo — a "verdade" do sistema, tipada.

Antes da Etapa 2, `world_state`, `combat_state` e `quest_log` (Backend/api.py)
eram dicionários soltos, passados de função em função sem forma garantida.
Aqui eles ganham um formato explícito; a forma do JSON gravado no banco e
devolvido pela API não muda (ver domain/state.py usado pelos routers)."""

from pydantic import BaseModel


class Inimigo(BaseModel):
    nome: str
    hp: int
    max_hp: int
    ca: int


class CombatState(BaseModel):
    ativo: bool = False
    inimigos: list[Inimigo] = []


class WorldState(BaseModel):
    local: str = ""
    clima: str = ""
    turno: int = 1


class QuestLog(BaseModel):
    nome_missao: str = ""
    objetivo_missao: str = ""
