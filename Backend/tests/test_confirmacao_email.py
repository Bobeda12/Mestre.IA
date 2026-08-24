"""Etapa 10 (A-2) — confirmação de e-mail bloqueante: registrar/reivindicar
dispara o e-mail (via Resend, ou só logado sem RESEND_API_KEY — ver
`app/infra/email.py`), e `get_current_verified_user` bloqueia jogar até o
link ser clicado. Convidado (sem e-mail) e conta Google (já verificada no
OAuth) não passam por nada disto."""

import pytest
from fastapi.testclient import TestClient

from app import routers
from app.infra import llm_client
from app.infra.db import SessionLocal, Usuario
from app.main import app
from app.services.auth import get_current_user
from tests.test_smoke import _payload_base


@pytest.fixture
def client(_usuario_autenticado):
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def link_capturado(monkeypatch):
    """Substitui o envio de verdade (Resend) por uma lista que guarda
    `(destinatario, link)` — assim o teste pode extrair o token sem
    precisar de conta nenhuma no Resend."""
    capturados: list[tuple[str, str]] = []
    monkeypatch.setattr(
        routers.auth, "enviar_email_confirmacao", lambda destinatario, link: capturados.append((destinatario, link))
    )
    return capturados


def _token_de(link: str) -> str:
    return link.split("token=", 1)[1]


class TestRegistrarDisparaConfirmacao:
    def test_registrar_deixa_email_nao_verificado(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "novo@teste.com", "senha": "senha-forte-123"})
        assert client.get("/auth/eu").json() == {"email": "novo@teste.com", "email_verificado": False}

    def test_registrar_dispara_o_email(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "novo2@teste.com", "senha": "senha-forte-123"})
        assert len(link_capturado) == 1
        destinatario, link = link_capturado[0]
        assert destinatario == "novo2@teste.com"
        assert "token=" in link

    def test_reivindicar_tambem_dispara_o_email(self, client, link_capturado):
        client.post("/auth/convidado")
        client.post("/auth/reivindicar", json={"email": "convidado-vira-conta@teste.com", "senha": "senha-forte-123"})
        assert len(link_capturado) == 1
        assert client.get("/auth/eu").json()["email_verificado"] is False


class TestBloqueioAntesDeConfirmar:
    def test_nao_pode_criar_personagem_sem_confirmar(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "bloqueado@teste.com", "senha": "senha-forte-123"})
        resp = client.post("/create_character", json=_payload_base(nome="HeroiBloqueado"))
        assert resp.status_code == 403

    def test_convidado_nao_e_bloqueado(self, client, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        client.post("/auth/convidado")
        resp = client.post("/create_character", json=_payload_base(nome="HeroiConvidadoLivre"))
        assert resp.status_code == 200

    def test_load_game_continua_acessivel_sem_confirmar(self, client, link_capturado):
        # Rota de leitura — o plano é explícito: bloquear leitura deixaria o
        # jogador sem conseguir nem ver a própria tela pedindo confirmação.
        client.post("/auth/registrar", json={"email": "leitura@teste.com", "senha": "senha-forte-123"})
        resp = client.post("/load_game", json={"session_id": "isso-nao-existe"})
        assert resp.status_code == 404  # não é 403 — passou da checagem de verificação


class TestConfirmar:
    def test_token_valido_verifica_e_redireciona(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "confirma@teste.com", "senha": "senha-forte-123"})
        _destinatario, link = link_capturado[0]
        token = _token_de(link)

        resp = client.get(f"/auth/confirmar?token={token}", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "confirmado=1" in resp.headers["location"]

        assert client.get("/auth/eu").json()["email_verificado"] is True

    def test_confirmar_libera_criar_personagem(self, client, link_capturado, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        client.post("/auth/registrar", json={"email": "libera@teste.com", "senha": "senha-forte-123"})
        token = _token_de(link_capturado[0][1])
        client.get(f"/auth/confirmar?token={token}", follow_redirects=False)

        resp = client.post("/create_character", json=_payload_base(nome="HeroiLiberado"))
        assert resp.status_code == 200

    def test_token_invalido_redireciona_sem_verificar(self, client):
        resp = client.get("/auth/confirmar?token=isto-nao-e-um-token-valido", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "confirmado=0" in resp.headers["location"]

    def test_token_de_outro_proposito_e_rejeitado(self, client):
        # Um cookie de sessão válido não pode virar confirmação de e-mail —
        # os dois usam a mesma chave HMAC, só o `proposito` no payload
        # distingue um do outro.
        from app.services.auth import criar_cookie_sessao

        cookie_sessao = criar_cookie_sessao(1)
        resp = client.get(f"/auth/confirmar?token={cookie_sessao}", follow_redirects=False)
        assert "confirmado=0" in resp.headers["location"]


class TestReenviar:
    def test_reenvia_para_quem_nao_confirmou(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "reenviar@teste.com", "senha": "senha-forte-123"})
        assert len(link_capturado) == 1
        resp = client.post("/auth/confirmar/reenviar")
        assert resp.status_code == 200
        assert len(link_capturado) == 2

    def test_reenviar_sem_login_devolve_401(self, client):
        resp = client.post("/auth/confirmar/reenviar")
        assert resp.status_code == 401

    def test_reenviar_para_convidado_e_rejeitado(self, client):
        client.post("/auth/convidado")
        resp = client.post("/auth/confirmar/reenviar")
        assert resp.status_code == 400

    def test_reenviar_tem_rate_limit(self, client, link_capturado):
        client.post("/auth/registrar", json={"email": "reenviar-limite@teste.com", "senha": "senha-forte-123"})
        for _ in range(3):
            client.post("/auth/confirmar/reenviar")
        resp = client.post("/auth/confirmar/reenviar")
        assert resp.status_code == 429


class TestGoogleJaEntraVerificado:
    def test_conta_criada_via_google_ja_esta_verificada(self, client, monkeypatch):
        from app.infra.settings import settings

        monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
        monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")

        iniciar = client.get("/auth/google/iniciar", follow_redirects=False)
        state = iniciar.headers["location"].split("state=")[1].split("&")[0]
        monkeypatch.setattr(
            routers.auth,
            "trocar_code_por_userinfo",
            lambda code: {"sub": "google-verif", "email": "google-verif@teste.com", "email_verified": True},
        )
        client.get(f"/auth/google/callback?code=fake-code&state={state}", follow_redirects=False)

        assert client.get("/auth/eu").json()["email_verificado"] is True

    def test_google_verifica_conta_que_ja_existia_por_senha(self, client, monkeypatch):
        from app.infra.settings import settings

        db = SessionLocal()
        try:
            db.add(Usuario(email="jasenha@teste.com", senha_hash="pbkdf2_sha256$1$a$b", email_verificado=False))
            db.commit()
        finally:
            db.close()

        monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
        monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")
        iniciar = client.get("/auth/google/iniciar", follow_redirects=False)
        state = iniciar.headers["location"].split("state=")[1].split("&")[0]
        monkeypatch.setattr(
            routers.auth,
            "trocar_code_por_userinfo",
            lambda code: {"sub": "google-vinculado", "email": "jasenha@teste.com", "email_verified": True},
        )
        client.get(f"/auth/google/callback?code=fake-code&state={state}", follow_redirects=False)

        assert client.get("/auth/eu").json()["email_verificado"] is True
