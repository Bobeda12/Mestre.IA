"""F8 do plano "Trilha do capítulo + Combate v2" (ADR-0042) — identidade das
classes, técnicas com custo/alcance/resistência, Foco que acaba e chefes por
degrau de nível."""

import pytest

from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.services import class_abilities as classes
from app.services import turnos
from app.services.class_abilities import limite_foco, perfil_classe
from app.services.tools import ToolExecutor
from tests.helpers import RngFixo
from tests.test_turno_heroi import _heroi, _jogar, _luta


def _de(classe: str, nivel: int = 3, **campos):
    atributo = perfil_classe(classe)["atributo"]
    atributos = {"forca": 10, "destreza": 12, "constituicao": 12, "inteligencia": 10, "sabedoria": 10, "carisma": 10,
                 atributo: 16}
    return _heroi(classe=classe, nivel=nivel, atributos=atributos, **campos)


def _ataques(ex) -> list[dict]:
    return [d for d in ex.eventos_estruturados if d.get("tipo") == "ataque"]


def _resistencias(ex) -> list[dict]:
    return [d for d in ex.eventos_estruturados if d.get("tipo") == "resistencia"]


# -- o catálogo -----------------------------------------------------------------

@pytest.mark.parametrize("classe", regras.get_classes_list())
def test_toda_classe_tem_traco_e_tecnicas_com_custo_e_alcance(classe):
    perfil = perfil_classe(classe)
    assert perfil["passiva"]["nome"] and perfil["passiva"]["descricao"]
    for h in perfil["habilidades"]:
        assert h["acao"] in ("acao", "bonus")
        assert h["alcance"] in ("corpo", "distancia", "area", "pessoal")
        assert (h["alcance"] == "pessoal") == (h["alvo"] == "heroi")


def test_dez_classes_tem_tecnica_de_acao_bonus():
    com_bonus = {c for c in regras.get_classes_list()
                 if any(h["acao"] == "bonus" for h in perfil_classe(c)["habilidades"])}
    assert set(regras.get_classes_list()) - com_bonus == {"Feiticeiro", "Mago"}


# -- técnicas -----------------------------------------------------------------

def test_tecnica_bonus_deixa_a_acao_livre_no_mesmo_turno():
    heroi, c, w = _luta("Orc", heroi=_de("Guerreiro"))
    c.foco = 2
    r, ok, _ = _jogar(heroi, c, w, "usar_habilidade", RngFixo([4]), habilidade="golpe_tatico", alvo="Orc")
    assert ok and c.bonus_usada and not c.acao_usada and c.foco == 1 and "fim_de_turno" not in r
    r, ok, _ = _jogar(heroi, c, w, "usar_habilidade", habilidade="golpe_tatico", alvo="Orc")
    assert not ok and "ação bônus" in r["erro"]
    r, ok, _ = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")  # ação e bônus gastos: o Orc age
    assert ok and r["fim_de_turno"] is True


def test_tecnica_corpo_a_corpo_avanca_sozinha_e_sem_movimento_nao_gasta_foco():
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Bárbaro"))
    c.foco, c.movimento_usado = 3, True
    r, ok, _ = _jogar(heroi, c, w, "usar_habilidade", habilidade="furia", alvo="Orc")
    assert not ok and "está longe" in r["erro"] and c.foco == 3
    c.movimento_usado = False
    r, ok, _ = _jogar(heroi, c, w, "usar_habilidade", RngFixo([4]), habilidade="furia", alvo="Orc")
    assert ok and c.inimigos[0].distancia == "perto" and c.movimento_usado and c.foco == 1


def test_tecnica_a_distancia_alcanca_de_longe():
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Mago"))
    c.foco = 3
    r, ok, _ = _jogar(heroi, c, w, "usar_habilidade", RngFixo([2, 2, 3, 3]), habilidade="misseis_arcanos", alvo="Orc")
    assert ok and c.inimigos[0].hp < 200 and not c.movimento_usado


def test_efeito_de_controle_so_entra_se_o_alvo_falhar_na_resistencia():
    heroi, c, w = _luta("Orc", heroi=_de("Monge"))
    c.foco = 5
    # dano 1d8 = 4; resistência do Orc: d20 = 1 falha
    _, ok, ex = _jogar(heroi, c, w, "usar_habilidade", RngFixo([4, 1]), habilidade="palma_atordoante", alvo="Orc")
    res = _resistencias(ex)[0]
    assert ok and res["sucesso"] is False and res["cd"] == 8 + 2 + 3  # 8 + proficiência + Destreza 16
    assert c.inimigos[0].hp < 200 and c.inimigos[0].efeitos.get("atordoado") == 1

    heroi, c, w = _luta("Orc", heroi=_de("Monge"))
    c.foco = 5
    _, ok, ex = _jogar(heroi, c, w, "usar_habilidade", RngFixo([4, 20]), habilidade="palma_atordoante", alvo="Orc")
    assert ok and _resistencias(ex)[0]["sucesso"] is True
    assert c.inimigos[0].hp < 200  # o dano entra de qualquer jeito
    assert "atordoado" not in c.inimigos[0].efeitos


def test_marcar_nao_pede_resistencia():
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Patrulheiro", inventario=["Arco Longo"],
                                                    equipamento={"arma": "Arco Longo"}))
    c.foco = 3
    _, ok, ex = _jogar(heroi, c, w, "usar_habilidade", RngFixo([3]), habilidade="marca_cacador", alvo="Orc")
    assert ok and _resistencias(ex) == [] and c.inimigos[0].efeitos["marcado"] == 3


def test_mago_impoe_cd_maior():
    heroi, c, w = _luta("Orc", heroi=_de("Mago"))
    c.foco = 5
    _, _, ex = _jogar(heroi, c, w, "usar_habilidade", RngFixo([4, 20, 2]), habilidade="prisao_gelo", alvo="Orc")
    assert _resistencias(ex)[0]["cd"] == 8 + 2 + 3 + 1


def test_cura_acompanha_o_nivel():
    def curado(nivel: int) -> int:
        heroi, c, w = _luta("Orc", heroi=_de("Clérigo", nivel=nivel, hp_atual=1, hp_max=200))
        c.foco = 5
        _jogar(heroi, c, w, "usar_habilidade", RngFixo([4, 4]), habilidade="santuario")
        return heroi.hp_atual - 1

    assert curado(9) - curado(3) == 6


# -- traços de classe -----------------------------------------------------------

def test_feiticeiro_rola_o_dano_duas_vezes_e_fica_com_o_maior():
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Feiticeiro"))
    c.foco = 5
    # chama_caotica 1d10: rola 2 e 9, vale 9; +3 de Carisma +1 de nível//2; depois a resistência ao fogo
    _jogar(heroi, c, w, "usar_habilidade", RngFixo([2, 9, 20, 2, 2]), habilidade="chama_caotica", alvo="Orc")
    assert 200 - c.inimigos[0].hp == 9 + 3 + 1


def test_ladino_soma_ataque_furtivo_so_contra_alvo_abalado_ou_com_vantagem():
    ladino = dict(inventario=["Rapier"], equipamento={"arma": "Rapier"})
    heroi, c, w = _luta("Orc", heroi=_de("Ladino", **ladino))
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    sem = 200 - c.inimigos[0].hp
    heroi, c, w = _luta("Orc", heroi=_de("Ladino", **ladino))
    c.inimigos[0].efeitos = {"enfraquecido": 2}
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 6, 2]), alvo="Orc")
    assert 200 - c.inimigos[0].hp == sem + 6


@pytest.mark.parametrize("classe, leva_golpe", [("Ladino", False), ("Monge", False), ("Mago", False),
                                                ("Feiticeiro", False), ("Guerreiro", True), ("Clérigo", True)])
def test_quem_recua_sem_levar_golpe_de_oportunidade(classe, leva_golpe):
    heroi, c, w = _luta("Orc", heroi=_de(classe))
    _, ok, ex = _jogar(heroi, c, w, "recuar", RngFixo([2]))
    assert ok and bool(_ataques(ex)) is leva_golpe and c.inimigos[0].distancia == "longe"


def test_patrulheiro_atira_com_vantagem_no_alvo_marcado_de_longe():
    arqueiro = dict(inventario=["Arco Longo"], equipamento={"arma": "Arco Longo"})
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Patrulheiro", **arqueiro))
    c.inimigos[0].efeitos = {"marcado": 3}
    _, _, ex = _jogar(heroi, c, w, "atacar", RngFixo([3, 18, 5, 5, 2, 2]), alvo="Orc")
    assert _ataques(ex)[0]["vantagem"] is True and _ataques(ex)[0]["d20"] == 18
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Guerreiro", **arqueiro))
    c.inimigos[0].efeitos = {"marcado": 3}
    _, _, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2, 2]), alvo="Orc")
    assert _ataques(ex)[0]["vantagem"] is None


def test_barbaro_ganha_foco_ao_ser_ferido():
    heroi, c, w = _luta("Orc", heroi=_de("Bárbaro"))
    assert c.foco == 0
    _jogar(heroi, c, w, "encerrar_turno", RngFixo([19, 4]))  # o Orc acerta
    assert heroi.hp_atual < 30 and c.foco == 1
    heroi, c, w = _luta("Orc", heroi=_de("Guerreiro"))
    _jogar(heroi, c, w, "encerrar_turno", RngFixo([19, 4]))
    assert c.foco == 0


def test_protecao_de_conjurador_cresce_com_o_nivel_e_paladino_resiste_melhor():
    def alvo(classe: str, nivel: int):
        return ToolExecutor(_de(classe, nivel=nivel, defesa=11), CombatState(), WorldState(), QuestLog())._alvo()

    assert alvo("Mago", 1).ca == 11 + 2 and alvo("Mago", 9).ca == 11 + 2 + 3
    assert alvo("Guerreiro", 9).ca == 11
    assert alvo("Paladino", 1).bonus_resistencia == 2 and alvo("Guerreiro", 1).bonus_resistencia == 0


def test_pulso_de_conjurador_bate_mais_forte_e_de_longe():
    heroi, c, w = _luta("Orc", perto=False, heroi=_de("Mago", inventario=[], equipamento={}))
    _, ok, ex = _jogar(heroi, c, w, "atacar", RngFixo([15, 10, 2, 2]), alvo="Orc")
    assert ok and c.inimigos[0].distancia == "longe" or c.rodada == 2  # não precisou chegar perto
    assert _ataques(ex)[0]["dano"] == 10 + 3 + 1  # 1d10 + Inteligência + nível // 2


# -- inimigos -------------------------------------------------------------------

def test_inimigo_que_atravessa_a_cena_ataca_com_desvantagem_so_nessa_vez():
    heroi, c, w = _luta("Orc", perto=False)
    alvo = turnos.Alvo(hp=40, ca=15, atributos=heroi.atributos)
    chegada = turnos.vez_inimigo(c, c.inimigos[0], alvo, RngFixo([18, 3]))
    seguinte = turnos.vez_inimigo(c, c.inimigos[0], alvo, RngFixo([3]))
    dados = [e.dados for e in [*chegada, *seguinte] if hasattr(e, "dados") and getattr(e.dados, "tipo", "") == "ataque"]
    assert dados[0].vantagem is False and dados[0].d20 == 3 and dados[1].vantagem is None


# -- Foco: recurso da jornada -----------------------------------------------------

def test_conjurador_tem_mais_foco():
    assert limite_foco(1, "Guerreiro") == 3 and limite_foco(1, "Mago") == 5
    assert limite_foco(8, "Guerreiro") == 5 and limite_foco(8, "Clérigo") == 7
    assert limite_foco(1) == 3  # sem classe: o valor de antes


def _executor(classe: str = "Guerreiro", **campos) -> ToolExecutor:
    return ToolExecutor(_de(classe, **campos), CombatState(), WorldState(local="Arena"), QuestLog(),
                        RngFixo([1, 20] + [5] * 30))


def test_primeira_luta_comeca_cheia_e_a_seguinte_com_o_que_sobrou():
    ex = _executor("Mago")
    ex.iniciar_combate(["Goblin"])
    assert ex.c_state.foco == ex.c_state.foco_max == limite_foco(3, "Mago")
    ex.c_state.foco = 1
    ex.c_state.ativo = False  # a luta acabou
    ex.rng = RngFixo([1, 20] + [5] * 30)
    ex.iniciar_combate(["Goblin"])
    assert ex.c_state.foco == 1


def test_atacar_nao_devolve_foco_e_defender_devolve_um():
    heroi, c, w = _luta("Orc")
    _jogar(heroi, c, w, "atacar", RngFixo([15, 5, 2]), alvo="Orc")
    assert c.foco == 0
    _jogar(heroi, c, w, "defender")
    assert c.foco == 1


def test_descanso_curto_devolve_metade_do_foco_duas_vezes_e_o_longo_devolve_tudo():
    ex = _executor("Guerreiro", hp_atual=5)
    ex.c_state.foco, ex.c_state.versao = 0, 2
    assert ex.descansar("curto")["foco"] == 2  # metade de 3, arredondada para cima
    assert ex.descansar("curto")["foco"] == 3
    terceiro = ex.descansar("curto")
    assert "erro" in terceiro and "descanso longo" in terceiro["erro"]
    ex.c_state.foco = 0
    ex.w_state.local = next(n for n in regras.get_locations_list() if (regras.get_location(n) or {}).get("seguro"))
    ex.w_state.turno = 50
    assert "erro" not in ex.descansar("longo")
    assert ex.c_state.foco == 3 and ex.w_state.descansos_curtos == 0
    assert "erro" not in ex.descansar("curto")  # o longo zerou a conta


def test_bruxo_recupera_todo_o_foco_no_descanso_curto():
    ex = _executor("Bruxo", hp_atual=5)
    ex.c_state.foco, ex.c_state.versao = 0, 2
    assert ex.descansar("curto")["foco"] == limite_foco(3, "Bruxo")


# -- chefes por degrau ------------------------------------------------------------

@pytest.mark.parametrize("nivel, esperado", [
    (1, {"Bugbear"}), (4, {"Bugbear"}), (5, {"Dragão Jovem"}), (7, {"Dragão Jovem"}),
    (8, {"Lich Menor", "Dragão Adulto Jovem"}), (10, {"Lich Menor", "Dragão Adulto Jovem"}),
])
def test_chefe_do_capitulo_acompanha_o_degrau_de_nivel(nivel, esperado):
    assert set(regras.chefes_para_nivel(nivel)) == esperado


def test_tracos_estao_ligados_as_regras_que_descrevem():
    assert classes.RECUA_SEM_OPORTUNIDADE == {"Ladino", "Monge", "Mago", "Feiticeiro"}
    assert classes.defesa_de_classe("Guerreiro", 10) == 0 and classes.defesa_de_classe("Bruxo", 6) == 4
