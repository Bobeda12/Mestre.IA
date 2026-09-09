"""Saque determinístico por banda do bestiário (Fase 1, ADR-0033).

Chamado em `ToolExecutor._conceder_xp`, o único ponto de vitória. Com `rng`
injetável, o mesmo combate produz o mesmo saque — testável sem sorte.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.domain.state import Inimigo
from app.infra.data_manager import regras
from app.services import rules_engine as motor


@dataclass
class Loot:
    ouro: int = 0
    itens: list[str] = field(default_factory=list)


def _banda_de(inimigo: Inimigo) -> str | None:
    nome = inimigo.arquetipo or inimigo.nome
    for banda, grupo in regras.monsters.items():
        if nome in grupo:
            return banda
    return None


def gerar_loot(inimigos: list[Inimigo], rng: random.Random) -> Loot:
    tabela = regras.loot
    saque = Loot()
    for inimigo in inimigos:
        if inimigo.hp > 0:
            continue  # afastado/fugido não deixa saque
        banda = _banda_de(inimigo)
        regra = tabela.get(banda or "", None)
        if not regra:
            continue
        saque.ouro += max(0, motor.calcular_dano(regra["ouro"], rng=rng))
        if regra.get("itens") and rng.randint(1, 100) <= regra.get("chance_item", 0):
            saque.itens.append(rng.choice(regra["itens"]))
    return saque


def recompensa_arco(nivel: int, rng: random.Random) -> Loot:
    faixas = regras.loot.get("arco", {})
    chave = max((int(k) for k in faixas if int(k) <= max(1, nivel)), default=None)
    if chave is None:
        return Loot()
    regra = faixas[str(chave)]
    return Loot(ouro=max(0, motor.calcular_dano(regra["ouro"], rng=rng)), itens=list(regra.get("itens", [])))
