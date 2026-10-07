"""Fase 1 do plano texto-livre: quem o jogador mata passa a estar morto.

O bug de origem: o NPC "morria" na prosa, o servidor não sabia, e o jogador
ainda conversava com ele (e ganhava XP de trilha por isso)."""

from app.domain.living_world import PessoaMundo
from app.domain.state import CombatState
from app.services.guardrail import validar_narrativa
from app.services.living_world import detectar_agressao, pessoa_do_local, registrar_mortes
from app.services.tools import tools_para
from tests.test_living_world import agir, executor  # noqa: F401  (fixture)


def _ruan(local: str, **extra) -> PessoaMundo:
    dados = {
        "id": "ruan", "nome": "Rei Ruan", "local": local, "objetivo": "manter a coroa",
        "mercadoria": ["Poção de Cura"], "estoque": {"Poção de Cura": 3}, **extra,
    }
    return PessoaMundo(**dados)


def _nomes(ferramentas) -> set[str]:
    return {t["function"]["name"] for t in ferramentas}


def test_detecta_agressao_e_acha_a_vitima(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    agressao, vitima = detectar_agressao("eu esfaqueio o Ruan", w)
    assert agressao and vitima is not None and vitima.id == "ruan"
    assert detectar_agressao("mato ele", w) == (True, None)


def test_conversa_e_mata_confundida_nao_dispara(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    for frase in ("converso com o Ruan", "vou para a mata", "examino o material"):
        assert detectar_agressao(frase, w)[0] is False


def test_agressao_abre_ferramentas_de_combate(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    assert "iniciar_combate" in _nomes(tools_para(CombatState(), "quero matar o Ruan", w))
    assert "iniciar_combate" not in _nomes(tools_para(CombatState(), "converso com o Ruan", w))


def test_pessoa_do_local_aceita_parte_do_nome_e_ignora_mortos(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    assert pessoa_do_local(w.mundo, w.local, "Ruan").id == "ruan"
    assert pessoa_do_local(w.mundo, w.local, "ruan").id == "ruan"
    w.mundo.pessoas["ruan"].disposicao = "morto"
    assert pessoa_do_local(w.mundo, w.local, "Ruan") is None


def test_iniciar_combate_vincula_a_pessoa_e_a_vitoria_a_mata(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    resultado, valido = agir(executor, "iniciar_combate", inimigos=["Rei Ruan"])
    assert valido, resultado
    inimigo = executor.c_state.inimigos[0]
    assert inimigo.pessoa_id == "ruan"
    inimigo.hp = 0
    eventos = registrar_mortes(executor.c_state, w)
    ruan = w.mundo.pessoas["ruan"]
    assert ruan.disposicao == "morto" and ruan.mercadoria == [] and ruan.estoque == {}
    assert any("morto" in e for e in eventos)


def test_quem_recuou_continua_vivo(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local)
    agir(executor, "iniciar_combate", inimigos=["Rei Ruan"])
    executor.c_state.inimigos[0].afastado = True  # ainda com PV
    assert registrar_mortes(executor.c_state, w) == []
    assert w.mundo.pessoas["ruan"].disposicao != "morto"


def test_morto_nao_conversa_nem_vende(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local, disposicao="morto")
    resultado, valido = agir(executor, "agir_no_mundo", acao="conversar", alvo="ruan")
    assert not valido and "morto" in resultado["erro"]
    resultado, valido = agir(executor, "comerciar", npc="ruan", operacao="comprar", item="Poção de Cura")
    assert not valido


def test_guardrail_reprova_morto_falando_e_morte_sem_combate(executor):  # noqa: F811
    w = executor.w_state
    w.mundo.pessoas["ruan"] = _ruan(w.local, disposicao="morto")
    violacoes = validar_narrativa("O rei ruan responde com um sorriso.", executor.heroi, CombatState(), w)
    assert any("morto" in v for v in violacoes)
    w.mundo.pessoas["ruan"].disposicao = "reservado"
    violacoes = validar_narrativa("Seu golpe acerta e o rei ruan morre na hora.", executor.heroi, CombatState(), w)
    assert any("sem o combate" in v for v in violacoes)
