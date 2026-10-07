"""F6 do plano "Trilha do capítulo + Combate v2" — as duas chamadas pequenas
de IA do combate: narrar a rodada (a IA só dá voz ao que o juiz resolveu) e
julgar o improviso (a IA escolhe numa lista fechada; o servidor rola)."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.infra import llm_client
from app.infra.db import EventoTelemetria, Personagem, SessionLocal
from app.infra.settings import settings
from app.main import app
from app.services import combate_ia, turnos
from tests.helpers import RngFixo
from tests.test_game_actions import _partida
from tests.test_turno_heroi import _heroi, _jogar, _luta, _textos

client = TestClient(app)


def _ia(conteudo):
    """Dublê do modelo: devolve `conteudo` (texto, ou dict que vira JSON)."""
    def chamar(msgs, **kwargs):
        chamar.msgs, chamar.kwargs, chamar.vezes = msgs, kwargs, chamar.vezes + 1
        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])
    chamar.vezes = 0
    return chamar


def _ia_fora_do_ar(msgs, **kwargs):
    raise RuntimeError("cota esgotada")


# -- fatos: o que vai para a narração ------------------------------------------

def test_fatos_nao_carregam_numero_nem_termo_de_regra():
    eventos = [
        EventoRolagem("🎲 Você ataca Orc com Espada Longa: d20(15)+5=20 vs CA 13 → ACERTO! 9 de dano.",
                      DadosRolagem(tipo="ataque", quem="heroi", alvo="Orc", arma="Espada Longa", sucesso=True, dano=9)),
        EventoRolagem("💀 Orc cai.", EventoStatus(tipo="morte_inimigo", quem="Orc")),
        "👣 Lobo avança até você.",
        EventoRolagem("🎲 Lobo ataca: ...", DadosRolagem(tipo="ataque", quem="Lobo", alvo="heroi", sucesso=False)),
        EventoRolagem("...", DadosRolagem(tipo="resistencia", quem="heroi", sucesso=False, motivo="Veneno")),
        EventoRolagem("...", EventoStatus(tipo="condicao", quem="heroi", valor=3, detalhe="envenenado")),
        "✨ Ganha 50 de XP (150 total).",
        "💰 Saque: 12 de ouro. Total: 40.",
    ]
    fatos = combate_ia.fatos_da_jogada("Atacar Orc", eventos)
    assert fatos == [
        "O jogador escolheu: Atacar Orc.",
        "Você ataca Orc com Espada Longa e acerta.",
        "Orc cai.",
        "Lobo avança até você.",
        "Lobo ataca você e erra.",
        "Você não resiste a Veneno.",
        "Você fica envenenado.",
    ]
    assert not any(ch.isdigit() for f in fatos[1:] for ch in f)


def test_fatos_tem_teto():
    eventos = [f"Evento sem número {'x' * n}" for n in range(40)]
    assert len(combate_ia.fatos_da_jogada("", eventos)) == combate_ia.MAX_FATOS


# -- narração ------------------------------------------------------------------

def test_narracao_usa_os_fatos_e_devolve_prosa_limpa():
    heroi, c, _ = _luta("Orc")
    ia = _ia("  Sua lâmina **corta** o ar e encontra o ombro do orc,\nque recua rosnando.  ")
    prosa = combate_ia.narrar_rodada(heroi, c, "Ponte Velha", ["Você ataca Orc e acerta."], ia)
    assert prosa == "Sua lâmina corta o ar e encontra o ombro do orc, que recua rosnando."
    pedido = ia.msgs[0]["content"]
    assert "Você ataca Orc e acerta." in pedido and "Ponte Velha" in pedido and "Orc (ileso, perto)" in pedido
    assert "tools" not in ia.kwargs  # sem ferramentas: a IA não decide nada aqui


@pytest.mark.parametrize("ruim", [
    "O orc perde 9 pontos de vida.",  # número: só o juiz dá número
    "Curto.",
    "x" * (combate_ia.PROSA_MAX + 1),
    "",
])
def test_prosa_invalida_e_descartada(ruim):
    heroi, c, _ = _luta("Orc")
    assert combate_ia.narrar_rodada(heroi, c, "Ponte", ["Você ataca Orc e acerta."], _ia(ruim)) is None


def test_narracao_sem_ia_ou_sem_fatos_devolve_none(monkeypatch):
    heroi, c, _ = _luta("Orc")
    assert combate_ia.narrar_rodada(heroi, c, "Ponte", ["Você ataca."], _ia_fora_do_ar) is None
    assert combate_ia.narrar_rodada(heroi, c, "Ponte", [], _ia("Uma frase longa o bastante.")) is None
    monkeypatch.setattr(llm_client, "clients", {})
    assert combate_ia.narrar_rodada(heroi, c, "Ponte", ["Você ataca."]) is None


# -- improviso: julgamento -----------------------------------------------------

def test_ia_julga_dentro_da_lista_fechada():
    heroi, c, _ = _luta("Orc", "Lobo")
    ia = _ia({"atributo": "forca", "dificuldade": "dificil", "efeito": "dano_area_leve", "alvo": "i2"})
    j, pela_ia = combate_ia.julgar_improviso("Derrubo o lustre em cima deles", heroi, c, "Salão em ruínas", "", ia)
    assert pela_ia and (j.atributo, j.dificuldade, j.efeito, j.alvo) == ("forca", "dificil", "dano_area_leve", "i2")
    pedido = ia.msgs[0]["content"]
    assert "Derrubo o lustre" in pedido and "i1 = Orc" in pedido and "Salão em ruínas" in pedido
    assert all(efeito in pedido for efeito in combate_ia.EFEITOS)
    assert ia.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("resposta", [
    {"atributo": "sorte", "dificuldade": "media", "efeito": "dano_leve", "alvo": ""},
    {"atributo": "forca", "dificuldade": "impossivel", "efeito": "dano_leve", "alvo": ""},
    {"atributo": "forca", "dificuldade": "media", "efeito": "matar_todos", "alvo": ""},
    {"dano": 999},
    "isto não é json",
])
def test_resposta_fora_da_lista_cai_no_julgamento_do_servidor(resposta):
    heroi, c, _ = _luta("Orc")
    j, pela_ia = combate_ia.julgar_improviso("Empurro o orc contra a parede", heroi, c, "", "i1", _ia(resposta))
    assert pela_ia is False
    assert (j.atributo, j.dificuldade, j.efeito, j.alvo) == ("forca", "media", "desequilibrar", "i1")


def test_alvo_inventado_pela_ia_e_trocado_pelo_do_jogador():
    heroi, c, _ = _luta("Orc")
    ia = _ia({"atributo": "carisma", "dificuldade": "facil", "efeito": "intimidar", "alvo": "i9"})
    j, pela_ia = combate_ia.julgar_improviso("Grito para assustar", heroi, c, "", "i1", ia)
    assert pela_ia and j.alvo == "i1"


def test_sem_ia_o_atributo_sai_das_palavras(monkeypatch):
    heroi, c, _ = _luta("Orc")
    monkeypatch.setattr(llm_client, "clients", {})
    for texto, atributo in (("Grito e provoco o orc", "carisma"), ("Salto por cima da mesa", "destreza"),
                            ("Analiso a armadilha", "inteligencia"), ("Faço qualquer coisa", "forca")):
        j, pela_ia = combate_ia.julgar_improviso(texto, heroi, c)
        assert not pela_ia and j.atributo == atributo
    assert combate_ia.julgar_improviso("Empurro", heroi, c, chamar_fn=_ia_fora_do_ar)[1] is False


# -- improviso: o servidor rola e aplica ---------------------------------------

def _improvisar(heroi, c, w, rng, efeito, dificuldade="media", alvo="i1", atributo="forca"):
    return _jogar(heroi, c, w, "improvisar", rng, atributo=atributo, dificuldade=dificuldade, efeito=efeito,
                  alvo=alvo, descricao="derrubo a estante")


def test_improviso_gasta_a_acao_e_falha_nao_faz_nada():
    heroi, c, w = _luta("Orc")
    r, ok, ex = _improvisar(heroi, c, w, RngFixo([2, 2]), "dano_leve")  # falha; depois o Orc erra
    assert ok and r["sucesso"] is False and c.inimigos[0].hp == 200
    assert r["fim_de_turno"] is True and "não funciona" in _textos(ex)


def test_cd_vem_da_dificuldade_e_soma_atributo_e_proficiencia():
    heroi, c, w = _luta("Orc")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([10, 3, 2]), "dano_leve", dificuldade="dificil")
    teste = ex.eventos_estruturados[0]
    assert teste["cd"] == 16 and teste["bonus"] == 3 + 2 and teste["motivo"] == "derrubo a estante"


def test_efeitos_aplicam_os_numeros_do_servidor():
    heroi, c, w = _luta("Orc")
    _improvisar(heroi, c, w, RngFixo([20, 4, 2]), "dano_leve")
    assert c.inimigos[0].hp == 200 - (4 + 3)  # 1d6 + nível

    heroi, c, w = _luta("Orc")
    _improvisar(heroi, c, w, RngFixo([20]), "derrubar")
    assert turnos.da_vez(c) == "heroi" and c.rodada == 2  # o Orc, atordoado, perdeu a vez

    heroi, c, w = _luta("Orc")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([20, 2, 2]), "empurrar")
    assert "Orc é afastado de você" in _textos(ex) and "Orc avança até você" in _textos(ex)  # e ele volta na vez dele

    heroi, c, w = _luta("Orc")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([20, 10]), "cobertura")
    ataque = next(d for d in ex.eventos_estruturados if d.get("tipo") == "ataque")
    assert ataque["ca"] == heroi.defesa + 3

    heroi, c, w = _luta("Orc")
    _improvisar(heroi, c, w, RngFixo([20, 2]), "vantagem")
    assert c.efeitos_heroi.get("precisao") == 1  # ainda vale no próximo turno do herói


def test_area_fere_todos_uma_vez_por_luta():
    heroi, c, w = _luta("Orc", "Lobo")
    _improvisar(heroi, c, w, RngFixo([20, 3, 3, 2, 2, 2]), "dano_area_leve", alvo="")
    assert [i.hp for i in c.inimigos] == [200 - 4, 200 - 4]  # 1d4 + nível // 2
    _improvisar(heroi, c, w, RngFixo([20, 3, 2, 2, 2]), "dano_area_leve", alvo="")
    assert sorted(i.hp for i in c.inimigos) == [200 - 4 - 6, 200 - 4]  # virou dano em um só


def test_efeito_forte_nunca_sai_por_dificuldade_facil():
    heroi, c, w = _luta("Orc")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([20]), "derrubar", dificuldade="facil")
    assert ex.eventos_estruturados[0]["cd"] == 13
    heroi, c, w = _luta("Orc")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([20, 2, 2]), "distrair", dificuldade="facil")  # Orc: dois d20
    assert ex.eventos_estruturados[0]["cd"] == 10


def test_chefe_nao_cai_nem_se_intimida():
    heroi, c, w = _luta("Dragão Jovem")
    r, ok, _ = _improvisar(heroi, c, w, RngFixo([20, 2]), "derrubar")
    assert ok and r["efeito"] == "desequilibrar" and "atordoado" not in c.inimigos[0].efeitos


def test_repetir_o_mesmo_truque_em_seguida_fica_mais_dificil():
    heroi, c, w = _luta("Orc")
    _improvisar(heroi, c, w, RngFixo([20, 2]), "desequilibrar")
    _, _, ex = _improvisar(heroi, c, w, RngFixo([20, 2]), "desequilibrar")
    assert ex.eventos_estruturados[0]["cd"] == 13 + 3 and "truque repetido" in _textos(ex)


def test_improviso_invalido_e_recusado_sem_gastar_a_acao():
    heroi, c, w = _luta("Orc")
    r, ok, _ = _jogar(heroi, c, w, "improvisar", atributo="sorte", dificuldade="media", efeito="dano_leve")
    assert not ok and c.acao_usada is False


# -- orçamento: as duas chamadas são pequenas ----------------------------------

def test_pedidos_cabem_no_orcamento_mesmo_no_pior_caso():
    heroi = _heroi(nome="Aldebaran das Sete Colinas", inventario=["Espada Longa"] * 20)
    _, c, _ = _luta("Dragão Adulto Jovem", "Golem de Pedra", "Vampiro Jovem", heroi=heroi)
    fatos = ["Um fato comprido de combate " + "x" * 200] * 30
    narracao = combate_ia.prompt_narracao(heroi, c, "L" * 300, fatos)
    improviso = combate_ia.prompt_improviso("i" * 500, heroi, c, "c" * 900)
    assert len(narracao) <= 4500 and len(improviso) <= 3000


# -- caminho real --------------------------------------------------------------

def _clique(sid, acao, esperado, **extra):
    return client.post("/game/action", json={"session_id": sid, "acao": acao, "turno_esperado": esperado, **extra})


def test_api_narra_a_rodada_com_os_fatos_do_servidor_e_grava(monkeypatch):
    sid = _partida(monkeypatch)
    carga = client.post("/load_game", json={"session_id": sid}).json()
    recuo = _clique(sid, "recuar", carga["revisao"]).json()
    assert recuo["narravel"] is False  # o turno ainda está aberto
    fim = _clique(sid, "encerrar_turno", recuo["revisao"]).json()
    assert fim["narravel"] is True
    indice = fim["turno_index"]

    ia = _ia("Você abre distância enquanto a sentinela avança, a lâmina dela raspando a pedra da ponte.")
    monkeypatch.setattr(combate_ia.llm_client, "clients", {"gemini": object()})
    monkeypatch.setattr(combate_ia.llm_client, "chamar_com_fallback", lambda msgs, **k: ia(msgs, **k))
    r = client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": indice})
    assert r.status_code == 200, r.text
    assert r.json()["prosa"].startswith("Você abre distância")
    pedido = ia.msgs[0]["content"]
    # as duas jogadas do mesmo turno entram no pedido
    assert "O jogador escolheu: recuar." in pedido and "Você recua e abre distância." in pedido
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        assert heroi.historico_chat[indice]["prosa"] == r.json()["prosa"]
        assert db.query(EventoTelemetria).filter_by(usuario_id=heroi.usuario_id, tipo="chamada_combate").count() == 1
    # pedir de novo devolve a prosa gravada, sem chamar a IA outra vez
    r2 = client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": indice})
    assert r2.json()["prosa"] == r.json()["prosa"] and ia.vezes == 1


def test_api_sem_ia_devolve_aviso_e_a_luta_segue(monkeypatch):
    sid = _partida(monkeypatch)  # `_partida` zera os provedores
    carga = client.post("/load_game", json={"session_id": sid}).json()
    fim = _clique(sid, "encerrar_turno", carga["revisao"]).json()
    r = client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": fim["turno_index"]})
    assert r.status_code == 200 and r.json()["prosa"] is None and "sem voz" in r.json()["aviso"]
    assert _clique(sid, "encerrar_turno", fim["revisao"]).status_code == 200


def test_api_recusa_narrar_o_que_nao_fechou_rodada(monkeypatch):
    sid = _partida(monkeypatch)
    carga = client.post("/load_game", json={"session_id": sid}).json()
    recuo = _clique(sid, "recuar", carga["revisao"]).json()
    r = client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": recuo["turno_index"]})
    assert r.status_code == 400
    assert client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": 9999}).status_code == 400


def test_api_acima_do_teto_nao_chama_a_ia(monkeypatch):
    sid = _partida(monkeypatch)
    monkeypatch.setattr(settings, "teto_chamadas_combate", 0)
    monkeypatch.setattr(combate_ia.llm_client, "clients", {"gemini": object()})
    monkeypatch.setattr(combate_ia.llm_client, "chamar_com_fallback",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não devia chamar a IA")))
    carga = client.post("/load_game", json={"session_id": sid}).json()
    improviso = _clique(sid, "improvisar", carga["revisao"], proposta="Empurro a sentinela da ponte", alvo="i1")
    assert improviso.status_code == 200, improviso.text  # julgado pelo servidor, sem erro
    assert "Improviso (forca)" in improviso.json()["narrativa"]
    fim = improviso.json()
    if not fim["narravel"]:
        fim = _clique(sid, "encerrar_turno", fim["revisao"]).json()
    r = client.post("/game/narrar_rodada", json={"session_id": sid, "turno_index": fim["turno_index"]})
    assert r.json()["prosa"] is None


def test_api_improvisar_usa_o_julgamento_da_ia_e_o_servidor_rola(monkeypatch):
    sid = _partida(monkeypatch)
    ia = _ia({"atributo": "carisma", "dificuldade": "facil", "efeito": "intimidar", "alvo": "i1"})
    monkeypatch.setattr(combate_ia.llm_client, "clients", {"gemini": object()})
    monkeypatch.setattr(combate_ia.llm_client, "chamar_com_fallback", lambda msgs, **k: ia(msgs, **k))
    carga = client.post("/load_game", json={"session_id": sid}).json()
    r = _clique(sid, "improvisar", carga["revisao"], proposta="Rosno e bato a espada no escudo",
                rotulo="Improvisar: rosno e bato a espada no escudo")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert "Improviso (carisma)" in corpo["narrativa"] and corpo["turno_combate"] is not None
    teste = next(e for e in corpo["eventos_estruturados"] if e["tipo"] == "teste")
    assert teste["cd"] == 10 and teste["atributo"] == "carisma"
    assert "Rosno e bato a espada no escudo" in ia.msgs[0]["content"]


def test_api_improvisar_fora_de_combate_ou_sem_texto_e_recusado(monkeypatch):
    sid = _partida(monkeypatch)
    carga = client.post("/load_game", json={"session_id": sid}).json()
    assert _clique(sid, "improvisar", carga["revisao"], proposta="  ").status_code == 400
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        heroi.combat_state = {**heroi.combat_state, "ativo": False}
        db.commit()
    assert _clique(sid, "improvisar", carga["revisao"], proposta="Derrubo o lustre").status_code == 400
