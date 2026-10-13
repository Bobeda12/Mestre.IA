"""Fase 3.5: banco de arquétipos de papel. O narrador diz QUEM é o inimigo
(papel e temperamento); o servidor escolhe a ficha certa do nível."""

import random

from app.domain.state import CombatState
from app.infra.data_manager import regras
from app.services import arquetipos, combat, combate_ia
from tests.helpers import RngFixo


def _luta(nomes, nivel, perfis=None, rng=None):
    estado, _, _ = combat.iniciar_combate(nomes, {"destreza": 10}, 15, rng or random.Random(1), nivel_heroi=nivel, perfis=perfis)
    return estado


def test_todo_nivel_de_1_a_10_tem_arquetipo_de_papel():
    for nivel in range(1, 11):
        assert arquetipos.arquetipos_do_nivel(nivel), nivel


def test_fichas_de_papel_tem_persona_e_nao_entram_no_sorteio_comum():
    por_papel = [(n, f) for g in regras.monsters.values() for n, f in g.items() if f.get("por_papel")]
    assert len(por_papel) >= 15
    for nome, ficha in por_papel:
        assert ficha["papel"] and ficha["temperamento"] and 20 <= len(ficha["persona"]) <= 200, nome
        assert nome not in [n for b in regras.monsters for n in regras.get_monstros_por_banda(b)]


def test_sinonimos_do_narrador_viram_o_termo_da_ficha():
    assert arquetipos.papel_de("Rei") == "nobre" and arquetipos.papel_de("a sacerdotisa") == "clerigo"
    assert arquetipos.temperamento_de("covarde") == "medroso" and arquetipos.temperamento_de("cruel") == "sadico"
    assert arquetipos.papel_de("dragão") == ""


def test_rei_medroso_de_nivel_4_vira_a_ficha_certa_com_o_nome_da_historia():
    estado = _luta(["Rei Ruan"], 4, {"rei ruan": {"nome": "Rei Ruan", "papel": "rei", "temperamento": "medroso"}})
    ruan = estado.inimigos[0]
    assert ruan.nome == "Rei Ruan" and ruan.arquetipo == "Rei Medroso"
    assert ruan.tatica == "covarde" or regras.get_monster("Rei Medroso")["tatica"] == "covarde"
    assert "tremor" in ruan.persona and ruan.temperamento == "medroso" and ruan.sprite


def test_papel_pesa_mais_que_temperamento_e_o_nivel_limita_a_escolha():
    # Nível 1 não tem nobre nem comandante: o temperamento "orgulhoso" acha o Valentão.
    assert arquetipos.escolher("rei", "orgulhoso", 1) == "Valentão de Taverna"
    # Nível 4: o papel (nobre) ganha do temperamento (astuto).
    assert arquetipos.escolher("rei", "astuto", 4) == "Rei Medroso"


def test_sem_afinidade_cai_no_sorteio_de_sempre():
    estado = _luta(["Vharn"], 3, {"vharn": {"nome": "Vharn", "papel": "dragão", "temperamento": "?"}})
    assert estado.inimigos[0].nome == "Vharn" and not estado.inimigos[0].persona
    sem_perfil = _luta(["Vharn"], 3)
    assert sem_perfil.inimigos[0].nome == "Vharn"


def test_escolha_e_deterministica_com_a_mesma_semente():
    a = arquetipos.escolher("guarda", "", 2, random.Random(7))
    b = arquetipos.escolher("guarda", "", 2, random.Random(7))
    assert a == b == "Guarda Corrupto"


def test_nome_exato_de_arquetipo_de_papel_no_nivel_certo_entra_direto():
    estado = _luta(["Mago Renegado"], 4)
    assert estado.inimigos[0].nome == "Mago Renegado" and estado.inimigos[0].papel == "mago"


def test_persona_chega_ao_prompt_de_narracao_e_o_temperamento_ao_do_juiz():
    estado = _luta(["Rei Ruan"], 4, {"rei ruan": {"nome": "Rei Ruan", "papel": "rei", "temperamento": "medroso"}})
    from tests.test_turno_heroi import _heroi  # noqa: PLC0415

    heroi = _heroi()
    assert "tremor" in combate_ia.prompt_narracao(heroi, estado, "Castelo", ["Você ataca."])
    assert "medroso" in combate_ia.prompt_improviso("assusto o rei", heroi, estado, "")


def test_papel_de_pessoa_sem_ficha_no_nivel_vira_outra_pessoa_e_nao_criatura():
    # Achado do teste ao vivo: "guarda" no nível 1 virava Esqueleto.
    escolhido = arquetipos.escolher("guarda", "desconfiado", 1, random.Random(2))
    assert escolhido in arquetipos.arquetipos_do_nivel(1)
    assert regras.get_monster(escolhido).get("por_papel") is True
    # Papel que não é de pessoa continua caindo no sorteio de criaturas.
    assert arquetipos.escolher("dragão", "feroz", 1, random.Random(2)) is None
