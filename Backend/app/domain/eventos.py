"""Eventos de rolagem estruturados (Etapa 7) — o dado por trás da frase.

Antes da Etapa 7, `services/combat.py`/`services/tools.py` só produziam
strings formatadas (`"🎲 Você ataca Goblin: d20(14)+2=16 vs CA 15 →
ACERTO!"`), boas para concatenar na narrativa mas inúteis para desenhar um
card de rolagem no frontend sem fazer parsing de texto.

`EventoRolagem` resolve isso sem quebrar nada que já lia esses eventos como
string: é uma subclasse de `str` — continua comparando, concatenando e
combinando com `"ACERTO" in evento` exatamente como antes (ver
`tests/test_combat.py`/`tests/test_tools.py`) — só que carrega, ao lado do
texto, o `DadosRolagem` estruturado que originou aquele texto. Quem só quer
a frase não muda uma linha; quem quer o card (SSE, Fase 2) lê `.dados`."""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass
class DadosRolagem:
    tipo: Literal["ataque", "teste", "dano", "morte"]
    quem: str
    alvo: str | None = None
    d20: int | None = None
    bonus: int | None = None
    total: int | None = None
    cd: int | None = None
    ca: int | None = None
    sucesso: bool | None = None
    critico: bool = False
    falha_critica: bool = False
    dano: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class EventoRolagem(str):
    """Uma linha de evento (a mesma string de sempre) mais o dado estruturado
    que a gerou. `dados` é `None` para eventos que não vêm de uma rolagem
    (movimento, item, ouro, reputação) — só quem rola dado carrega card."""

    dados: DadosRolagem | None

    def __new__(cls, texto: str, dados: DadosRolagem | None = None) -> "EventoRolagem":
        obj = super().__new__(cls, texto)
        obj.dados = dados
        return obj
