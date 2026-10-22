"""Achado do teste ao vivo (ADR-0048): turno só de narração também gasta tempo."""

from app.domain.state import CombatState
from app.routers.game import _tempo_da_narracao
from app.services.tools import tools_para
from tests.test_tools import _executor


def test_turno_sem_acao_gasta_dez_minutos():
    ex = _executor()
    antes = ex.w_state.mundo.minutos
    _tempo_da_narracao(ex)
    assert ex.w_state.mundo.minutos == antes + 10


def test_acao_ja_resolvida_nao_cobra_duas_vezes():
    ex = _executor()
    ex._acao_gasta = True
    antes = ex.w_state.mundo.minutos
    _tempo_da_narracao(ex)
    assert ex.w_state.mundo.minutos == antes


def test_em_combate_o_tempo_e_do_motor_de_turnos():
    ex = _executor(c_state=CombatState(ativo=True))
    antes = ex.w_state.mundo.minutos
    _tempo_da_narracao(ex)
    assert ex.w_state.mundo.minutos == antes


def test_luta_e_duelo_abrem_as_ferramentas_de_combate():
    ex = _executor()
    for frase in ("Eu o desafio para um duelo e começo a luta contra ele.", "Vou enfrentar o capitão.", "Quero uma briga"):  # noqa: E501
        nomes = {t["function"]["name"] for t in tools_para(ex.c_state, frase, ex.w_state)}
        assert "iniciar_combate" in nomes, frase
    nomes = {t["function"]["name"] for t in tools_para(ex.c_state, "Converso com o ferreiro", ex.w_state)}
    assert "iniciar_combate" not in nomes
