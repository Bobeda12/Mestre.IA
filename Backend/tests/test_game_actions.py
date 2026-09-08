"""Caminho real do jogador: clique, juiz, persistência, recarregamento e repetição rejeitada."""

import random

from fastapi.testclient import TestClient

from app.domain.state import CombatState, Inimigo, QuestLog, WorldState
from app.infra import llm_client
from app.infra.db import EventoMemoria, Personagem, SessionLocal
from app.main import app
from app.services.encounters import CENARIOS, interagir_cenario, painel_cena, preparar_encontro
from app.services.tools import ToolExecutor
from tests.test_smoke import _payload_base

client = TestClient(app)


def _partida(monkeypatch, cenario="duelo"):
    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="ControleJogo"))
    assert criado.status_code == 200, criado.text
    sid = criado.json()["session_id"]
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        heroi.hp_atual = heroi.hp_max = 200
        heroi.defesa = 20
        heroi.world_state = WorldState(local="Ponte", versao_progressao=1).model_dump()
        heroi.combat_state = CombatState(
            ativo=True, cenario_id=cenario,
            inimigos=[Inimigo(nome="Sentinela", arquetipo="Goblin", hp=100, max_hp=100, ca=12,
                             bonus_ataque=0, dano_dado="1d4", xp=50)],
        ).model_dump()
        db.commit()
    return sid


def test_clique_resolve_persiste_e_repeticao_nao_gasta_rodada(monkeypatch):
    sid = _partida(monkeypatch)
    payload = {"session_id": sid, "acao": "atacar", "alvo": "Sentinela", "turno_esperado": 1}
    resposta = client.post("/game/action", json=payload)
    assert resposta.status_code == 200, resposta.text
    estado = resposta.json()
    assert estado["turno_mundo"] == 2
    assert estado["narrativa"]
    assert estado["progressao"]["nivel_maximo"] == 10
    assert client.post("/game/action", json=payload).status_code == 409
    salvo = client.post("/load_game", json={"session_id": sid}).json()
    assert salvo["turno_mundo"] == 2
    assert salvo["hp_atual"] == estado["hp_atual"]
    assert salvo["inimigos"] == estado["inimigos"]
    assert salvo["historico_chat"][-1]["content"] == estado["narrativa"]
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        assert db.query(EventoMemoria).filter_by(personagem_id=heroi.id, tipo="acao_jogo").count() == 1


def test_controle_nao_expoe_ferramentas_de_recompensa(monkeypatch):
    sid = _partida(monkeypatch)
    for acao in ("dar_item", "aplicar_dano", "concluir_objetivo", "iniciar_combate"):
        assert client.post("/game/action", json={
            "session_id": sid, "acao": acao, "turno_esperado": 1,
        }).status_code == 422


def test_alvo_invalido_nao_consume_acao(monkeypatch):
    sid = _partida(monkeypatch)
    resposta = client.post("/game/action", json={
        "session_id": sid, "acao": "atacar", "alvo": "Fantasma inventado", "turno_esperado": 1,
    })
    assert resposta.status_code == 400
    assert client.post("/load_game", json={"session_id": sid}).json()["turno_mundo"] == 1


def test_habilidade_classe_resolve_e_consume_foco(monkeypatch):
    sid = _partida(monkeypatch)
    resposta = client.post("/game/action", json={
        "session_id": sid, "acao": "usar_habilidade", "habilidade": "golpe_tatico",
        "alvo": "Sentinela", "turno_esperado": 1,
    })
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["inimigos"][0]["hp"] < 100
    assert resposta.json()["progressao"]["recurso"]["atual"] == 2


def test_resgate_vence_sem_matar_e_so_recompensa_uma_vez(monkeypatch):
    sid = _partida(monkeypatch, "resgate")
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        # Maior que a CD mesmo com d20=1: testa o contrato do objetivo, não sorte.
        heroi.atributos = {"forca": 50, "destreza": 14}
        db.commit()
    for turno in (1, 2, 3):
        resposta = client.post("/game/action", json={
            "session_id": sid, "acao": "interagir", "interacao": "objetivo", "turno_esperado": turno,
        })
        assert resposta.status_code == 200, resposta.text
    estado = resposta.json()
    assert not estado["combat_active"]
    assert estado["resultado_combate"] == "vitoria"
    assert estado["inimigos"][0]["hp"] == 100
    assert estado["monstros_derrotados"] == {}
    assert any("Libertou" in m for m in estado["marcos"])
    assert estado["xp"] > 0
    repetido = client.post("/game/action", json={
        "session_id": sid, "acao": "interagir", "interacao": "objetivo", "turno_esperado": 4,
    })
    assert repetido.status_code == 400
    salvo = client.post("/load_game", json={"session_id": sid}).json()
    assert salvo["xp"] == estado["xp"]


def test_todos_cenarios_tem_interacoes_validas_e_persistentes(monkeypatch):
    sid = _partida(monkeypatch)
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        mundo = WorldState(local="Ponte", semente_aventura=12)
        for cenario in CENARIOS:
            combate = CombatState.model_validate(heroi.combat_state)
            preparar_encontro(combate, mundo, cenario)
            salvo = CombatState.model_validate(combate.model_dump())
            assert painel_cena(salvo, mundo)["tipo"] == cenario
            executor = ToolExecutor(heroi, salvo, mundo, QuestLog(), random.Random(3))
            resultado = interagir_cenario(executor, CENARIOS[cenario]["interacoes"][0]["id"])
            assert "erro" not in resultado


def test_acao_de_outro_usuario_e_rejeitada(monkeypatch):
    sid = _partida(monkeypatch)
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        heroi.usuario_id = 999999
        db.commit()
    assert client.post("/game/action", json={
        "session_id": sid, "acao": "defender", "turno_esperado": 1,
    }).status_code == 403
