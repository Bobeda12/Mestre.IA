"""Etapa 8 (ADR-0014) — login por senha, login opcional com Google, e
autorização por recurso. `tests/conftest.py` loga um usuário fixo
automaticamente para todo o resto da suíte; aqui é o próprio login que
está sendo testado, então a fixture `client` abaixo desliga aquele
override.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import get_current_user
from tests.test_smoke import _payload_base


@pytest.fixture
def client(_usuario_autenticado):
    """TestClient próprio por teste — evita que o cookie de sessão de um
    teste vaze para o próximo (o TestClient guarda cookies pela sua vida
    inteira, e um `client` de módulo compartilhado, como o resto da suíte
    usa, ficaria "logado" depois do primeiro teste que fizer login).

    Depende explicitamente de `_usuario_autenticado` (conftest.py) só para
    garantir a ordem: ela roda primeiro e liga o override, esta fixture
    desliga por cima — sem essa dependência explícita, a ordem entre duas
    fixtures `autouse` de arquivos diferentes não é garantida."""
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def dois_clientes(_usuario_autenticado):
    """Para os testes de IDOR: dois `TestClient` independentes, cada um vai
    logar como um usuário diferente."""
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app), TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _registrar(client: TestClient, email: str, senha: str = "senha-forte-123") -> None:
    resp = client.post("/auth/registrar", json={"email": email, "senha": senha})
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Registro e login por senha
# ---------------------------------------------------------------------------


def test_registrar_e_login_funcionam(client):
    _registrar(client, "jogador@teste.com")
    assert client.get("/auth/eu").json()["email"] == "jogador@teste.com"

    client.post("/auth/sair")
    assert client.get("/auth/eu").status_code == 401

    resp = client.post("/auth/login", json={"email": "jogador@teste.com", "senha": "senha-forte-123"})
    assert resp.status_code == 200
    assert client.get("/auth/eu").json()["email"] == "jogador@teste.com"


def test_registrar_email_duplicado_e_rejeitado(client):
    _registrar(client, "duplicado@teste.com")
    resp = client.post("/auth/registrar", json={"email": "duplicado@teste.com", "senha": "outra-senha-123"})
    assert resp.status_code == 409


def test_registrar_senha_curta_e_rejeitada(client):
    resp = client.post("/auth/registrar", json={"email": "senhacurta@teste.com", "senha": "123"})
    assert resp.status_code == 422


def test_registrar_email_invalido_e_rejeitado(client):
    resp = client.post("/auth/registrar", json={"email": "nao-e-email", "senha": "senha-forte-123"})
    assert resp.status_code == 422


def test_login_com_senha_errada_e_rejeitado(client):
    _registrar(client, "senhacerta@teste.com")
    client.post("/auth/sair")
    resp = client.post("/auth/login", json={"email": "senhacerta@teste.com", "senha": "senha-errada"})
    assert resp.status_code == 401


def test_login_de_email_inexistente_e_rejeitado(client):
    resp = client.post("/auth/login", json={"email": "ninguem@teste.com", "senha": "qualquer-coisa"})
    assert resp.status_code == 401


def test_eu_sem_cookie_devolve_401(client):
    assert client.get("/auth/eu").status_code == 401


def test_sair_apaga_a_sessao(client):
    _registrar(client, "vaisair@teste.com")
    assert client.get("/auth/eu").status_code == 200
    client.post("/auth/sair")
    assert client.get("/auth/eu").status_code == 401


def test_criar_personagem_sem_login_devolve_401(client):
    resp = client.post("/create_character", json=_payload_base(nome="SemLogin"))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Login com Google
# ---------------------------------------------------------------------------


def test_opcoes_google_desabilitado_sem_credenciais(client, monkeypatch):
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", None)
    monkeypatch.setattr(settings, "google_client_secret", None)
    assert client.get("/auth/opcoes").json() == {"google_disponivel": False}


def test_google_iniciar_sem_configuracao_devolve_503(client, monkeypatch):
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", None)
    resp = client.get("/auth/google/iniciar", follow_redirects=False)
    assert resp.status_code == 503


def test_google_iniciar_seta_cookie_de_state_e_redireciona(client, monkeypatch):
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")

    resp = client.get("/auth/google/iniciar", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]
    assert "oauth_state" in resp.cookies


def test_google_callback_sem_state_valido_e_rejeitado(client, monkeypatch):
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")

    resp = client.get("/auth/google/callback?code=abc&state=nunca-emitido", follow_redirects=False)
    assert resp.status_code == 400


def test_google_callback_cria_conta_e_loga(client, monkeypatch):
    from app import routers
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")

    iniciar = client.get("/auth/google/iniciar", follow_redirects=False)
    state = iniciar.headers["location"].split("state=")[1].split("&")[0]

    monkeypatch.setattr(
        routers.auth,
        "trocar_code_por_userinfo",
        lambda code: {"sub": "google-123", "email": "google@teste.com", "email_verified": True},
    )

    callback = client.get(f"/auth/google/callback?code=fake-code&state={state}", follow_redirects=False)
    assert callback.status_code in (302, 307)
    assert "sessao" in callback.cookies

    assert client.get("/auth/eu").json()["email"] == "google@teste.com"


def test_login_com_senha_em_conta_so_google_e_rejeitado(client, monkeypatch):
    from app import routers
    from app.infra.settings import settings

    monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")
    monkeypatch.setattr(
        routers.auth,
        "trocar_code_por_userinfo",
        lambda code: {"sub": "google-456", "email": "sogoogle@teste.com", "email_verified": True},
    )

    iniciar = client.get("/auth/google/iniciar", follow_redirects=False)
    state = iniciar.headers["location"].split("state=")[1].split("&")[0]
    client.get(f"/auth/google/callback?code=fake-code&state={state}", follow_redirects=False)
    client.post("/auth/sair")

    resp = client.post("/auth/login", json={"email": "sogoogle@teste.com", "senha": "qualquer-coisa"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Autorização por recurso (IDOR)
# ---------------------------------------------------------------------------


def test_personagem_de_outro_usuario_devolve_403(dois_clientes, monkeypatch):
    from app.services import narrator

    monkeypatch.setattr(narrator, "client", None)
    cliente_a, cliente_b = dois_clientes
    _registrar(cliente_a, "dona@teste.com")
    _registrar(cliente_b, "intrusa@teste.com")

    criado = cliente_a.post("/create_character", json=_payload_base(nome="HeroiDaDona"))
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]

    # B tenta acessar o personagem de A trocando o session_id no pedido —
    # o cenário de IDOR que o plano da Etapa 8 pede explicitamente.
    resp_load = cliente_b.post("/load_game", json={"session_id": session_id})
    assert resp_load.status_code == 403

    resp_chat = cliente_b.post("/chat", json={"session_id": session_id, "action": "Eu olho ao redor"})
    assert resp_chat.status_code == 403

    # A continua acessando o próprio personagem normalmente.
    assert cliente_a.post("/load_game", json={"session_id": session_id}).status_code == 200


def test_personagens_lista_so_os_do_dono(dois_clientes, monkeypatch):
    from app.services import narrator

    monkeypatch.setattr(narrator, "client", None)
    cliente_a, cliente_b = dois_clientes
    _registrar(cliente_a, "colecionador@teste.com")
    _registrar(cliente_b, "outrocolecionador@teste.com")

    cliente_a.post("/create_character", json=_payload_base(nome="HeroiListaA"))

    lista_a = cliente_a.get("/personagens")
    lista_b = cliente_b.get("/personagens")
    assert lista_a.status_code == 200
    assert any(p["nome"] == "HeroiListaA" for p in lista_a.json())
    assert all(p["nome"] != "HeroiListaA" for p in lista_b.json())


def test_arquivar_personagem_de_outro_usuario_devolve_403(dois_clientes, monkeypatch):
    from app.services import narrator

    monkeypatch.setattr(narrator, "client", None)
    cliente_a, cliente_b = dois_clientes
    _registrar(cliente_a, "dona2@teste.com")
    _registrar(cliente_b, "intrusa2@teste.com")

    criado = cliente_a.post("/create_character", json=_payload_base(nome="HeroiArquivavel"))
    session_id = criado.json()["session_id"]

    resp = cliente_b.patch(f"/personagens/{session_id}/arquivar")
    assert resp.status_code == 403

    resp_dono = cliente_a.patch(f"/personagens/{session_id}/arquivar")
    assert resp_dono.status_code == 200
    assert all(p["nome"] != "HeroiArquivavel" for p in cliente_a.get("/personagens").json())


# ---------------------------------------------------------------------------
# Rate limit (Etapa 9) — força bruta em /auth/login
# ---------------------------------------------------------------------------


def test_login_tem_rate_limit_por_ip(client):
    """`app/infra/rate_limit.py` limita `/auth/login` a 10/minuto por IP —
    sem isto, a verificação de senha aceitava tentativas ilimitadas."""
    for _ in range(10):
        resp = client.post("/auth/login", json={"email": "ninguem@teste.com", "senha": "tentativa-errada"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"email": "ninguem@teste.com", "senha": "tentativa-errada"})
    assert resp.status_code == 429
