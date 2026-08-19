"""
Prova que a API sobe e responde — substitui o antigo Backend/teste.py,
que exigia um `uvicorn` rodando à mão em outro terminal e nunca
verificava nada com `assert`.

O TestClient do FastAPI sobe a aplicação em processo, sem precisar de
um servidor ativo nem de rede.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import narrator

client = TestClient(app)


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
    Força client=None para que gerar_prologo_missao (app/services/narrator.py)
    caia no fallback determinístico — o teste fica rápido, gratuito e sem
    dependência da cota da Groq, não importa se quem roda o pytest tem
    GROQ_API_KEY configurada ou não.
    """
    monkeypatch.setattr(narrator, "client", None)

    criado = client.post(
        "/create_character",
        json={
            "nome": "TesteSmoke",
            "raca": "Humano",
            "classe": "Guerreiro",
            "alinhamento": "Neutro",
            "background": "Andarilho",
            "objetivo": "Provar que o sistema roda",
            "atributos": {
                "forca": 15, "destreza": 14, "constituicao": 13,
                "inteligencia": 12, "sabedoria": 10, "carisma": 8,
            },
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
    # Humano dá +1 fixo em todos os atributos (data/races.json) — não tem livre_escolha.
    assert dados["atributos"]["forca"] == 16
    assert dados["defesa"] == 10 + (dados["atributos"]["destreza"] - 10) // 2


def _payload_base(**overrides):
    payload = {
        "nome": "TesteValidacao",
        "raca": "Humano",
        "classe": "Guerreiro",
        "alinhamento": "Neutro",
        "background": "Andarilho",
        "objetivo": "Testar validação",
        "atributos": {
            "forca": 15, "destreza": 14, "constituicao": 13,
            "inteligencia": 12, "sabedoria": 10, "carisma": 8,
        },
    }
    payload.update(overrides)
    return payload


def test_point_buy_acima_do_limite_e_rejeitado():
    payload = _payload_base(atributos={
        "forca": 15, "destreza": 15, "constituicao": 15,
        "inteligencia": 15, "sabedoria": 15, "carisma": 15,
    })
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 422


def test_atributo_fora_do_intervalo_e_rejeitado():
    payload = _payload_base(atributos={
        "forca": 20, "destreza": 14, "constituicao": 13,
        "inteligencia": 12, "sabedoria": 10, "carisma": 8,
    })
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 422


def test_atributos_livre_sem_direito_a_raca_e_rejeitado():
    # Humano não tem livre_escolha; pedir um ponto livre deve ser recusado.
    payload = _payload_base(atributos_livre=["forca"])
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 400


def test_atributos_livre_do_meio_elfo_e_aceito(monkeypatch):
    monkeypatch.setattr(narrator, "client", None)
    # Meio-Elfo (data/races.json): +2 carisma fixo, 2 pontos livres.
    payload = _payload_base(raca="Meio-Elfo", atributos_livre=["forca", "destreza"])
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 200
    dados = client.post("/load_game", json={"session_id": resp.json()["session_id"]}).json()
    assert dados["atributos"]["forca"] == 16
    assert dados["atributos"]["destreza"] == 15
    assert dados["atributos"]["carisma"] == 10


def test_atributos_livre_em_atributo_com_bonus_fixo_e_rejeitado():
    # Meio-Elfo já tem +2 fixo em carisma; não pode usar o ponto livre nele também.
    payload = _payload_base(raca="Meio-Elfo", atributos_livre=["carisma", "forca"])
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 400


def test_chat_sem_chave_de_api_devolve_mensagem_explicita(monkeypatch):
    """O bug original (api.py, versão anterior às Etapas 1 e 2) engolia qualquer
    erro num `except:` nu e respondia sempre a mesma narrativa "...". Agora
    cada causa de falha tem uma mensagem própria — aqui testamos a mais
    comum: a chave da Groq não está configurada."""
    monkeypatch.setattr(narrator, "client", None)
    criado = client.post("/create_character", json=_payload_base(nome="TesteErro"))
    session_id = criado.json()["session_id"]

    resp = client.post("/chat", json={"session_id": session_id, "action": "Eu ataco"})
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["erro"] is True
    assert "chave" in dados["narrativa"].lower()
    assert dados["narrativa"] != "*(...)*"


def test_chat_de_sessao_inexistente_devolve_404():
    resp = client.post("/chat", json={"session_id": "isso-nao-existe", "action": "Eu ataco"})
    assert resp.status_code == 404


def test_load_game_de_sessao_inexistente_devolve_404():
    resp = client.post("/load_game", json={"session_id": "isso-nao-existe"})
    assert resp.status_code == 404
