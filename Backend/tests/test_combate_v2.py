"""F4 do plano "Trilha do capítulo + Combate v2" — o motor de turnos novo
(`services/turnos.py`): iniciativa que vale, distância perto/longe, táticas
de monstro lidas da ficha, resistências e condições no herói."""

import random

import pytest

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import combat, turnos
from app.services.turnos import HEROI, Alvo
from tests.helpers import RngFixo

ATRIBUTOS = {"forca": 16, "destreza": 12, "constituicao": 12, "sabedoria": 10}


def _inimigo(arquetipo: str, nome: str | None = None, **campos) -> Inimigo:
    criado = combat._criar_inimigo(arquetipo, nome_exibicao=nome)
    assert criado is not None
    return criado.model_copy(update=campos)


def _luta(*arquetipos: str, iniciativas: list[int] | None = None, perto: bool = False,
          aliados: list[Aliado] | None = None) -> CombatState:
    """Luta preparada. `iniciativas`: d20 de cada inimigo, depois de cada
    aliado, depois do herói (a ordem em que `preparar` rola)."""
    c = CombatState(ativo=True, inimigos=[_inimigo(a) for a in arquetipos], aliados=aliados or [])
    total = len(arquetipos) + len(c.aliados) + 1
    turnos.preparar(c, ATRIBUTOS, RngFixo(iniciativas or [10] * total), perto=perto)
    return c


def _alvo(hp: int = 40, ca: int = 15) -> Alvo:
    return Alvo(hp=hp, ca=ca, atributos=ATRIBUTOS, nivel=3)


def _dados(eventos, tipo=None) -> list:
    return [e.dados for e in eventos if isinstance(e, EventoRolagem) and e.dados is not None
            and (tipo is None or e.dados.tipo == tipo)]


# -- preparação e fila ------------------------------------------------------

def test_preparar_da_id_estavel_distancia_e_fila_por_iniciativa():
    aliados = [Aliado(nome="Dara", hp=10, max_hp=10, ca=12, bonus_ataque=2, dano_dado="1d6")]
    # Orc 5, Lobo 18, Dara 12, herói 15 (+1 de Destreza = 16)
    c = _luta("Orc", "Lobo", iniciativas=[5, 18, 12, 15], aliados=aliados)
    assert [i.id for i in c.inimigos] == ["i1", "i2"] and c.aliados[0].id == "a1"
    assert all(i.distancia == "longe" for i in c.inimigos)
    assert c.fila == ["i2", HEROI, "a1", "i1"]
    assert c.versao == 2


def test_emboscada_comeca_com_todos_perto():
    assert all(i.distancia == "perto" for i in _luta("Orc", "Lobo", perto=True).inimigos)


def test_empate_de_iniciativa_favorece_o_heroi():
    c = _luta("Esqueleto", iniciativas=[9, 10])  # Esqueleto 9+2 = 11; herói 10+1 = 11
    assert c.fila == [HEROI, "i1"]


def test_inimigo_mais_rapido_age_antes_do_heroi():
    c = _luta("Orc", iniciativas=[20, 1])
    alvo = _alvo()
    eventos = turnos.avancar_fila(c, alvo, RngFixo([15, 15, 4]))  # chega e ataca (dois d20: desvantagem); dano 4
    assert turnos.da_vez(c) == HEROI and c.rodada == 1
    assert alvo.hp < 40 and c.inimigos[0].distancia == "perto"
    assert any("avança até você" in str(e) for e in eventos)


def test_heroi_mais_rapido_abre_a_luta_sem_ninguem_agir():
    c = _luta("Orc", iniciativas=[1, 20])
    alvo = _alvo()
    assert turnos.avancar_fila(c, alvo, RngFixo([])) == []
    assert turnos.da_vez(c) == HEROI and c.rodada == 1 and alvo.hp == 40


def test_rodada_sobe_quando_a_fila_da_a_volta():
    c = _luta("Orc", iniciativas=[1, 20])
    alvo = _alvo()
    turnos.avancar_fila(c, alvo, RngFixo([]))
    turnos.avancar_fila(c, alvo, RngFixo([2, 2]))  # o Orc avança e erra
    assert c.rodada == 2 and turnos.da_vez(c) == HEROI


def test_fila_para_quando_nao_sobra_inimigo():
    c = _luta("Orc", iniciativas=[20, 1])
    c.inimigos[0].hp = 0
    assert turnos.avancar_fila(c, _alvo(), RngFixo([])) == []


# -- distância ---------------------------------------------------------------

def test_atirador_fica_longe_e_atira_sem_penalidade():
    c = _luta("Manticora")
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([15, 3, 3, 3]))
    assert c.inimigos[0].distancia == "longe"
    assert _dados(eventos, "ataque")[0].vantagem is None


def test_atirador_com_o_heroi_colado_atira_com_desvantagem():
    c = _luta("Manticora", perto=True)
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([18, 3]))  # dois d20: fica o menor
    ataque = _dados(eventos, "ataque")[0]
    assert ataque.vantagem is False and ataque.d20 == 3


def test_recuar_provoca_ataque_de_oportunidade_de_quem_esta_perto():
    c = _luta("Orc", "Manticora")
    c.inimigos[0].distancia = "perto"  # só o Orc está colado
    alvo = _alvo()
    eventos = turnos.recuar(c, alvo, RngFixo([15, 4]))
    ataques = _dados(eventos, "ataque")
    assert [a.ator for a in ataques] == ["i1"] and alvo.hp < 40
    assert all(i.distancia == "longe" for i in c.inimigos) and c.inimigos[0].reacao_usada is True


def test_cada_inimigo_so_reage_uma_vez_por_rodada_e_recupera_na_propria_vez():
    c = _luta("Orc", perto=True)
    alvo = _alvo()
    turnos.recuar(c, alvo, RngFixo([2]))
    c.inimigos[0].distancia = "perto"
    assert _dados(turnos.recuar(c, alvo, RngFixo([])), "ataque") == []  # já reagiu
    turnos.vez_inimigo(c, c.inimigos[0], alvo, RngFixo([2, 2]))  # volta a avançar e erra
    assert c.inimigos[0].reacao_usada is False


def test_recuar_sem_oportunidade_nao_leva_golpe():
    c = _luta("Orc", perto=True)
    alvo = _alvo()
    turnos.recuar(c, alvo, RngFixo([]), sem_oportunidade=True)
    assert alvo.hp == 40 and c.inimigos[0].distancia == "longe"


def test_alcance_da_arma_sai_das_propriedades():
    assert turnos.alcance_da_arma(["Munição (alcance 45/180)", "Duas Mãos"]) == "distancia"
    assert turnos.alcance_da_arma(["Arremesso (alcance 6/18)", "Leve"]) == "ambos"
    assert turnos.alcance_da_arma(["Versátil (1d10)"]) == "corpo"


# -- táticas ---------------------------------------------------------------

def test_bruto_ataca_toda_vez_e_alterna_o_golpe_pesado_avisando_antes():
    c = _luta("Orc", perto=True)
    orc, alvo = c.inimigos[0], _alvo(hp=200)
    comum = turnos.vez_inimigo(c, orc, alvo, RngFixo([15, 4]))
    assert len(_dados(comum, "ataque")) == 1 and orc.intencao == "golpe pesado"  # o aviso
    pesado = turnos.vez_inimigo(c, orc, alvo, RngFixo([15, 4]))
    assert _dados(pesado, "ataque")[0].dano == _dados(comum, "ataque")[0].dano + turnos.BONUS_GOLPE_PESADO
    assert orc.intencao == "atacar"


def test_covarde_foge_abaixo_do_limiar_e_chefe_nunca():
    c = _luta("Goblin", perto=True)
    goblin = c.inimigos[0]
    goblin.hp = 1
    eventos = turnos.vez_inimigo(c, goblin, _alvo(), RngFixo([]))
    assert goblin.afastado is True and "foge" in str(eventos[0])
    c = _luta("Dragão Jovem", perto=True)
    dragao = c.inimigos[0]
    dragao.hp, dragao.foge_abaixo = 1, 0.9  # mesmo com a ficha mandando fugir
    turnos.vez_inimigo(c, dragao, _alvo(), RngFixo([2]))
    assert dragao.afastado is False


def test_matilha_so_tem_vantagem_acompanhada():
    c = _luta("Lobo", "Lobo", perto=True)
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([3, 4]))  # erra com os dois
    assert _dados(eventos, "ataque")[0].vantagem is True
    c.inimigos[1].hp = 0
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([3]))
    assert _dados(eventos, "ataque")[0].vantagem is None


def test_regenera_cura_e_ainda_ataca():
    c = _luta("Troll", perto=True)
    troll = c.inimigos[0]
    troll.hp -= 10
    eventos = turnos.vez_inimigo(c, troll, _alvo(), RngFixo([2]))
    assert troll.hp == troll.max_hp - 10 + turnos.REGENERACAO
    assert len(_dados(eventos, "ataque")) == 1


def test_atordoado_perde_exatamente_uma_vez():
    c = _luta("Orc", perto=True)
    orc, alvo = c.inimigos[0], _alvo()
    orc.efeitos = {"atordoado": 1}
    assert _dados(turnos.vez_inimigo(c, orc, alvo, RngFixo([])), "ataque") == []
    assert "atordoado" not in orc.efeitos
    assert len(_dados(turnos.vez_inimigo(c, orc, alvo, RngFixo([2])), "ataque")) == 1


def test_inimigo_queimando_pode_morrer_antes_de_agir():
    c = _luta("Kobold", perto=True)
    kobold = c.inimigos[0]
    kobold.hp, kobold.efeitos = 2, {"queimando": 2}
    eventos = turnos.vez_inimigo(c, kobold, _alvo(), RngFixo([]))
    assert kobold.hp == 0
    assert any(isinstance(e, EventoRolagem) and isinstance(e.dados, EventoStatus) for e in eventos)


# -- resistências e condições ---------------------------------------------------

def test_veneno_da_aranha_entra_quando_o_heroi_falha_na_resistencia():
    c = _luta("Aranha Gigante", perto=True)
    rng = RngFixo([15, 3, 3, 2])  # acerta, dano (2 dados), resistência 2
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), rng)
    resistencia = _dados(eventos, "resistencia")[0]
    assert resistencia.sucesso is False and resistencia.atributo == "constituicao" and resistencia.ator == "i1"
    assert c.efeitos_heroi["envenenado"] == 3
    status = [e.dados for e in eventos if isinstance(e, EventoRolagem) and isinstance(e.dados, EventoStatus)]
    assert status[0].tipo == "condicao" and status[0].detalhe == "envenenado"


def test_quem_resiste_nao_fica_envenenado():
    c = _luta("Aranha Gigante", perto=True)
    turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([15, 3, 3, 19]))
    assert "envenenado" not in c.efeitos_heroi


def test_sopro_avisa_uma_vez_antes_e_depois_recarrega():
    c = _luta("Dragão Jovem", perto=True)
    dragao, alvo = c.inimigos[0], _alvo(hp=500)
    primeira = turnos.vez_inimigo(c, dragao, alvo, RngFixo([2]))  # ataque comum, erra
    assert _dados(primeira, "resistencia") == [] and dragao.intencao == "sopro"
    sopro = turnos.vez_inimigo(c, dragao, alvo, RngFixo([3, 6, 6, 6]))  # resistência 3 falha; 3d6
    res = _dados(sopro, "resistencia")[0]
    assert res.sucesso is False and res.dano == 18 and alvo.hp == 500 - 18
    assert dragao.recarga == 3
    for _ in range(2):
        assert _dados(turnos.vez_inimigo(c, dragao, alvo, RngFixo([2])), "resistencia") == []
    assert dragao.intencao == "sopro"


def test_resistir_ao_sopro_corta_o_dano_pela_metade():
    c = _luta("Dragão Jovem", perto=True)
    dragao, alvo = c.inimigos[0], _alvo(hp=500)
    dragao.recarga = 1
    turnos.vez_inimigo(c, dragao, alvo, RngFixo([20, 6, 6, 6]))
    assert alvo.hp == 500 - 9


def test_heroi_caido_no_chao_leva_ataque_com_vantagem_de_quem_esta_perto():
    c = _luta("Orc", perto=True)
    c.efeitos_heroi = {"caido": 1}
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([3, 4]))
    assert _dados(eventos, "ataque")[0].vantagem is True


def test_defesa_e_esquiva_do_heroi_valem_contra_a_fila_e_expiram_no_turno_dele():
    c = _luta("Orc", perto=True)
    c.heroi_bonus_ca, c.heroi_vantagem_inimiga, c.heroi_escondido = 2, False, False
    alvo = _alvo(ca=15)
    ataque = _dados(turnos.vez_inimigo(c, c.inimigos[0], alvo, RngFixo([10, 9])), "ataque")[0]
    assert ataque.ca == 17 and ataque.vantagem is False
    turnos.iniciar_vez_heroi(c, alvo)
    assert (c.heroi_bonus_ca, c.heroi_vantagem_inimiga, c.heroi_escondido) == (0, None, False)


def test_inicio_do_turno_do_heroi_cobra_veneno_e_devolve_as_acoes():
    c = _luta("Orc", perto=True)
    c.efeitos_heroi = {"envenenado": 2}
    c.acao_usada = c.bonus_usada = c.movimento_usado = True
    alvo = _alvo(hp=10)
    eventos = turnos.iniciar_vez_heroi(c, alvo)
    assert alvo.hp == 10 - turnos.DANO_CONDICAO and len(_dados(eventos, "dano")) == 1
    assert (c.acao_usada, c.bonus_usada, c.movimento_usado) == (False, False, False)
    turnos.encerrar_vez_heroi(c)
    assert c.efeitos_heroi == {"envenenado": 1}
    turnos.encerrar_vez_heroi(c)
    assert c.efeitos_heroi == {}


def test_heroi_atordoado_comeca_o_turno_sem_nada_para_gastar():
    c = _luta("Orc", perto=True)
    c.efeitos_heroi = {"atordoado": 1}
    turnos.iniciar_vez_heroi(c, _alvo())
    assert c.acao_usada and c.bonus_usada and c.movimento_usado


def test_heroi_caido_a_zero_nao_leva_golpe_de_misericordia():
    c = _luta("Orc", perto=True)
    alvo = _alvo(hp=0)
    assert _dados(turnos.vez_inimigo(c, c.inimigos[0], alvo, RngFixo([])), "ataque") == []


def test_escondido_o_inimigo_perde_a_vez_procurando():
    c = _luta("Orc", perto=True)
    c.heroi_escondido = True
    eventos = turnos.vez_inimigo(c, c.inimigos[0], _alvo(), RngFixo([]))
    assert "vasculha" in str(eventos[0])


def test_resistencia_de_monstro_acompanha_o_ataque_e_o_forte_soma_tres():
    orc = _inimigo("Orc")
    turnos._aplicar_ficha(orc)
    base = max(0, orc.bonus_ataque - 3)
    assert turnos.bonus_resistencia(orc, "vigor") == base + 3  # forte do Orc
    assert turnos.bonus_resistencia(orc, "vontade") == base
    r = turnos.resistir_inimigo(orc, "vontade", 12, RngFixo([11 - base]))
    assert r.sucesso is False


# -- aliados ---------------------------------------------------------------

def _dara() -> Aliado:
    return Aliado(nome="Dara", hp=10, max_hp=10, ca=12, bonus_ataque=2, dano_dado="1d6", nome_ataque="Ataque")


def test_aliado_age_sozinho_no_mais_ferido():
    c = _luta("Orc", "Lobo", aliados=[_dara()])
    c.inimigos[1].hp = 2
    eventos = turnos.vez_aliado(c, c.aliados[0], RngFixo([15, 4]))
    assert _dados(eventos, "ataque")[0].alvo == c.inimigos[1].nome


def test_comando_marca_o_alvo_e_da_vantagem_uma_vez():
    c = _luta("Orc", "Lobo", aliados=[_dara()])
    c.inimigos[0].hp = c.inimigos[0].max_hp = 200
    c.alvo_marcado, c.comando = "i1", True
    primeiro = _dados(turnos.vez_aliado(c, c.aliados[0], RngFixo([15, 3, 4])), "ataque")[0]
    assert primeiro.alvo == c.inimigos[0].nome and primeiro.vantagem is True
    segundo = _dados(turnos.vez_aliado(c, c.aliados[0], RngFixo([15, 4])), "ataque")[0]
    assert segundo.alvo == c.inimigos[0].nome and segundo.vantagem is None  # segue no alvo, sem a vantagem


def test_fila_resolve_aliado_e_inimigos_ate_a_vez_do_heroi():
    # Orc 20, Dara 15, herói 1 → fila: Orc, Dara, herói
    c = _luta("Orc", iniciativas=[20, 15, 1], aliados=[_dara()])
    assert c.fila == ["i1", "a1", HEROI]
    eventos = turnos.avancar_fila(c, _alvo(), random.Random(3))
    atores = [d.quem for d in _dados(eventos, "ataque")]
    assert atores == [c.inimigos[0].nome, "Dara"] and turnos.da_vez(c) == HEROI


# -- saves antigos e dados --------------------------------------------------

def test_migrar_luta_antiga_engaja_todos_e_da_a_vez_ao_heroi():
    c = CombatState(ativo=True, inimigos=[_inimigo("Orc"), _inimigo("Lobo")], ordem_iniciativa=[1, -1, 0],
                    aliados=[_dara()])
    assert turnos.migrar_combate(c) is True
    assert c.versao == 2 and c.fila == [HEROI, "a1", "i2", "i1"] and turnos.da_vez(c) == HEROI
    assert all(i.distancia == "perto" and i.id for i in c.inimigos)
    assert c.inimigos[0].tatica == "bruto"  # a ficha tática veio do bestiário
    assert turnos.migrar_combate(c) is False


def test_migrar_nao_mexe_em_quem_nao_esta_lutando():
    assert turnos.migrar_combate(CombatState()) is False


def test_save_antigo_sem_os_campos_novos_ainda_carrega():
    antigo = {"ativo": True, "inimigos": [{"nome": "Orc", "hp": 15, "max_hp": 15, "ca": 13}]}
    c = CombatState.model_validate(antigo)
    assert c.versao == 1 and c.inimigos[0].id == "" and c.inimigos[0].distancia == "perto"


@pytest.mark.parametrize("nome", [n for grupo in regras.monsters.values() for n in grupo])
def test_todo_monstro_tem_ficha_tatica_valida(nome):
    c = _luta(nome)
    inimigo, ficha = c.inimigos[0], regras.get_monster(nome)
    assert {"alcance", "tatica", "foge_abaixo", "fortes"} <= set(ficha)
    assert set(inimigo.fortes) <= set(turnos.ATRIBUTO_RESISTENCIA)
    hab = inimigo.habilidade
    if hab:
        assert hab["gatilho"] in ("no_acerto", "acao") and hab["resistencia"] in turnos.ATRIBUTO_RESISTENCIA
        assert 8 <= hab["cd"] <= 18
        assert hab.get("condicao", "envenenado") in turnos.NOME_CONDICAO
        assert (hab["gatilho"] == "acao") == ("recarga" in hab)
    if nome in regras.get_monstros_chefe():
        assert inimigo.foge_abaixo == 0  # chefe não tem limiar de fuga na ficha


def test_evento_de_rolagem_carrega_os_ids_para_a_tela():
    d = DadosRolagem(tipo="ataque", quem="Orc", ator="i1", alvo_id=HEROI).to_dict()
    assert d["ator"] == "i1" and d["alvo_id"] == HEROI
