"""Fase 4 (ADR-0047): itens encantados — bônus em combate e saque."""

import random

from app.domain.state import CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import rules_engine as motor
from app.services.loot import gerar_loot, recompensa_arco
from tests.helpers import RngFixo
from tests.test_tools import _executor, _heroi


def test_todo_item_raro_da_tabela_existe_no_catalogo():
    nomes = []
    for chave, regra in regras.loot.items():
        if not isinstance(regra, dict):
            continue
        faixas = regra.values() if chave == "arco" else [regra]
        for faixa in faixas:
            nomes += (faixa.get("raros") or {}).get("itens", [])
    assert nomes
    assert all(regras.get_item(n) or regras.get_weapon(n) for n in nomes), nomes


def test_arma_encantada_soma_no_acerto_e_no_dano():
    def golpe(arma):
        goblin = Inimigo(nome="Goblin", hp=40, max_hp=40, ca=15, bonus_ataque=4, dano_dado="1d6+2")
        heroi = _heroi(inventario=[arma], equipamento={})
        executor = _executor(heroi=heroi, c_state=CombatState(ativo=True, inimigos=[goblin]), rng=RngFixo([12, 5]))
        executor.atacar("Goblin", arma)
        return 40 - executor.c_state.inimigos[0].hp, executor.eventos

    dano_base, _ = golpe("Espada Longa")
    dano_magico, eventos = golpe("Espada Longa +1")
    assert dano_magico == dano_base + 1
    assert any(getattr(getattr(e, "dados", None), "bonus", None) is not None for e in eventos)


def test_chefe_de_elite_sempre_deixa_um_encantado():
    lich = Inimigo(nome="Lich Menor", arquetipo="Lich Menor", hp=0, max_hp=72, ca=16)
    for semente in range(15):
        saque = gerar_loot([lich], random.Random(semente))
        assert any("+" in item for item in saque.itens), semente


def test_banda_comum_quase_nunca_deixa_encantado():
    goblin = Inimigo(nome="Goblin", arquetipo="Goblin", hp=0, max_hp=7, ca=15)
    assert not any("+" in i for s in range(50) for i in gerar_loot([goblin], random.Random(s)).itens)


def test_recompensa_de_arco_alto_pode_trazer_encantado():
    achou = any(
        any("+" in i for i in recompensa_arco(8, random.Random(s)).itens) for s in range(40)
    )
    assert achou


def test_armadura_encantada_vale_mais_ca():
    des = {"destreza": 14}
    comum = motor.calcular_defesa(des, regras.get_item("Cota de Malha"), None)
    magica = motor.calcular_defesa(des, regras.get_item("Cota de Malha +1"), None)
    assert magica == comum + 1
    assert regras.get_item("Escudo +1")["ca_bonus"] == regras.get_item("Escudo")["ca_bonus"] + 1
