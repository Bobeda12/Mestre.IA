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
    # Etapa 11 (B-8) — "de onde vem o bônus": qual atributo/arma originou a
    # rolagem, e a decomposição do bônus somado (ex: Destreza +2,
    # Proficiência +2, em vez de só "+4"). `None` quando não há o que
    # decompor (ex: ataque de monstro, que já vem com um bônus fixo do
    # bestiário).
    atributo: str | None = None
    arma: str | None = None
    partes_bonus: list[dict] | None = None
    # Fase 0 da revisão de gameplay (Etapa 12/13) — vantagem/desvantagem
    # rola dois d20; `d20_extra` é o dado descartado e `vantagem` diz qual
    # regra valeu, para o RollCard mostrar "d20(7) d20(18) → 18, vantagem"
    # em vez de esconder a segunda rolagem.
    d20_extra: int | None = None
    vantagem: bool | None = None
    # Rodada de conserto (Parte 2, item I) — "Teste de Sabedoria" não dizia
    # se era pra perceber uma emboscada ou resistir a medo; `motivo` é o
    # argumento que o modelo já manda pra `rolar_teste` (ele decide a ação,
    # o servidor decide o resultado — mesmo padrão de sempre), só que agora
    # também chega ao card em vez de morrer na chamada. `None` em ataques
    # (o alvo/arma já contam essa história) e em testes de eventos antigos
    # sem o campo.
    motivo: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EventoStatus:
    """Etapa 10 (A-7) — cura e morte de inimigo: não são rolagem de d20
    (sem acerto/erro, sem CD/CA), mas mereciam o mesmo tratamento de card
    que `DadosRolagem` já dá a ataque/teste, em vez de ficarem como texto
    solto com emoji dentro da narrativa. Dataclass separado de propósito —
    os campos de rolagem não fazem sentido aqui."""

    # Fase 2 da revisão de gameplay — "morte_aliado" (um aliado caiu em
    # combate) some pelo mesmo card de "morte_inimigo", só com o `tipo`
    # correto guardado — o frontend hoje trata os dois iguais
    # (StatusCard.tsx), mas o dado fica honesto para quando isso mudar.
    tipo: Literal["cura", "morte_inimigo", "morte_aliado"]
    quem: str
    valor: int | None = None  # cura: quanto de PV recuperou. morte_*: sem valor.

    def to_dict(self) -> dict:
        return asdict(self)


class EventoRolagem(str):
    """Uma linha de evento (a mesma string de sempre) mais o dado estruturado
    que a gerou. `dados` é `None` para eventos que não vêm de uma rolagem
    (movimento, item, ouro, reputação) — só quem rola dado carrega card."""

    dados: DadosRolagem | EventoStatus | None

    def __new__(cls, texto: str, dados: DadosRolagem | EventoStatus | None = None) -> "EventoRolagem":
        obj = super().__new__(cls, texto)
        obj.dados = dados
        return obj
