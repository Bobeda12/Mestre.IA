"""Etapa 9 — telemetria de produto (eventos_telemetria) e feedback do
jogador (feedback_narracoes, 👍/👎 por narração)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.infra.db import EventoTelemetria, SessionLocal
from app.main import app
from app.services import narrator
from app.services.auth import get_current_user
from tests.test_smoke import _payload_base


@pytest.fixture
def client(_usuario_autenticado):
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _registrar(client: TestClient, email: str, senha: str = "senha-forte-123") -> None:
    resp = client.post("/auth/registrar", json={"email": email, "senha": senha})
    assert resp.status_code == 201, resp.text


def _eventos_do_tipo(tipo: str) -> list[EventoTelemetria]:
    db = SessionLocal()
    try:
        return db.query(EventoTelemetria).filter(EventoTelemetria.tipo == tipo).all()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Telemetria
# ---------------------------------------------------------------------------


def test_criar_personagem_registra_evento_sessao_criada(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    _registrar(client, "telemetria-criacao@teste.com")

    antes = len(_eventos_do_tipo("sessao_criada"))
    resp = client.post("/create_character", json=_payload_base(nome="HeroiTelemetria"))
    assert resp.status_code == 200, resp.text

    depois = _eventos_do_tipo("sessao_criada")
    assert len(depois) == antes + 1


def test_arquivar_personagem_registra_evento(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    _registrar(client, "telemetria-arquivar@teste.com")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiArquivar2")).json()["session_id"]

    antes = len(_eventos_do_tipo("personagem_arquivado"))
    resp = client.patch(f"/personagens/{session_id}/arquivar")
    assert resp.status_code == 200

    depois = _eventos_do_tipo("personagem_arquivado")
    assert len(depois) == antes + 1


def test_chat_registra_evento_turno(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    _registrar(client, "telemetria-turno@teste.com")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiTurno")).json()["session_id"]

    from app.services import agent_loop

    class _RespostaFalsa:
        class _Choice:
            class _Msg:
                content = "Uma narração qualquer."
                tool_calls = None
            message = _Msg()
        choices = [_Choice()]

    # `agent_loop` importa `chamar_com_fallback` com `from ... import` — o
    # nome vive no NAMESPACE de `agent_loop`, não no de `llm_client`, depois
    # do import. Substituir em `llm_client` não afeta quem `agent_loop`
    # realmente chama (o mesmo padrão usado em tests/test_agent_loop.py).
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", lambda *a, **k: _RespostaFalsa())

    antes = len(_eventos_do_tipo("turno"))
    resp = client.post("/chat", json={"session_id": session_id, "action": "Eu observo o local."})
    assert resp.status_code == 200, resp.text
    assert "turno_index" in resp.json()

    depois = _eventos_do_tipo("turno")
    assert len(depois) == antes + 1


# ---------------------------------------------------------------------------
# Feedback (👍/👎)
# ---------------------------------------------------------------------------


@pytest.fixture
def personagem_com_historico(client, monkeypatch):
    """Um personagem com pelo menos uma narração no histórico — o mínimo
    para exercitar `turno_index` de verdade."""
    monkeypatch.setattr(narrator, "client", None)
    _registrar(client, f"feedback-dono-{uuid.uuid4().hex[:8]}@teste.com")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiFeedback")).json()["session_id"]
    return client, session_id


def test_feedback_do_dono_e_aceito(personagem_com_historico):
    client, session_id = personagem_com_historico
    resp = client.post(f"/personagens/{session_id}/feedback", json={"turno_index": 0, "valor": 1})
    assert resp.status_code == 201, resp.text


def test_feedback_valor_invalido_e_rejeitado(personagem_com_historico):
    client, session_id = personagem_com_historico
    resp = client.post(f"/personagens/{session_id}/feedback", json={"turno_index": 0, "valor": 5})
    assert resp.status_code == 422


def test_feedback_turno_index_fora_do_historico_e_rejeitado(personagem_com_historico):
    client, session_id = personagem_com_historico
    resp = client.post(f"/personagens/{session_id}/feedback", json={"turno_index": 999, "valor": 1})
    assert resp.status_code == 400


def test_feedback_de_outro_usuario_devolve_403(client, monkeypatch):
    """Mesma regra de IDOR do resto do jogo (ADR-0014) — dono só de si mesmo."""
    monkeypatch.setattr(narrator, "client", None)
    cliente_a = client

    from fastapi.testclient import TestClient as _TC

    cliente_b = _TC(app)
    _registrar(cliente_a, "feedback-dona@teste.com")
    _registrar(cliente_b, "feedback-intrusa@teste.com")

    session_id = cliente_a.post("/create_character", json=_payload_base(nome="HeroiFeedbackIDOR")).json()[
        "session_id"
    ]

    resp = cliente_b.post(f"/personagens/{session_id}/feedback", json={"turno_index": 0, "valor": -1})
    assert resp.status_code == 403
