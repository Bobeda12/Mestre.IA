"""Fase 4 do plano "jogo completo" (ADR-0035) — arcos com final verificável pelo servidor."""
# ruff: noqa: F811 — a fixture `executor` é importada de test_living_world e usada como parâmetro

import json

import pytest

from app.domain.state import CombatState, Inimigo
from app.services import living_world as mundo
from app.services.emergent_start import criar_origem, validar_mundo_inicial
from tests.helpers import RngFixo
from tests.test_living_world import agir, executor  # noqa: F401 — fixture


def test_origem_abre_o_arco_um(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    assert arco is not None and arco.id == "arco_1" and arco.conflito_central in executor.w_state.mundo.conflitos
    cond = mundo.condicoes_arco(executor.w_state)
    assert cond["ativo"] and cond["pode_encerrar"] is False


def test_encerrar_cedo_e_recusado_por_cada_condicao(executor):
    r, ok = agir(executor, "encerrar_arco", resumo_proposto="fim")
    assert ok is False and "turnos" in r["erro"] and "fatos" in r["erro"] and "conflito" in r["erro"]
    executor.w_state.turno = 20
    r, ok = agir(executor, "encerrar_arco")
    assert ok is False and "turnos" not in r["erro"]


def test_uma_tentativa_por_turno(executor):
    r1, _ = executor.executar("encerrar_arco", "{}")
    r2, ok2 = executor.executar("encerrar_arco", "{}")
    assert ok2 is False and "já tentou" in r2["erro"]


def _resolver_conflito(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    conflito = executor.w_state.mundo.conflitos[arco.conflito_central]
    conflito.estado = "resolvido"
    executor.w_state.turno = arco.turno_inicio + 10
    mundo.registrar_fato(executor, "O depósito reabriu.")
    mundo.registrar_fato(executor, "Dara aceitou dividir a reserva.")


def test_encerrar_com_acordo_da_recompensa_e_marco(executor):
    _resolver_conflito(executor)
    ouro, xp = executor.heroi.ouro or 0, executor.heroi.xp or 0
    executor.rng = RngFixo([3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
    r, ok = agir(executor, "encerrar_arco", resumo_proposto="acordo fechado")
    assert ok and r["encerrado"] and r["resultado"] == "acordo"
    assert (executor.heroi.ouro or 0) > ouro and (executor.heroi.xp or 0) > xp
    assert r["recompensa"]["itens"] == ["Poção de Cura", "Poção de Foco"]
    assert executor.w_state.marcos[-1].startswith("Arco encerrado:")
    assert executor.w_state.arco_recem_encerrado == "arco_1"
    assert mundo.arco_ativo(executor.w_state.mundo) is None
    assert executor.w_state.mundo.arcos[0].estado == "encerrado"


def test_consequencia_da_metade_sem_item(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    executor.w_state.mundo.conflitos[arco.conflito_central].estado = "concretizado"
    executor.w_state.turno = 12
    mundo.registrar_fato(executor, "a")
    mundo.registrar_fato(executor, "b")
    r, ok = agir(executor, "encerrar_arco")
    assert ok and r["resultado"] == "consequencia" and r["recompensa"]["itens"] == []
    assert r["recompensa"]["xp"] == (mundo.XP_ARCO_BASE + mundo.XP_ARCO_POR_NIVEL * executor.heroi.nivel) // 2


def test_abandono_encerra_sem_recompensa(executor):
    r = mundo.encerrar_arco(executor, abandonar=True)
    assert r["encerrado"] and r["resultado"] == "abandono" and r["recompensa"] == {"xp": 0, "ouro": 0, "itens": []}


def test_abrir_arco_exige_conflito_ativo_e_nenhum_arco_aberto(executor):
    r, ok = agir(executor, "abrir_arco", titulo="Outro", premissa="x", conflito="distribuicao")
    assert ok is False and "Já existe" in r["erro"]
    mundo.encerrar_arco(executor, abandonar=True)
    r, ok = agir(executor, "abrir_arco", titulo="A Segunda Disputa", premissa="p", conflito="inexistente")
    assert ok is False
    r, ok = agir(executor, "abrir_arco", titulo="A Segunda Disputa", premissa="p", conflito="distribuicao")
    assert ok and r["arco"].startswith("a_segunda_disputa")


def test_nao_encerra_em_combate(executor):
    _resolver_conflito(executor)
    executor.c_state.ativo = True
    r, ok = agir(executor, "encerrar_arco")
    assert ok is False


def test_validar_mundo_inicial_aceita_um_arco_e_recusa_dois(executor):
    base = criar_origem(executor.heroi, 5)["mundo_inicial"]
    assert validar_mundo_inicial(base, criar_origem(executor.heroi, 5)["local_inicial"])
    dois = json.loads(json.dumps(base))
    dois["arcos"].append({**dois["arcos"][0], "id": "arco_2"})
    with pytest.raises(ValueError):
        validar_mundo_inicial(dois, criar_origem(executor.heroi, 5)["local_inicial"])


def test_vitoria_contra_chefe_habilita_encerrar(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    arco.chefe = "Bugbear"
    executor.w_state.turno = 12
    mundo.registrar_fato(executor, "a")
    mundo.registrar_fato(executor, "b")
    executor.c_state = CombatState(ativo=True, chefe_do_arco=True, inimigos=[
        Inimigo(nome="Bugbear", arquetipo="Bugbear", hp=0, max_hp=27, ca=16, bonus_ataque=4, dano_dado="2d8+2", xp=200)
    ])
    executor.rng = RngFixo([5] * 6)
    executor._verificar_vitoria()
    assert arco.chefe_enfrentado is True
    assert mundo.condicoes_arco(executor.w_state)["resultado_esperado"] == "vitoria_chefe"


def test_desfecho_sem_modelo_usa_os_marcos(executor, monkeypatch):
    from app.infra import llm_client
    from app.services.narrator import gerar_desfecho_arco

    monkeypatch.setattr(llm_client, "clients", {})
    d = gerar_desfecho_arco(executor.heroi, {"titulo": "T", "premissa": "p", "resultado": "acordo"}, ["x", "y"])
    assert d["titulo"] == "T" and "x" in d["texto"]


def test_tools_de_arco_so_fora_de_combate():
    from app.services.tools import tools_para

    fora = {t["function"]["name"] for t in tools_para(CombatState(ativo=False))}
    dentro = {t["function"]["name"] for t in tools_para(CombatState(ativo=True))}
    assert {"abrir_arco", "encerrar_arco"} <= fora and not {"abrir_arco", "encerrar_arco"} & dentro
