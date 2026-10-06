"""F0 do plano "Trilha do capítulo + Combate v2" — bugs de combate e de arco
achados por leitura, consertados antes de qualquer redesenho."""
# ruff: noqa: F811 — a fixture `executor` é importada de test_living_world e usada como parâmetro

import pytest
from fastapi.testclient import TestClient

from app.domain.state import Aliado, CombatState, Inimigo
from app.infra.db import Personagem, SessionLocal
from app.main import app
from app.routers.game import _resposta
from app.routers.regras import _ACOES_TATICAS
from app.services import combat
from app.services import living_world as mundo
from tests.helpers import RngFixo
from tests.test_game_actions import _partida
from tests.test_living_world import executor  # noqa: F401 — fixture

client = TestClient(app)


def _luta_com_chefe(executor, cenario: str = "duelo"):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    arco.chefe = "Bugbear"
    executor.rng = RngFixo([10] * 30)
    executor.iniciar_combate(["O Carrasco de Vharn"], chefe=True)
    assert executor.c_state.chefe_do_arco is True
    executor.c_state.cenario_id = cenario
    executor.c_state.inimigos[0].hp = 1
    executor.rng = RngFixo([20] + [3] * 20)  # 20 natural acerta; os dados de dano que vierem valem 3
    return arco


@pytest.mark.parametrize("golpe", ["atacar", "investir", "aliado", "terreno"])
def test_chefe_derrotado_por_qualquer_golpe_marca_o_arco(executor, golpe):
    arco = _luta_com_chefe(executor, cenario="emboscada" if golpe == "terreno" else "duelo")
    alvo = executor.c_state.inimigos[0].nome
    if golpe == "atacar":
        r = executor.atacar(alvo)
    elif golpe == "investir":
        r = executor.investir(alvo)
    elif golpe == "aliado":
        executor.c_state.aliados = [Aliado(nome="Dara", hp=10, max_hp=10, ca=12, bonus_ataque=2, dano_dado="1d6")]
        r = executor.atacar_com_aliado("Dara", alvo)
    else:
        r = executor.interagir("derrubar")
    assert r["resultado"] == "vitoria"
    assert arco.chefe_enfrentado is True
    assert mundo.condicoes_arco(executor.w_state)["resultado_esperado"] == "vitoria_chefe"


def test_inimigo_que_recuou_nao_rende_xp(executor):
    caido = Inimigo(nome="Goblin", arquetipo="Goblin", hp=0, max_hp=7, ca=12, xp=50)
    fujao = Inimigo(nome="Kobold", arquetipo="Kobold", hp=3, max_hp=5, ca=12, xp=25, afastado=True)
    r = executor._conceder_xp([caido, fujao])
    assert r["xp_ganho"] == 50


def test_chefe_ferido_nao_recua_mas_monstro_comum_sim():
    texto = "Territorial. Recua para o ar quando abaixo de 30% de HP e ataca de longe."
    chefe = Inimigo(nome="Vharn", arquetipo="Dragão Jovem", hp=10, max_hp=78, ca=17, comportamento=texto)
    comum = Inimigo(nome="Manticora", arquetipo="Manticora", hp=10, max_hp=46, ca=14,
                    comportamento="Predadora. Ataca de longe e recua quando abaixo de 30% de HP.")
    assert combat._comportamento_inimigo(chefe, 0)[0] is False
    assert combat._comportamento_inimigo(comum, 0)[0] is True


def test_fatos_do_arco_contam_mesmo_com_marcos_cortados(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    executor.w_state.marcos = [f"marco {n}" for n in range(60)]
    arco.marcos_no_inicio = 60  # arco aberto com a lista já no teto
    mundo.registrar_fato(executor, "O depósito reabriu.")
    mundo.registrar_fato(executor, "Dara aceitou dividir a reserva.")
    assert mundo.condicoes_arco(executor.w_state)["marcos"] == 2


def test_arco_de_save_antigo_continua_contando_pelos_marcos(executor):
    arco = mundo.arco_ativo(executor.w_state.mundo)
    assert arco.fatos_registrados is None  # save anterior à F0: sem contador próprio
    executor.w_state.marcos = ["antes do arco", "fato um"]
    arco.marcos_no_inicio = 1
    assert mundo.condicoes_arco(executor.w_state)["marcos"] == 1
    mundo.registrar_fato(executor, "fato dois")
    assert arco.fatos_registrados == 2


def test_estado_enviado_ao_cliente_nao_revela_o_chefe(executor):
    heroi = executor.heroi
    heroi.world_state = executor.w_state.model_dump()
    arco = _resposta(heroi, CombatState(), executor.q_state)["arco"]
    assert arco["ativo"] and "chefe" not in arco
    assert mundo.condicoes_arco(executor.w_state)["chefe"]  # o narrador ainda recebe


def test_alvo_que_recuou_nao_pode_ser_atacado(monkeypatch):
    sid = _partida(monkeypatch)
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        estado = CombatState.model_validate(heroi.combat_state)
        estado.inimigos = [*estado.inimigos,
                           Inimigo(nome="Fujão", arquetipo="Kobold", hp=3, max_hp=5, ca=12, afastado=True)]
        heroi.combat_state = estado.model_dump()
        db.commit()
    resposta = client.post(
        "/game/action", json={"session_id": sid, "acao": "atacar", "alvo": "Fujão", "turno_esperado": 1}
    )
    assert resposta.status_code == 400


def test_painel_de_regras_descreve_esquivar_como_o_motor_resolve():
    esquivar = next(a for a in _ACOES_TATICAS if a["nome"] == "Esquivar")
    assert "desvantagem" in esquivar["efeito"]
