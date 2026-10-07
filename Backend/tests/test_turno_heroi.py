"""F5 do plano "Trilha do capítulo + Combate v2" — o turno do herói no motor
novo, pelo caminho real (`ToolExecutor.executar` e `/game/action`): ação,
ação bônus e movimento; alcance; condições; fim do turno e a fila."""

import json

from fastapi.testclient import TestClient

from app.domain.state import CombatState, Inimigo, QuestLog, WorldState
from app.infra.db import Personagem, SessionLocal
from app.main import app
from app.services import combat, turnos
from app.services.tools import ToolExecutor
from tests.helpers import RngFixo
from tests.test_game_actions import _partida

client = TestClient(app)
POCAO = "Poção de Cura"


def _heroi(**campos) -> Personagem:
    base = dict(
        nome="Lia", raca="Humano", classe="Guerreiro", nivel=3, xp=900, hp_atual=30, hp_max=30, defesa=16,
        atributos={"forca": 16, "destreza": 12, "constituicao": 12, "inteligencia": 10, "sabedoria": 10, "carisma": 10},
        inventario=["Espada Longa"], equipamento={"arma": "Espada Longa"}, dificuldade="Normal",
        reputacao_npcs={}, monstros_derrotados={}, aliados=[], ouro=0,
    )
    return Personagem(**{**base, **campos})


def _luta(*arquetipos: str, perto: bool = True, heroi: Personagem | None = None, hp_inimigo: int = 200):
    """Luta v2 com o herói na vez e os inimigos depois dele na fila."""
    heroi = heroi or _heroi()
    inimigos: list[Inimigo] = []
    for a in arquetipos:
        criado = combat._criar_inimigo(a)
        assert criado is not None
        inimigos.append(criado.model_copy(update={"hp": hp_inimigo, "max_hp": hp_inimigo}))
    c = CombatState(ativo=True, cenario_id="duelo", inimigos=inimigos)
    turnos.preparar(c, heroi.atributos, RngFixo([1] * len(inimigos) + [20]), perto=perto)
    c.vez, c.rodada = 0, 1
    c.foco = 0  # sem Foco, nenhuma técnica de ação bônus segura o turno: cada teste liga o que quer medir
    return heroi, c, WorldState(local="Arena", versao_progressao=1, versao_mundo=2)


def _jogar(heroi, c, w, nome: str, rng=None, **args):
    ex = ToolExecutor(heroi, c, w, QuestLog(), rng or RngFixo([]))
    resultado, ok = ex.executar(nome, json.dumps(args, ensure_ascii=False))
    return resultado, ok, ex


def _textos(ex) -> str:
    return "\n".join(str(e) for e in ex.eventos)


# -- alcance e movimento ------------------------------------------------------

def test_atacar_alvo_longe_com_espada_avanca_sozinho_e_gasta_o_movimento():
    heroi, c, w = _luta("Orc", perto=False)
    # herói: acerta (15) e dano (5); depois o Orc, na vez dele, erra (2)
    r, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo=c.inimigos[0].nome)
    assert ok, r
    assert c.inimigos[0].distancia == "perto" and c.inimigos[0].hp < 200
    assert "Você avança até Orc" in _textos(ex)


def test_sem_movimento_o_alvo_longe_fica_fora_do_alcance_e_a_acao_nao_e_gasta():
    heroi, c, w = _luta("Orc", perto=False)
    c.movimento_usado = True
    r, ok, _ = _jogar(heroi, c, w, "atacar", alvo="Orc")
    assert not ok and "está longe" in r["erro"]
    assert c.acao_usada is False and c.inimigos[0].hp == 200


def test_arco_atira_de_longe_e_sofre_desvantagem_com_inimigo_colado():
    arqueira = _heroi(inventario=["Arco Longo"], equipamento={"arma": "Arco Longo"})
    heroi, c, w = _luta("Orc", perto=False, heroi=arqueira)
    r, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2, 2]), alvo="Orc")  # depois o Orc avança e erra
    assert ok and c.inimigos[0].distancia in ("longe", "perto")
    assert ex.eventos_estruturados[0]["vantagem"] is None
    heroi, c, w = _luta("Orc", perto=True, heroi=_heroi(inventario=["Arco Longo"], equipamento={"arma": "Arco Longo"}))
    r, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([18, 3, 2, 2]), alvo="Orc")  # dois d20: vale o 3
    ataque = ex.eventos_estruturados[0]
    assert ok and ataque["vantagem"] is False and ataque["d20"] == 3


def test_aproximar_e_recuar_sao_movimento_e_so_um_por_turno():
    heroi, c, w = _luta("Orc", "Manticora", perto=False)
    r, ok, _ = _jogar(heroi, c, w, "aproximar", alvo="i1")
    assert ok and c.inimigos[0].distancia == "perto" and c.movimento_usado and not c.acao_usada
    r, ok, _ = _jogar(heroi, c, w, "recuar")
    assert not ok and "movimento" in r["erro"]


def test_recuar_leva_o_golpe_de_oportunidade_e_afasta_todos():
    heroi, c, w = _luta("Orc")
    r, ok, ex = _jogar(heroi, c, w, "recuar", RngFixo([15, 4]))
    assert ok and r["dano_recebido"] > 0 and heroi.hp_atual == 30 - r["dano_recebido"]
    assert c.inimigos[0].distancia == "longe" and "aproveita a brecha" in _textos(ex)
    assert turnos.da_vez(c) == "heroi" and not c.acao_usada  # recuar não encerra o turno


def test_recuar_sem_ninguem_perto_e_recusado():
    heroi, c, w = _luta("Orc", perto=False)
    r, ok, _ = _jogar(heroi, c, w, "recuar")
    assert not ok and c.movimento_usado is False


# -- condições no herói -------------------------------------------------------

def test_envenenado_ataca_com_desvantagem():
    heroi, c, w = _luta("Orc")
    c.efeitos_heroi = {"envenenado": 2}
    _, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([18, 3, 2]), alvo="Orc")
    assert ok and ex.eventos_estruturados[0]["vantagem"] is False


def test_caido_nao_se_desloca_ate_levantar_e_levantar_gasta_o_movimento():
    heroi, c, w = _luta("Orc", perto=False)
    c.efeitos_heroi = {"caido": 1}
    r, ok, _ = _jogar(heroi, c, w, "aproximar", alvo="Orc")
    assert not ok and "levante-se" in r["erro"]
    r, ok, _ = _jogar(heroi, c, w, "levantar")
    assert ok and "caido" not in c.efeitos_heroi and c.movimento_usado
    r, ok, _ = _jogar(heroi, c, w, "atacar", alvo="Orc")  # longe, e o movimento já foi
    assert not ok and "está longe" in r["erro"]


def test_amedrontado_nao_avanca_e_contido_nao_recua():
    heroi, c, w = _luta("Orc", perto=False)
    c.efeitos_heroi = {"amedrontado": 2}
    r, ok, _ = _jogar(heroi, c, w, "aproximar", alvo="Orc")
    assert not ok and "amedrontado" in r["erro"]
    heroi, c, w = _luta("Orc")
    c.efeitos_heroi = {"contido": 1}
    r, ok, _ = _jogar(heroi, c, w, "recuar")
    assert not ok and "contido" in r["erro"]


def test_enfraquecido_bate_mais_fraco():
    heroi, c, w = _luta("Orc")
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    normal = 200 - c.inimigos[0].hp
    heroi, c, w = _luta("Orc")
    c.efeitos_heroi = {"enfraquecido": 2}
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    assert 200 - c.inimigos[0].hp == normal - 3


# -- economia do turno --------------------------------------------------------

def test_acao_fecha_o_turno_quando_nao_sobra_nada_util_e_o_inimigo_age():
    heroi, c, w = _luta("Orc")
    r, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 15, 4]), alvo="Orc")
    assert ok and r["fim_de_turno"] is True and ex.turno_passou
    assert heroi.hp_atual < 30  # o Orc bateu na vez dele
    assert turnos.da_vez(c) == "heroi" and c.rodada == 2
    assert (c.acao_usada, c.bonus_usada, c.movimento_usado) == (False, False, False)


def test_pocao_e_acao_bonus_e_nao_fecha_o_turno():
    heroi, c, w = _luta("Orc", heroi=_heroi(hp_atual=10, inventario=["Espada Longa", POCAO, POCAO]))
    r, ok, ex = _jogar(heroi, c, w, "usar_item", RngFixo([3, 3]), item=POCAO)
    assert ok and heroi.hp_atual > 10 and c.bonus_usada and not c.acao_usada
    assert "fim_de_turno" not in r and turnos.da_vez(c) == "heroi" and c.rodada == 1
    r, ok, _ = _jogar(heroi, c, w, "usar_item", item=POCAO)
    assert not ok and "ação bônus" in r["erro"]


def test_ferido_com_pocao_na_mochila_o_turno_fica_aberto_depois_da_acao():
    heroi, c, w = _luta("Orc", heroi=_heroi(hp_atual=10, inventario=["Espada Longa", POCAO]))
    r, ok, _ = _jogar(heroi, c, w, "atacar", RngFixo([15, 5]), alvo="Orc")
    assert ok and "fim_de_turno" not in r and c.acao_usada
    r, ok, _ = _jogar(heroi, c, w, "atacar", alvo="Orc")
    assert not ok and "sua ação" in r["erro"]
    r, ok, ex = _jogar(heroi, c, w, "encerrar_turno", RngFixo([2]))
    assert ok and r["fim_de_turno"] is True and c.rodada == 2


def test_de_vida_cheia_a_pocao_nao_segura_o_turno():
    heroi, c, w = _luta("Orc", heroi=_heroi(inventario=["Espada Longa", POCAO]))
    r, ok, _ = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    assert ok and r["fim_de_turno"] is True


def test_quem_luta_de_longe_fica_com_o_turno_aberto_para_recuar():
    arqueira = _heroi(inventario=["Arco Longo"], equipamento={"arma": "Arco Longo"})
    heroi, c, w = _luta("Orc", heroi=arqueira)
    r, ok, _ = _jogar(heroi, c, w, "atacar", RngFixo([18, 15, 5]), alvo="Orc")
    assert ok and "fim_de_turno" not in r  # ainda pode abrir distância


def test_encerrar_sem_agir_passa_a_vez():
    heroi, c, w = _luta("Orc")
    r, ok, _ = _jogar(heroi, c, w, "encerrar_turno", RngFixo([15, 4]))
    assert ok and r["fim_de_turno"] is True and heroi.hp_atual < 30


def test_defender_vale_contra_a_fila_e_expira_no_turno_seguinte():
    heroi, c, w = _luta("Orc")
    r, ok, _ = _jogar(heroi, c, w, "defender")
    assert ok and c.foco == 1 and "fim_de_turno" not in r  # defender devolve 1 de Foco, e o turno segue aberto
    _, _, ex = _jogar(heroi, c, w, "encerrar_turno", RngFixo([11]))
    ataque = next(d for d in ex.eventos_estruturados if d.get("tipo") == "ataque")
    assert ataque["ca"] == 18
    assert c.heroi_bonus_ca == 0  # já expirou: é o turno do herói de novo


def test_veneno_cobra_no_comeco_do_turno_e_some_com_o_tempo():
    heroi, c, w = _luta("Orc")
    c.efeitos_heroi = {"envenenado": 2}
    _jogar(heroi, c, w, "encerrar_turno", RngFixo([2]))
    assert heroi.hp_atual == 30 - turnos.DANO_CONDICAO and c.efeitos_heroi == {"envenenado": 1}
    _jogar(heroi, c, w, "encerrar_turno", RngFixo([2]))
    assert c.efeitos_heroi == {}


def test_heroi_atordoado_perde_a_vez_e_a_fila_anda_duas_vezes():
    heroi, c, w = _luta("Orc")
    c.efeitos_heroi = {"atordoado": 2}  # vale para o próximo turno dele
    r, ok, ex = _jogar(heroi, c, w, "encerrar_turno", RngFixo([2, 2]))
    assert ok and c.rodada == 3 and "perde a vez" in _textos(ex)
    assert not c.acao_usada


def test_inimigo_que_foge_na_vez_dele_encerra_a_luta_com_vitoria():
    heroi, c, w = _luta("Goblin")
    c.inimigos[0].hp = 1  # abaixo do limiar de fuga
    r, ok, _ = _jogar(heroi, c, w, "encerrar_turno")
    assert ok and r["resultado"] == "vitoria" and c.ativo is False


def test_heroi_caido_a_zero_so_pode_resistir():
    heroi, c, w = _luta("Orc", heroi=_heroi(hp_atual=0))
    for nome, args in (("atacar", {"alvo": "Orc"}), ("recuar", {}), ("encerrar_turno", {})):
        r, ok, _ = _jogar(heroi, c, w, nome, **args)
        assert not ok and "inconsciente" in r["erro"]


# -- o que os testes do motor antigo cobriam, agora na fila de turnos ----------

def test_card_do_ataque_diz_a_arma_o_atributo_e_de_onde_vem_o_bonus():
    heroi, c, w = _luta("Orc")
    _, _, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    ataque = ex.eventos_estruturados[0]
    assert ataque["arma"] == "Espada Longa" and ataque["atributo"] == "forca"
    assert ataque["partes_bonus"] == [{"rotulo": "Força", "valor": 3}, {"rotulo": "Proficiência", "valor": 2}]


def test_investir_bate_mais_forte_e_o_inimigo_revida_com_vantagem():
    heroi, c, w = _luta("Orc")
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    normal = 200 - c.inimigos[0].hp
    heroi, c, w = _luta("Orc")
    _, ok, ex = _jogar(heroi, c, w, "investir", RngFixo([15, 5, 3, 4]), alvo="Orc")
    ataques = [d for d in ex.eventos_estruturados if d.get("tipo") == "ataque"]
    assert ok and 200 - c.inimigos[0].hp == normal * 3 // 2
    assert ataques[1]["quem"] == "Orc" and ataques[1]["vantagem"] is True
    assert c.heroi_vantagem_inimiga is None  # a exposição dura só até o turno seguinte do herói


def test_esconder_se_faz_o_inimigo_perder_a_vez_procurando():
    heroi, c, w = _luta("Orc")
    r, ok, ex = _jogar(heroi, c, w, "esconder_se", RngFixo([19]))
    assert ok and r["escondido"] is True and "vasculha" in _textos(ex) and heroi.hp_atual == 30
    assert c.heroi_escondido is False  # já é o turno seguinte


def test_dano_do_cenario_num_inimigo_gasta_a_acao():
    # ferido e com poção: o turno não fecha sozinho depois da ação
    heroi, c, w = _luta("Orc", heroi=_heroi(hp_atual=10, inventario=["Espada Longa", POCAO]))
    r, ok, _ = _jogar(heroi, c, w, "aplicar_dano", RngFixo([4]), alvo="Orc", dado_dano="1d6", motivo="fogo")
    assert ok and c.acao_usada and c.inimigos[0].hp == 196
    r, ok, _ = _jogar(heroi, c, w, "atacar", alvo="Orc")
    assert not ok and "sua ação" in r["erro"]


def test_oleo_de_lamina_e_acao_bonus_e_soma_dois_no_golpe():
    heroi, c, w = _luta("Orc")
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    normal = 200 - c.inimigos[0].hp
    heroi, c, w = _luta("Orc", heroi=_heroi(inventario=["Espada Longa", "Óleo de Lâmina"]))
    r, ok, _ = _jogar(heroi, c, w, "usar_item", item="Óleo de Lâmina")
    assert ok and c.bonus_usada and not c.acao_usada and c.efeitos_heroi.get("lamina")
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    assert 200 - c.inimigos[0].hp == normal + 2


# -- caminho real: /game/action -----------------------------------------------

def test_cliques_de_movimento_e_fim_de_turno_pela_api(monkeypatch):
    sid = _partida(monkeypatch)  # luta salva no formato antigo: é migrada ao carregar
    carga = client.post("/load_game", json={"session_id": sid}).json()
    turno = carga["turno_combate"]
    assert turno["fila"] == ["heroi", "i1"] and turno["vez"] == "heroi"
    assert turno["alcance_ataque"] == "corpo"  # Espada Longa: a tela trava Atacar para alvo longe sem movimento
    assert carga["inimigos"][0]["id"] == "i1" and carga["inimigos"][0]["distancia"] == "perto"

    def clique(acao: str, esperado: int, **extra):
        return client.post("/game/action", json={"session_id": sid, "acao": acao, "turno_esperado": esperado, **extra})

    recuo = clique("recuar", carga["revisao"])
    assert recuo.status_code == 200, recuo.text
    corpo = recuo.json()
    assert corpo["inimigos"][0]["distancia"] == "longe" and corpo["turno_combate"]["movimento_usado"] is True
    assert clique("aproximar", corpo["revisao"], alvo="i1").status_code == 400  # movimento já gasto
    fim = clique("encerrar_turno", corpo["revisao"])
    assert fim.status_code == 200, fim.text
    depois = fim.json()
    assert depois["turno_combate"]["rodada"] == 2 and depois["turno_combate"]["movimento_usado"] is False
    assert "Sentinela ataca" in depois["narrativa"]  # ela agiu na vez dela, de onde estava
    with SessionLocal() as db:
        salvo = db.query(Personagem).filter_by(session_id=sid).one().combat_state
    assert salvo["versao"] == 2 and salvo["rodada"] == 2


def test_resistir_caido_faz_a_fila_andar(monkeypatch):
    sid = _partida(monkeypatch)
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        heroi.hp_atual = 0
        db.commit()
    carga = client.post("/load_game", json={"session_id": sid}).json()
    r = client.post("/game/action", json={"session_id": sid, "acao": "resistir",
                                          "turno_esperado": carga["revisao"]})
    assert r.status_code == 200, r.text
    corpo = r.json()
    if corpo["combat_active"]:
        assert corpo["turno_combate"]["rodada"] == 2 and corpo["turno_combate"]["vez"] == "heroi"


def test_relogio_do_mundo_so_anda_quando_o_heroi_gasta_um_turno(monkeypatch):
    # `revisao` sobe a cada clique (é o que barra o clique repetido); `turno_mundo`
    # é tempo de jogo e não anda com movimento, ação bônus nem clique de painel.
    sid = _partida(monkeypatch)
    carga = client.post("/load_game", json={"session_id": sid}).json()
    turno, revisao = carga["turno_mundo"], carga["revisao"]

    def clique(acao: str, esperado: int, **extra):
        return client.post("/game/action", json={"session_id": sid, "acao": acao, "turno_esperado": esperado, **extra})

    recuo = clique("recuar", revisao).json()
    assert (recuo["turno_mundo"], recuo["revisao"]) == (turno, revisao + 1)
    assert clique("recuar", revisao).status_code == 409  # clique repetido com a revisão velha
    fim = clique("encerrar_turno", recuo["revisao"]).json()
    assert (fim["turno_mundo"], fim["revisao"]) == (turno + 1, revisao + 2)
