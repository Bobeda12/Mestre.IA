"""Fase 3 do plano texto-livre: o mundo cresce sem trancar o jogador.

Viajar é livre; o que escala é o perigo do lugar e o que o jogo revela."""

import random

from app.domain.state import WorldState
from app.infra.data_manager import regras
from app.services import rules_engine as motor
from app.services.living_world import locais_conhecidos, nivel_do_local, painel_mundo, revelar_locais
from tests.helpers import RngFixo
from tests.test_tools import _executor


def test_catalogo_cresceu_e_todo_local_tem_nivel():
    nomes = regras.get_locations_list()
    assert len(nomes) >= 14
    for nome in nomes:
        assert isinstance(regras.get_location(nome)["nivel"], int)
    assert max(regras.get_location(n)["nivel"] for n in nomes) >= 9


def test_perigo_do_local_nunca_fica_abaixo_do_heroi_e_respeita_o_teto():
    assert nivel_do_local("Vila de Phandalin", 4) == 4  # seguro não fica trivial
    assert nivel_do_local("Vulcão de Cinzas", 1) == 8  # longe do que aguenta: desafiado
    assert nivel_do_local("Masmorra Esquecida", 7) == 7
    assert nivel_do_local("Cidadela Esquecida", 10) == motor.NIVEL_MAXIMO


def test_mover_a_lugar_perigoso_e_livre_mas_avisa():
    ex = _executor(rng=RngFixo([10]))  # d20 do encontro de viagem: nada acontece
    resultado = ex.mover("Vulcão de Cinzas")
    assert "erro" not in resultado
    assert resultado["perigo_nivel"] == 8
    assert any("perigoso" in str(e) for e in ex.eventos)
    assert "Vulcão de Cinzas" in ex.w_state.locais_conhecidos


def test_combate_em_lugar_perigoso_usa_a_banda_do_lugar():
    ex = _executor(rng=random.Random(3))
    ex.w_state.local = "Vulcão de Cinzas"
    ex.iniciar_combate(["Cultista das Cinzas"])
    esperados = {m for banda in motor.desafio_sugerido(8) for m in regras.get_monstros_por_banda(banda)}
    assert ex.c_state.inimigos and all(i.arquetipo in esperados for i in ex.c_state.inimigos)


def test_revelar_locais_abre_o_mapa_na_ordem_de_dificuldade():
    w = WorldState(local="Vila de Phandalin", clima="Ensolarado")
    assert locais_conhecidos(w) == ["Vila de Phandalin"]
    novos = revelar_locais(w, nivel_heroi=1, quantidade=2)
    assert len(novos) == 2
    niveis = [regras.get_location(n)["nivel"] for n in novos]
    assert niveis == sorted(niveis) and max(niveis) <= 4  # nível 1 + 3
    assert set(novos) <= set(locais_conhecidos(w))
    # nada acima de nível+3 é revelado, por mais que se peça
    muitos = revelar_locais(w, nivel_heroi=1, quantidade=20)
    assert all(regras.get_location(n)["nivel"] <= 4 for n in muitos)


def test_painel_lista_os_lugares_conhecidos():
    w = WorldState(local="Vila de Phandalin", clima="Ensolarado")
    revelar_locais(w, 1, 1)
    lugares = painel_mundo(w, "Guerreiro")["lugares"]
    assert lugares[0] == {"nome": "Vila de Phandalin", "nivel": 0, "atual": True}
    assert len(lugares) == 2
