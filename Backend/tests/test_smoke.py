"""
Prova que a API sobe e responde — substitui o antigo Backend/teste.py,
que exigia um `uvicorn` rodando à mão em outro terminal e nunca
verificava nada com `assert`.

O TestClient do FastAPI sobe a aplicação em processo, sem precisar de
um servidor ativo nem de rede.
"""

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_lista_racas():
    resp = client.get("/options/races")
    assert resp.status_code == 200
    opcoes = resp.json()["opcoes"]
    assert "Humano" in opcoes
    assert "Elfo" in opcoes


def test_lista_classes():
    resp = client.get("/options/classes")
    assert resp.status_code == 200
    assert "Guerreiro" in resp.json()["opcoes"]


def test_detalhe_de_raca_existente():
    resp = client.get("/options/races/Anão")
    assert resp.status_code == 200
    assert "bonus_atributos" in resp.json()


def test_detalhe_de_raca_inexistente_nao_quebra():
    resp = client.get("/options/races/Hobbit-do-Condado")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_criar_e_carregar_personagem(monkeypatch):
    """
    Força client=None para que gerar_prologo_missao (api.py:47) caia
    no fallback determinístico — o teste fica rápido, gratuito e sem
    dependência da cota da Groq, não importa se quem roda o pytest tem
    GROQ_API_KEY configurada ou não.
    """
    monkeypatch.setattr(api, "client", None)

    criado = client.post(
        "/create_character",
        json={
            "nome": "TesteSmoke",
            "raca": "Humano",
            "classe": "Guerreiro",
            "alinhamento": "Neutro",
            "background": "Andarilho",
            "objetivo": "Provar que o sistema roda",
        },
    )
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]
    assert session_id.startswith("testesmoke_")

    carregado = client.post("/load_game", json={"session_id": session_id})
    assert carregado.status_code == 200
    dados = carregado.json()
    assert dados["nome"] == "TesteSmoke"
    assert dados["hp_atual"] == dados["hp_max"]
    assert dados["hp_atual"] > 0


def test_load_game_de_sessao_inexistente_devolve_404():
    resp = client.post("/load_game", json={"session_id": "isso-nao-existe"})
    assert resp.status_code == 404
