"""
Prova que a API sobe e responde — substitui o antigo Backend/teste.py,
que exigia um `uvicorn` rodando à mão em outro terminal e nunca
verificava nada com `assert`.

O TestClient do FastAPI sobe a aplicação em processo, sem precisar de
um servidor ativo nem de rede.
"""

import json

from fastapi.testclient import TestClient

from app.infra import llm_client
from app.main import app

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
    monkeypatch.setattr(llm_client, "clients", {})

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
    monkeypatch.setattr(llm_client, "clients", {})
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


def test_imagem_persiste_e_volta_no_load_game(monkeypatch):
    # Etapa 11 (B-3): a foto gerada na criação não pode mais se perder ao
    # recarregar — antes só vivia em `location.state`, agora é uma coluna.
    monkeypatch.setattr(llm_client, "clients", {})
    payload = _payload_base(imagem="https://image.pollinations.ai/prompt/teste")
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 200
    dados = client.post("/load_game", json={"session_id": resp.json()["session_id"]}).json()
    assert dados["imagem"] == "https://image.pollinations.ai/prompt/teste"


def test_historia_texto_persiste_e_volta_no_load_game(monkeypatch):
    # Etapa 11 (B-7, resolve P-4): antes, historia_texto entrava no prompt
    # do prólogo e nunca era gravado — a tela de abertura precisa dele.
    monkeypatch.setattr(llm_client, "clients", {})
    payload = _payload_base(historia_texto="Nasceu numa vila que o fogo levou.")
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 200
    dados = client.post("/load_game", json={"session_id": resp.json()["session_id"]}).json()
    assert dados["historia_texto"] == "Nasceu numa vila que o fogo levou."


def test_local_inicial_novo_com_descricao_e_registrado_em_locais_descobertos(monkeypatch):
    # Rodada de conserto (Parte 2, item J) — "chega de goblins", ponto de
    # partida: quando o prólogo aceita um local fora do catálogo (com
    # descrição), `create_character` precisa registrar ele em
    # `WorldState.locais_descobertos` — senão o herói "nasceria" num lugar
    # que o resto do motor nunca ouviu falar (`mover` recusaria).
    from app.routers import character

    monkeypatch.setattr(
        character,
        "gerar_prologo_missao",
        lambda char, chamar_fn=None: {
            "local_inicial": "Vilarejo de Corvoceu",
            "local_inicial_descricao": "Um vilarejo de pescadores encravado num penhasco.",
            "clima_inicial": "Nublado",
            "nome_missao": "Missão",
            "objetivo_missao": "Objetivo",
            "intro_narrativa": "Texto.",
            "atos": [
                {"titulo": "A", "objetivo": "a"},
                {"titulo": "B", "objetivo": "b"},
                {"titulo": "C", "objetivo": "c"},
            ],
        },
    )
    resp = client.post("/create_character", json=_payload_base(nome="TesteLocalNovo"))
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    from app.infra.db import Personagem, SessionLocal

    db = SessionLocal()
    try:
        heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
        assert heroi.world_state["local"] == "Vilarejo de Corvoceu"
        descoberto = heroi.world_state["locais_descobertos"]["Vilarejo de Corvoceu"]
        assert "penhasco" in descoberto["descricao"]
    finally:
        db.close()


def test_load_game_sem_resumo_nao_traz_anteriormente(monkeypatch):
    # Parte 2 (item G) da rodada de conserto — campanha nova, sem turnos
    # resumidos ainda: nada para recapitular.
    monkeypatch.setattr(llm_client, "clients", {})
    resp = client.post("/create_character", json=_payload_base(nome="TesteSemAnteriormente"))
    dados = client.post("/load_game", json={"session_id": resp.json()["session_id"]}).json()
    assert dados["anteriormente"] is None


def test_load_game_traz_anteriormente_a_partir_do_resumo_rolante(monkeypatch):
    # Parte 2 (item G) — "Anteriormente…": três fatos do resumo rolante
    # (Etapa 5) pro jogador que volta a uma campanha em andamento lembrar
    # onde parou, sem esperar o histórico de chat inteiro rolar de volta.
    monkeypatch.setattr(llm_client, "clients", {})
    resp = client.post("/create_character", json=_payload_base(nome="TesteComAnteriormente"))
    session_id = resp.json()["session_id"]

    from app.infra.db import Personagem, SessionLocal

    db = SessionLocal()
    try:
        heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
        heroi.resumo_rolante = {
            "fatos_estabelecidos": ["O ferreiro é o irmão perdido do herói."],
            "mudancas_no_mundo": ["A ponte do vilarejo desabou."],
            "npcs_conhecidos": [],
            "promessas_feitas": [],
        }
        db.commit()
    finally:
        db.close()

    dados = client.post("/load_game", json={"session_id": session_id}).json()
    assert "A ponte do vilarejo desabou." in dados["anteriormente"]
    assert "O ferreiro é o irmão perdido do herói." in dados["anteriormente"]


def test_historia_texto_vira_primeiro_evento_de_memoria(monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    payload = _payload_base(nome="TesteMemoriaHistoria", historia_texto="Um segredo que ninguém mais sabe.")
    resp = client.post("/create_character", json=payload)
    session_id = resp.json()["session_id"]

    from app.infra.db import EventoMemoria, Personagem, SessionLocal

    db = SessionLocal()
    try:
        heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
        evento = db.query(EventoMemoria).filter(EventoMemoria.personagem_id == heroi.id).first()
        assert evento is not None
        assert evento.tipo == "historia_pessoal"
        assert evento.texto == "Um segredo que ninguém mais sabe."
    finally:
        db.close()


def test_historia_texto_vazia_nao_cria_evento_de_memoria(monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    payload = _payload_base(nome="TesteSemHistoria")
    resp = client.post("/create_character", json=payload)
    session_id = resp.json()["session_id"]

    from app.infra.db import EventoMemoria, Personagem, SessionLocal

    db = SessionLocal()
    try:
        heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
        assert db.query(EventoMemoria).filter(EventoMemoria.personagem_id == heroi.id).count() == 0
    finally:
        db.close()


def test_imagem_sem_url_valida_e_rejeitada():
    payload = _payload_base(imagem="javascript:alert(1)")
    resp = client.post("/create_character", json=payload)
    assert resp.status_code == 422


def test_chat_sem_chave_de_api_devolve_mensagem_explicita(monkeypatch):
    """O bug original (api.py, versão anterior às Etapas 1 e 2) engolia qualquer
    erro num `except:` nu e respondia sempre a mesma narrativa "...". Agora
    cada causa de falha tem uma mensagem própria — aqui testamos a mais
    comum: nenhuma chave de API configurada. `/chat` (loop de agente, Etapa
    4) e `/create_character` (prólogo, narrator.py) checam o mesmo
    `llm_client.clients` (Etapa 14, ADR-0024) — um só patch cobre os dois."""
    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteErro"))
    session_id = criado.json()["session_id"]

    resp = client.post("/chat", json={"session_id": session_id, "action": "Eu ataco"})
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["erro"] is True
    # Etapa 10 (A-7): a mensagem vira um campo próprio (`erro_mensagem`),
    # não texto embutido em `narrativa` com `*(...)*`.
    assert "chave" in dados["erro_mensagem"].lower()
    assert dados["narrativa"] == ""


def test_chat_de_sessao_inexistente_devolve_404():
    resp = client.post("/chat", json={"session_id": "isso-nao-existe", "action": "Eu ataco"})
    assert resp.status_code == 404


def test_load_game_de_sessao_inexistente_devolve_404():
    resp = client.post("/load_game", json={"session_id": "isso-nao-existe"})
    assert resp.status_code == 404


def test_chat_com_ferramenta_chamada_de_ponta_a_ponta(monkeypatch):
    """Sobe o /chat inteiro (Etapa 4) com um LLM falso roteirizado — chama a
    ferramenta `mover`, depois entrega a narrativa final — provando que
    routers/game.py, services/agent_loop.py e services/tools.py estão
    ligados de verdade, sem precisar de rede nem de GROQ_API_KEY."""
    from app.services import agent_loop
    from tests.test_agent_loop import _LLMFalso, _MensagemFalsa, _ToolCallFalso

    monkeypatch.setattr(llm_client, "clients", {})  # prólogo cai no fallback determinístico, sem rede
    criado = client.post("/create_character", json=_payload_base(nome="TesteFerramentaChat"))
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]

    fake = _LLMFalso(
        [
            _MensagemFalsa(tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta das Sombras"}')]),
            _MensagemFalsa(content="Vocês seguem para a floresta, sob galhos retorcidos."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)

    resp = client.post("/chat", json={"session_id": session_id, "action": "Eu vou para a floresta"})
    assert resp.status_code == 200
    dados = resp.json()
    assert "erro" not in dados
    assert "Vocês seguem para a floresta" in dados["narrativa"]
    assert "🧭" in dados["narrativa"]  # evento da ferramenta mover anexado
    assert "ouro" in dados


def test_chat_stream_de_ponta_a_ponta(monkeypatch):
    """Mesma prova de ponta a ponta de `test_chat_com_ferramenta_chamada_de_
    ponta_a_ponta`, mas em `/chat/stream` (Etapa 7): confere que o frame
    `token` chega em pedaços, o `tool_event` carrega o dado estruturado do
    `mover`... na verdade `mover` não é uma rolagem (sem EventoRolagem), então
    o que este teste prova é que o frame `state` final tem a narrativa
    completa e persistida, igual ao `/chat` síncrono."""
    from app.services import agent_loop
    from tests.test_agent_loop import _ChunkFalso, _DeltaFalso, _DeltaToolCallFalso, _StreamLLMFalso

    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteStreamChat"))
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]

    tc = _DeltaToolCallFalso(0, id="t1", name="mover", arguments='{"destino": "Floresta das Sombras"}')
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[tc]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Vocês seguem ")), _ChunkFalso(_DeltaFalso(content="para a floresta."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    monkeypatch.setattr(agent_loop, "chamar_stream_com_fallback", fake)

    resp = client.post("/chat/stream", json={"session_id": session_id, "action": "Eu vou para a floresta"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    corpo = resp.text
    assert "event: token" in corpo
    assert "Vocês seguem " in corpo

    frames = [f for f in corpo.strip().split("\n\n") if f]
    assert frames[-1].startswith("event: state")
    dados_state = json.loads(frames[-1].split("data: ", 1)[1])
    assert "Vocês seguem para a floresta." in dados_state["narrativa"]
    assert "🧭" in dados_state["narrativa"]  # evento da ferramenta mover, persistido igual ao /chat
    assert "ouro" in dados_state


def test_chat_stream_com_chave_propria_de_ponta_a_ponta(monkeypatch):
    """Item F.1 da rodada de conserto — os testes de BYOK existentes
    (`test_telemetria_e_feedback.py`) só batiam em `/chat`, nunca no
    `/chat/stream` que o jogo de verdade usa. É esse caminho (header →
    `ChaveUsuario.chamar_fn_stream` → `chamar_stream_com_chave_usuario`)
    que carregava o bug do `content: null` (ver `agent_loop.py`) — este
    teste teria pegado uma regressão dele."""
    from app.services import agent_loop
    from tests.test_agent_loop import _ChunkFalso, _DeltaFalso, _DeltaToolCallFalso, _StreamLLMFalso

    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteStreamByok"))
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]

    tc = _DeltaToolCallFalso(0, id="t1", name="mover", arguments='{"destino": "Floresta das Sombras"}')
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[tc]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Vocês seguem para a floresta."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    # `ChaveUsuario.chamar_fn_stream` é um `functools.partial` de
    # `llm_client.chamar_stream_com_chave_usuario` — não de
    # `chamar_stream_com_fallback` (esse é o caminho da chave do servidor,
    # que este teste não deve exercitar).
    monkeypatch.setattr(agent_loop, "chamar_stream_com_fallback", None)  # não deveria ser chamado
    monkeypatch.setattr(llm_client, "chamar_stream_com_chave_usuario", lambda msgs, api_key, **k: fake(msgs, **k))

    resp = client.post(
        "/chat/stream",
        json={"session_id": session_id, "action": "Eu vou para a floresta"},
        headers={"X-Gemini-Key": "chave-de-teste"},
    )
    assert resp.status_code == 200

    corpo = resp.text
    frames = [f for f in corpo.strip().split("\n\n") if f]
    assert frames[-1].startswith("event: state")
    dados_state = json.loads(frames[-1].split("data: ", 1)[1])
    assert "Vocês seguem para a floresta." in dados_state["narrativa"]
    assert fake.chamadas == 2


def test_chat_stream_frame_de_correcao_nao_vaza_tag_nem_markdown(monkeypatch):
    """Item C da rodada de conserto — achado ao vivo: o frame `correcao`
    mandava a narrativa corrigida CRUA (com `[OPCOES]` e markdown ainda
    dentro), porque a limpeza/extração só rodava depois do frame já ter
    saído. O jogador via a tag como texto na tela, sem nenhum botão."""
    from app.routers import game
    from app.services import agent_loop
    from tests.test_agent_loop import _ChunkFalso, _DeltaFalso, _StreamLLMFalso

    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteCorrecaoStream"))
    assert criado.status_code == 200
    session_id = criado.json()["session_id"]

    passo = [_ChunkFalso(_DeltaFalso(content="Você usa sua Espada Longa."))]
    fake = _StreamLLMFalso([passo])
    monkeypatch.setattr(agent_loop, "chamar_stream_com_fallback", fake)
    # Força uma violação (não importa qual) — o que este teste prova é o
    # que acontece DEPOIS da violação, não a heurística que a detecta.
    monkeypatch.setattr(game, "validar_narrativa", lambda *a, **k: ["item fora do inventário"])
    monkeypatch.setattr(
        game,
        "corrigir_narrativa",
        lambda *a, **k: "**Corrigido.**\n[OPCOES]: Atacar|Recuar|Esperar",
    )

    resp = client.post("/chat/stream", json={"session_id": session_id, "action": "Eu ataco"})
    assert resp.status_code == 200

    frames = [f for f in resp.text.strip().split("\n\n") if f]
    frame_correcao = next(f for f in frames if f.startswith("event: correcao"))
    dados_correcao = json.loads(frame_correcao.split("data: ", 1)[1])
    assert "[OPCOES" not in dados_correcao["narrativa"]
    assert "**" not in dados_correcao["narrativa"]
    assert dados_correcao["narrativa"] == "Corrigido."

    dados_state = json.loads(frames[-1].split("data: ", 1)[1])
    assert dados_state["opcoes"] == ["Atacar", "Recuar", "Esperar"]
    assert "[OPCOES" not in dados_state["narrativa"]


def test_cronica_de_sessao_inexistente_devolve_404():
    resp = client.get("/personagens/isso-nao-existe/cronica")
    assert resp.status_code == 404


def test_cronica_sem_eventos_nao_quebra(monkeypatch):
    # Fase 7 da revisão de gameplay (Etapa 12/13) — "Exportar Crônica".
    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteCronicaVazia"))
    session_id = criado.json()["session_id"]

    resp = client.get(f"/personagens/{session_id}/cronica")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["nome"] == "TesteCronicaVazia"
    assert "ainda não tem nada registrado" in dados["cronica"]


def test_cronica_sem_llm_devolve_eventos_crus(monkeypatch):
    from app.services import agent_loop
    from tests.test_agent_loop import _LLMFalso, _MensagemFalsa, _ToolCallFalso

    monkeypatch.setattr(llm_client, "clients", {})
    criado = client.post("/create_character", json=_payload_base(nome="TesteCronicaEventos"))
    session_id = criado.json()["session_id"]

    fake = _LLMFalso(
        [
            _MensagemFalsa(tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta das Sombras"}')]),
            _MensagemFalsa(content="Vocês seguem para a floresta, sob galhos retorcidos."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    resp_chat = client.post("/chat", json={"session_id": session_id, "action": "Eu vou para a floresta"})
    assert resp_chat.status_code == 200

    # Sem client configurado, gerar_cronica cai no fallback (eventos crus
    # colados) — o mesmo padrão de gerar_prologo_missao/gerar_epitafio.
    resp = client.get(f"/personagens/{session_id}/cronica")
    assert resp.status_code == 200
    assert "floresta" in resp.json()["cronica"].lower()
