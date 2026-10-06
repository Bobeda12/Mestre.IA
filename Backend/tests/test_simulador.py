"""F1 do plano "Trilha do capítulo + Combate v2" — o simulador de balanceamento
roda o caminho real do juiz, é reprodutível por semente e cobre todas as classes."""

import pytest

from app.infra.data_manager import regras
from evals import simulador


def test_mesma_semente_mesmo_resultado():
    a = simulador.simular("Guerreiro", 3, ["Ogro"], "basico", n=15, semente=7)
    b = simulador.simular("Guerreiro", 3, ["Ogro"], "basico", n=15, semente=7)
    assert a.duelos == b.duelos
    outra = simulador.simular("Guerreiro", 3, ["Ogro"], "basico", n=15, semente=8)
    assert outra.duelos != a.duelos


def test_goblin_no_nivel_1_e_um_encontro_comum():
    r = simulador.simular("Guerreiro", 1, ["Goblin"], "basico", n=60)
    assert r.vitoria > 0.7 and 0 < r.turnos < 15


@pytest.mark.parametrize("classe", regras.get_classes_list())
@pytest.mark.parametrize("bot", sorted(simulador.BOTS))
def test_toda_classe_luta_sem_jogada_recusada(classe, bot):
    # nível 7: todas as técnicas liberadas; o juiz recusar uma jogada levanta erro.
    r = simulador.simular(classe, 7, ["Cavaleiro Negro"], bot, n=5)
    assert r.n == 5 and all(d.turnos >= 1 for d in r.duelos)


def test_bot_tatico_gasta_foco_e_o_basico_nao():
    basico = simulador.simular("Mago", 5, ["Urso-Coruja"], "basico", n=20)
    tatico = simulador.simular("Mago", 5, ["Urso-Coruja"], "tatico", n=20)
    assert basico.foco_gasto == 0 and tatico.foco_gasto > 0


def test_encontros_do_nivel_incluem_o_chefe_do_arco():
    nomes = [m[0] for _, m in simulador.encontros_do_nivel(1)]
    assert set(regras.get_monstros_por_banda("Nivel_1")) <= set(nomes)
    assert set(regras.chefes_para_nivel(1)) <= set(nomes)


def test_chefe_entra_com_a_propria_ficha():
    heroi = simulador.heroi_de_referencia("Guerreiro", 1)
    import random

    c_state, _ = simulador._abrir_luta(heroi, ["Dragão Jovem"], random.Random(1))
    assert c_state.inimigos[0].arquetipo == "Dragão Jovem"
    assert c_state.inimigos[0].max_hp == regras.get_monster("Dragão Jovem")["hp"]
