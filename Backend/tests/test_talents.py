"""Fase 3 do plano "jogo completo" (ADR-0034) — escolha de nível pelo jogador."""

from app.domain.state import CombatState, Inimigo, WorldState
from app.services import talents
from tests.helpers import RngFixo
from tests.test_tools import _executor, _heroi


def _executor_nivel(nivel=2, pendentes=(2,), talentos=(), **kw):
    heroi = _heroi(nivel=nivel, xp=0, hp_max=20, hp_atual=20, classe="Guerreiro", **kw)
    w = WorldState(local="Vila de Phandalin", niveis_pendentes=list(pendentes), talentos=list(talentos))
    return _executor(heroi=heroi, w_state=w), heroi, w


def test_subir_de_nivel_deixa_escolha_pendente():
    heroi = _heroi(xp=90, nivel=1, hp_max=10, hp_atual=10, classe="Guerreiro")
    w = WorldState(local="Vila de Phandalin")
    ex = _executor(heroi=heroi, w_state=w, rng=RngFixo([7]))
    ex._aplicar_xp(10)
    assert heroi.nivel == 2 and w.niveis_pendentes == [2]
    assert any("escolha espera" in str(e) for e in ex.eventos)


def test_opcoes_por_nivel():
    o2 = talents.opcoes_para("Guerreiro", 2, [], {"forca": 20, "destreza": 10})
    assert {"atributo", "talento"} == {o["tipo"] for o in o2}
    assert not any(o["id"] == "forca" for o in o2)  # 20 é o teto
    assert not any(o["id"] == "mestre_de_armas" for o in o2)  # nível mínimo 4
    assert [o["id"] for o in talents.opcoes_para("Guerreiro", 3, [], {})] == ["explorador", "diplomata", "combatente"]
    assert any(o["id"] == "mestre_de_armas" for o in talents.opcoes_para("Guerreiro", 4, [], {}))


def test_escolher_atributo_sobe_e_consome_a_pendencia():
    ex, heroi, w = _executor_nivel()
    r = ex.escolher_nivel(2, "atributo", "forca")
    assert "erro" not in r and heroi.atributos["forca"] == 15 and w.niveis_pendentes == []
    assert "erro" in ex.escolher_nivel(2, "atributo", "forca")  # sem pendência


def test_constituicao_que_muda_o_modificador_da_pv_retroativo():
    ex, heroi, w = _executor_nivel(nivel=4, pendentes=(4,))
    heroi.atributos = {**heroi.atributos, "constituicao": 13}
    ex.escolher_nivel(4, "atributo", "constituicao")
    assert heroi.atributos["constituicao"] == 14 and heroi.hp_max == 24


def test_talento_de_defesa_recalcula_e_sobrevive_ao_equipar():
    ex, heroi, w = _executor_nivel()
    heroi.inventario = ["Escudo"]
    heroi.equipamento = {}
    defesa_antes = 10 + 1  # DES 12
    ex.heroi.defesa = defesa_antes
    r = ex.escolher_nivel(2, "talento", "couro_duro")
    assert r["defesa"] == defesa_antes + 1
    ex2 = _executor(heroi=heroi, w_state=w)
    ex2.equipar("Escudo")
    assert heroi.defesa == defesa_antes + 1 + 2


def _dano_de_um_ataque(w):
    heroi = _heroi(nivel=4, xp=0, hp_max=20, hp_atual=20, classe="Guerreiro")
    goblin = Inimigo(nome="Goblin", hp=30, max_hp=30, ca=5, bonus_ataque=0, dano_dado="1d4")
    c = CombatState(ativo=True, inimigos=[goblin])
    _executor(heroi=heroi, c_state=c, w_state=w, rng=RngFixo([15, 3, 5, 5])).atacar("Goblin")
    return 30 - goblin.hp


def test_talento_de_dano_entra_no_ataque():
    sem = _dano_de_um_ataque(WorldState(local="Vila de Phandalin"))
    com = _dano_de_um_ataque(WorldState(local="Vila de Phandalin", talentos=["mestre_de_armas"]))
    assert com == sem + 1


def test_talento_de_vantagem_e_robusto():
    ex, heroi, w = _executor_nivel(talentos=("sortudo",))
    assert "sortudo" in w.talentos
    ex.rolar_teste("destreza", 15, motivo="equilibrar")
    assert ex.eventos[-1].dados.vantagem is True
    ex3, heroi3, w3 = _executor_nivel(nivel=3, pendentes=(2,))
    ex3.escolher_nivel(2, "talento", "robusto")
    assert heroi3.hp_max == 23  # +1 por nível, 3 níveis


def test_escolha_invalida_ou_em_combate():
    ex, heroi, w = _executor_nivel()
    assert "erro" in ex.escolher_nivel(2, "talento", "inexistente")
    ex.c_state.ativo = True
    assert "erro" in ex.escolher_nivel(2, "atributo", "forca")


def test_especializacao_pelo_mesmo_caminho():
    ex, heroi, w = _executor_nivel(nivel=3, pendentes=(3,))
    r = ex.escolher_nivel(3, "especializacao", "diplomata")
    assert "erro" not in r and w.mundo.especializacoes["3"] == "diplomata"


def test_escolher_nivel_nunca_e_ferramenta_do_narrador():
    from app.services.tools import ToolExecutor, tools_para

    for ativo in (True, False):
        assert "escolher_nivel" not in {t["function"]["name"] for t in tools_para(CombatState(ativo=ativo))}
    assert "escolher_nivel" in ToolExecutor._DESPACHO


def test_painel_traz_pendencias_e_talentos():
    from app.services.progression import painel_progressao

    ex, heroi, w = _executor_nivel(talentos=("couro_duro",))
    painel = painel_progressao(heroi, CombatState(), w)
    assert painel["pendencias"][0]["nivel"] == 2 and painel["talentos"][0]["id"] == "couro_duro"
