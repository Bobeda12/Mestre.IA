"""Fase 5 do plano "jogo completo" — bestiário 5-10, chefe do arco, saque das bandas novas."""

import random

from app.domain.state import CombatState
from app.infra.data_manager import regras
from app.services import combat
from app.services import living_world as mundo
from app.services import rules_engine as motor
from app.services.loot import gerar_loot
from tests.helpers import RngFixo
from tests.test_living_world import agir, executor  # noqa: F401,F811


def test_bandas_cobrem_1_a_10_sem_repetir_chefe():
    vistos = set()
    for nivel in range(1, 11):
        bandas = motor.desafio_sugerido(nivel)
        assert bandas and all(regras.get_monstros_por_banda(b) for b in bandas), nivel
        vistos.update(bandas)
    assert {"Nivel_5", "Nivel_6", "Nivel_7", "Nivel_8", "Chefe_Elite"} <= vistos
    assert "Chefe" not in vistos  # o chefe é do arco, não da banda do nível


def test_toda_ficha_nova_e_parseavel_e_tem_saque():
    for banda, grupo in regras.monsters.items():
        assert banda in regras.loot, banda
        for nome, dados in grupo.items():
            motor.parse_ataque_monstro(dados["ataque"])
            assert dados["hp"] > 0 and dados["xp"] > 0, nome


def test_sem_escala_artificial_a_ficha_e_a_do_bestiario():
    estado, _, _ = combat.iniciar_combate(["Golem de Pedra"], {"destreza": 10}, 15, random.Random(1), nivel_heroi=9)
    assert estado.inimigos[0].hp == regras.get_monster("Golem de Pedra")["hp"]


def test_chefe_reservado_entra_fora_do_orcamento_com_a_pele_proposta():
    estado, _, _ = combat.iniciar_combate(
        ["Vharn, o Devorador", "Goblin"], {"destreza": 10}, 15, random.Random(1), nivel_heroi=1,
        chefe_reservado="Dragão Jovem",
    )
    assert estado.inimigos[0].nome == "Vharn, o Devorador" and estado.inimigos[0].arquetipo == "Dragão Jovem"
    assert estado.inimigos[0].hp == regras.get_monster("Dragão Jovem")["hp"]


def test_origem_e_abrir_arco_sorteiam_chefe(executor):  # noqa: F811
    arco = mundo.arco_ativo(executor.w_state.mundo)
    assert arco.chefe in regras.chefes_para_nivel(1)
    mundo.encerrar_arco(executor, abandonar=True)
    r, ok = agir(executor, "abrir_arco", titulo="Segundo", premissa="p", conflito="distribuicao")
    assert ok and mundo.arco_ativo(executor.w_state.mundo).chefe in regras.get_monstros_chefe()


def test_iniciar_combate_com_chefe_usa_a_ficha_reservada_e_vitoria_fecha(executor):  # noqa: F811
    arco = mundo.arco_ativo(executor.w_state.mundo)
    arco.chefe = "Bugbear"
    executor.rng = RngFixo([10] * 30)
    r = executor.iniciar_combate(["O Carrasco de Vharn"], chefe=True)
    assert "erro" not in r and executor.c_state.chefe_do_arco is True
    chefe = executor.c_state.inimigos[0]
    assert chefe.arquetipo == "Bugbear" and chefe.nome == "O Carrasco de Vharn"
    for i in executor.c_state.inimigos:
        i.hp = 0
    executor._verificar_vitoria()
    assert arco.chefe_enfrentado is True
    assert mundo.condicoes_arco(executor.w_state)["resultado_esperado"] == "vitoria_chefe"
    # segunda vez: a ficha reservada não volta
    executor.c_state = CombatState()
    executor.iniciar_combate(["Outro"], chefe=True)
    assert executor.c_state.chefe_do_arco is False


def test_saque_das_bandas_altas():
    from app.domain.state import Inimigo

    golem = Inimigo(nome="Golem de Pedra", arquetipo="Golem de Pedra", hp=0, max_hp=120, ca=17, bonus_ataque=9,
                    dano_dado="3d8+6", xp=2300)
    saque = gerar_loot([golem], random.Random(3))
    assert saque.ouro >= 47


def test_todo_arquetipo_tem_sprite():
    # Fase 5 — a arte mora em Frontend/public/assets/monstros/<slug>.png (Dungeon Crawl CC0).
    import pathlib
    import re
    import unicodedata

    pasta = pathlib.Path(__file__).resolve().parents[2] / "Frontend" / "public" / "assets" / "monstros"
    def slug(n):
        base = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn").lower()
        return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", base))
    faltam = [n for g in regras.monsters.values() for n in g if not (pasta / f"{slug(n)}.png").exists()]
    assert faltam == []
