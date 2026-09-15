"""Ambições escolhidas pelo jogador e condições geradas para aquela campanha."""

from typing import Literal

from pydantic import Field

from app.domain.emergencia import Registro


class CondicaoProjeto(Registro):
    descricao: str = Field(min_length=1, max_length=300)
    alvo: str = Field(min_length=1, max_length=100)
    estado: Literal["aberta", "satisfeita", "superada"] = "aberta"
    origem: str = ""
    evidencia: str = ""


class PropostaProjeto(Registro):
    organizacao: str = Field(default="", max_length=60)
    nome_organizacao: str = ""
    npc: str = Field(min_length=1, max_length=60)
    nome_npc: str = ""
    condicao: str = Field(min_length=1, max_length=60)
    oferta: str = Field(min_length=1, max_length=300)
    contrapartida: str = Field(min_length=1, max_length=300)
    motivo_declarado: str = Field(min_length=1, max_length=300)
    exclusiva: bool = False
    estado: Literal["oferecida", "aceita", "recusada", "cumprida", "renunciada"] = "oferecida"
    evidencia: str = ""
    origem: str = ""


class Projeto(Registro):
    ambicao: str = Field(min_length=1, max_length=500)
    local: str
    estado: Literal["ativo", "concluido", "abandonado"] = "ativo"
    condicoes: list[CondicaoProjeto] = Field(default_factory=list, max_length=5)
    propostas: list[PropostaProjeto] = Field(default_factory=list, max_length=8)
    turno: int = 0
