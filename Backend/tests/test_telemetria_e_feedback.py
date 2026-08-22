"""Etapa 9 — telemetria de produto (eventos_telemetria) e feedback do
jogador (feedback_narracoes, 👍/👎 por narração)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.infra.db import EventoTelemetria, FeedbackNarracao, Personagem, SessionLocal, Usuario
from app.infra.settings import settings
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
    # Igual ao helper de test_auth.py: verifica direto no banco, porque
    # nada aqui é sobre o fluxo de confirmação (Etapa 10, A-2).
    resp = client.post("/auth/registrar", json={"email": email, "senha": senha})
    assert resp.status_code == 201, resp.text
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.email == email).first()
        assert usuario is not None
        usuario.email_verificado = True
        db.commit()
    finally:
        db.close()


def _eventos_do_tipo(tipo: str) -> list[EventoTelemetria]:
    db = SessionLocal()
    try:
        return db.query(EventoTelemetria).filter(EventoTelemetria.tipo == tipo).all()
    finally:
        db.close()


def _ultimo_feedback(session_id: str) -> FeedbackNarracao | None:
    """`turno_index` sozinho não identifica uma linha entre testes — vários
    personagens diferentes têm um `turno_index=0`. Passa pelo `session_id`
    (que é único) até o `personagem_id`, e pega o registro mais recente."""
    db = SessionLocal()
    try:
        personagem = db.query(Personagem).filter(Personagem.session_id == session_id).first()
        assert personagem is not None
        return (
            db.query(FeedbackNarracao)
            .filter(FeedbackNarracao.personagem_id == personagem.id)
            .order_by(FeedbackNarracao.id.desc())
            .first()
        )
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
# Teto de custo por usuário/dia (Etapa 10, A-3)
# ---------------------------------------------------------------------------


class _RespostaFalsa:
    class _Choice:
        class _Msg:
            content = "Uma narração qualquer."
            tool_calls = None
        message = _Msg()
    choices = [_Choice()]


def _preparar_chat_falso(monkeypatch):
    """Mesmo dublê de `test_chat_registra_evento_turno` — o teto é checado
    antes de qualquer chamada à Groq, então nem precisaria de um dublê
    realista, mas os turnos que passam do teto ainda completam de verdade
    (senão não estariam "gastos")."""
    from app.services import agent_loop

    monkeypatch.setattr(agent_loop, "chamar_com_fallback", lambda *a, **k: _RespostaFalsa())


def test_teto_diario_bloqueia_apos_o_limite(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    monkeypatch.setattr(settings, "teto_turnos_conta", 2)
    _preparar_chat_falso(monkeypatch)
    _registrar(client, "teto-conta@teste.com")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiTeto")).json()["session_id"]

    for _ in range(2):
        resp = client.post("/chat", json={"session_id": session_id, "action": "Eu observo."})
        assert resp.status_code == 200, resp.text

    resp = client.post("/chat", json={"session_id": session_id, "action": "Eu observo de novo."})
    assert resp.status_code == 429
    assert "amanhã" in resp.json()["detail"]


def test_teto_diario_do_convidado_e_menor(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    monkeypatch.setattr(settings, "teto_turnos_convidado", 1)
    _preparar_chat_falso(monkeypatch)
    client.post("/auth/convidado")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiTetoConvidado")).json()["session_id"]

    resp1 = client.post("/chat", json={"session_id": session_id, "action": "Eu observo."})
    assert resp1.status_code == 200, resp1.text

    resp2 = client.post("/chat", json={"session_id": session_id, "action": "Eu observo de novo."})
    assert resp2.status_code == 429


def test_teto_diario_e_por_usuario_nao_global(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    monkeypatch.setattr(settings, "teto_turnos_conta", 1)
    _preparar_chat_falso(monkeypatch)
    cliente_a = client
    cliente_b = TestClient(app)
    _registrar(cliente_a, "teto-a@teste.com")
    _registrar(cliente_b, "teto-b@teste.com")

    session_a = cliente_a.post("/create_character", json=_payload_base(nome="HeroiTetoA")).json()["session_id"]
    session_b = cliente_b.post("/create_character", json=_payload_base(nome="HeroiTetoB")).json()["session_id"]

    assert cliente_a.post("/chat", json={"session_id": session_a, "action": "Eu observo."}).status_code == 200
    # B ainda não gastou o teto dele — o de A não afeta o de B.
    assert cliente_b.post("/chat", json={"session_id": session_b, "action": "Eu observo."}).status_code == 200
    assert cliente_a.post("/chat", json={"session_id": session_a, "action": "De novo."}).status_code == 429


def test_teto_diario_bloqueia_o_stream_tambem(client, monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    monkeypatch.setattr(settings, "teto_turnos_conta", 1)
    _preparar_chat_falso(monkeypatch)
    _registrar(client, "teto-stream@teste.com")
    session_id = client.post("/create_character", json=_payload_base(nome="HeroiTetoStream")).json()["session_id"]

    assert client.post("/chat", json={"session_id": session_id, "action": "Eu observo."}).status_code == 200

    resp = client.post("/chat/stream", json={"session_id": session_id, "action": "De novo."})
    assert resp.status_code == 429


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


def test_feedback_com_comentario_e_gravado(personagem_com_historico):
    """Etapa 10 (A-4) — o campo livre do 👎, opcional."""
    client, session_id = personagem_com_historico
    resp = client.post(
        f"/personagens/{session_id}/feedback",
        json={"turno_index": 0, "valor": -1, "comentario": "ficou repetitivo"},
    )
    assert resp.status_code == 201, resp.text

    registro = _ultimo_feedback(session_id)
    assert registro is not None
    assert registro.comentario == "ficou repetitivo"


def test_feedback_sem_comentario_continua_funcionando(personagem_com_historico):
    """O clique de um botão só (sem digitar nada) não pode virar obrigação."""
    client, session_id = personagem_com_historico
    resp = client.post(f"/personagens/{session_id}/feedback", json={"turno_index": 0, "valor": 1})
    assert resp.status_code == 201, resp.text

    registro = _ultimo_feedback(session_id)
    assert registro is not None
    assert registro.comentario is None


def test_feedback_comentario_so_espacos_vira_none(personagem_com_historico):
    client, session_id = personagem_com_historico
    resp = client.post(
        f"/personagens/{session_id}/feedback", json={"turno_index": 0, "valor": -1, "comentario": "   "}
    )
    assert resp.status_code == 201, resp.text

    registro = _ultimo_feedback(session_id)
    assert registro is not None
    assert registro.comentario is None


def test_feedback_comentario_maior_que_500_e_rejeitado(personagem_com_historico):
    client, session_id = personagem_com_historico
    resp = client.post(
        f"/personagens/{session_id}/feedback",
        json={"turno_index": 0, "valor": -1, "comentario": "x" * 501},
    )
    assert resp.status_code == 422


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
