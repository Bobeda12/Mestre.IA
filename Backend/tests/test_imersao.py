"""Imersão persistente sem roteiro imposto, concessões mecânicas ou vazamento de pistas."""

import json

import pytest

from app.domain.emergencia import Acontecimento
from app.domain.state import WorldState
from app.services.contexto_ia import consultar_contexto
from app.services.emergencia import painel_emergente
from app.services.imersao import direcao_cena, painel_imersao, registrar_ritmo
from app.services.living_world import painel_mundo
from app.services.tools import tools_para
from tests.test_emergencia import chamar, proposta, proximo
from tests.test_emergencia import executor as executor


def vivido(ex):
    ex.w_state.mundo.acontecimentos.append(Acontecimento(
        id="origem", turno=0, local=ex.w_state.local, acao="ajudar", descricao="Você reparou o sino com Ivo",
    ))


def momento(**mudancas):
    return {"id": "cha", "npc": "zelador", "origem": "origem",
            "gesto": "Ivo serve chá junto ao sino reparado", "convite": "Quer ouvir uma história?", **mudancas}


def marca(**mudancas):
    return {"id": "guardiao", "origem": "origem", "tipo": "apelido", "alvo": "zelador",
            "nome": "Guardião do bronze", "significado": "Ivo passou a chamá-lo assim pelo reparo", **mudancas}


def regra():
    return {"id": "eco", "alvo": "sino", "regra": "Responde a sussurros", "pista": "O bronze vibra",
            "pistas": [{"id": "metal", "alvo": "sino", "texto": "A rachadura pulsa com sua voz"},
                       {"id": "relato", "alvo": "zelador", "texto": "Ivo recorda vozes baixas"}]}


def test_pistas_privadas_descobertas_em_qualquer_ordem_e_persistidas(executor):
    assert chamar(executor, "registrar_particularidade", particularidade=regra())[1]
    assert "vozes baixas" not in json.dumps(painel_mundo(executor.w_state, executor.heroi.classe))
    for pista in ("relato", "metal"):
        executor = proximo(executor)
        resposta, ok = chamar(executor, "resolver_intencao", proposta=proposta(
            sucesso=[{"tipo": "pista", "alvo": "eco", "texto": pista}],
        ))
        assert ok and resposta["sucesso"]
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    publico = painel_emergente(salvo)["particularidades"][0]
    assert len(publico["pistas"]) == 2 and "regra" not in publico
    assert salvo.mundo.particularidades["eco"].pistas_descobertas == ["relato", "metal"]


def test_deducao_livre_nao_exige_coletar_todas_as_pistas(executor):
    chamar(executor, "registrar_particularidade", particularidade=regra())
    assert chamar(executor, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "revelar", "alvo": "eco"}],
    ))[1]
    publico = painel_emergente(executor.w_state)["particularidades"][0]
    assert publico["regra"] == "Responde a sussurros" and publico["pistas"] == []


@pytest.mark.parametrize("pista,ausente", [("inventada", False), ("relato", True)])
def test_pista_invalida_nao_consume_acao_nem_muda_estado(executor, pista, ausente):
    chamar(executor, "registrar_particularidade", particularidade=regra())
    if ausente:
        executor.w_state.mundo.pessoas["zelador"].disposicao = "ausente"
    antes = executor.w_state.model_dump_json()
    assert not chamar(executor, "resolver_intencao", proposta=proposta(
        alvo="sino", sucesso=[{"tipo": "pista", "alvo": "eco", "texto": pista}], falha=[],
    ))[1]
    assert executor.w_state.model_dump_json() == antes and not executor._acao_gasta


def test_pistas_imutaveis_e_descoberta_nao_injetavel(executor):
    chamar(executor, "registrar_particularidade", particularidade={**regra(), "pistas_descobertas": ["metal"]})
    assert painel_emergente(executor.w_state)["particularidades"][0]["pistas"] == []
    chamar(executor, "registrar_particularidade", particularidade={**regra(), "pistas": []})
    assert len(executor.w_state.mundo.particularidades["eco"].pistas) == 2


def test_momento_nao_aceita_convite_nem_concede_confianca(executor):
    vivido(executor)
    npc = executor.w_state.mundo.pessoas["zelador"]
    heroi, confianca, minutos = dict(executor.heroi.__dict__), npc.confianca, executor.w_state.mundo.minutos
    assert chamar(executor, "registrar_momento", momento=momento())[1]
    assert npc.promessas == [] and npc.confianca == confianca
    assert executor.heroi.__dict__ == heroi and executor.w_state.mundo.minutos == minutos
    assert not executor._acao_gasta
    assert direcao_cena(executor.w_state, executor.c_state)["foco"] == "escuta"
    chamar(executor, "registrar_momento", momento=momento(gesto="Mudado"))
    assert npc.lembrancas == [momento()["gesto"]]
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert painel_imersao(salvo)["momentos"][0]["convite"] == momento()["convite"]


@pytest.mark.parametrize("caso", ["sem_origem", "distante", "ausente", "combate", "inconsciente"])
def test_momento_rejeita_contexto_incompativel(executor, caso):
    vivido(executor)
    if caso == "sem_origem":
        executor.w_state.mundo.acontecimentos.clear()
    elif caso == "distante":
        executor.w_state.mundo.acontecimentos[0].local = "Outro reino"
    elif caso == "ausente":
        executor.w_state.mundo.pessoas["zelador"].disposicao = "ausente"
    elif caso == "combate":
        executor.c_state.ativo = True
    else:
        executor.heroi.hp_atual = 0
    antes = executor.w_state.model_dump_json()
    assert not chamar(executor, "registrar_momento", momento=momento())[1]
    assert executor.w_state.model_dump_json() == antes


def test_momento_tem_intervalo_e_nao_repete_experiencia(executor):
    vivido(executor)
    assert chamar(executor, "registrar_momento", momento=momento())[1]
    assert not chamar(executor, "registrar_momento", momento=momento(id="outro"))[1]
    executor.w_state.turno += 3
    assert not chamar(executor, "registrar_momento", momento=momento(id="outro"))[1]


def test_marca_requer_origem_e_objeto_possuido_sem_conceder_bonus(executor):
    assert not chamar(executor, "registrar_marca", marca=marca())[1]
    vivido(executor)
    assert not chamar(executor, "registrar_marca", marca=marca(tipo="objeto", alvo="Relíquia inventada"))[1]
    antes = dict(executor.heroi.__dict__)
    assert chamar(executor, "registrar_marca", marca=marca(tipo="objeto", alvo="Cimitarra"))[1]
    assert executor.heroi.__dict__ == antes
    chamar(executor, "registrar_marca", marca=marca(nome="Reescrita"))
    assert painel_imersao(executor.w_state)["marcas"][0]["nome"] == "Guardião do bronze"


def test_oportunidades_validacao_atomica_e_expiracao(executor):
    sinal = {"id": "fenda", "alvo": "sino", "percepcao": "A fenda vibra", "risco": "O metal está frágil"}
    assert chamar(executor, "apresentar_oportunidades", oportunidades=[sinal])[1]
    antes = executor.w_state.model_dump_json()
    assert not chamar(executor, "apresentar_oportunidades", oportunidades=[
        sinal, {**sinal, "id": "x", "alvo": "nada"},
    ])[1]
    assert executor.w_state.model_dump_json() == antes
    executor.w_state.turno += 2
    assert painel_imersao(executor.w_state)["oportunidades"] == []
    registrar_ritmo(executor, "defender", {}, True)
    assert not executor.w_state.mundo.oportunidades


def test_apresentar_oportunidades_recusa_combate_mesmo_chamada_direto(executor):
    # Achado da auditoria pré-lançamento — segunda linha de defesa: mesmo que
    # `tools_para` já esconda a ferramenta do narrador em combate, a função
    # em si precisa recusar se for chamada de qualquer outro jeito.
    antes = executor.w_state.model_dump_json()
    executor.c_state.ativo = True
    sinal = {"id": "fenda", "alvo": "sino", "percepcao": "A fenda vibra", "risco": "O metal está frágil"}
    assert not chamar(executor, "apresentar_oportunidades", oportunidades=[sinal])[1]
    assert executor.w_state.model_dump_json() == antes


def test_ritmo_orienta_sem_modificar_relogios(executor):
    minutos = executor.w_state.mundo.minutos
    assert direcao_cena(executor.w_state, executor.c_state)["foco"] == "descoberta"
    for _ in range(2):
        registrar_ritmo(executor, "resolver_intencao", {"sucesso": False}, False)
    assert direcao_cena(executor.w_state, executor.c_state)["foco"] == "respiro"
    executor.c_state.ativo = True
    assert direcao_cena(executor.w_state, executor.c_state)["foco"] == "tensao"
    executor.c_state.ativo = False
    registrar_ritmo(executor, "descansar", {}, False)
    assert direcao_cena(executor.w_state, executor.c_state)["foco"] == "convivio"
    assert executor.w_state.mundo.minutos == minutos


def test_grupo_sob_demanda_e_compatibilidade_save_antigo(executor):
    def nomes(ts):
        return {t["function"]["name"] for t in ts}
    assert "registrar_momento" not in nomes(tools_para(executor.c_state, "Observo", executor.w_state))
    assert "registrar_momento" in nomes(tools_para(executor.c_state, "Converso com Ivo", executor.w_state))
    executor.c_state.ativo = True
    grupo = consultar_contexto(executor, "ferramentas", "imersao")
    # Corrigido pela auditoria pré-lançamento: `apresentar_oportunidades`
    # muda o save e precisa ficar fora de combate como as outras.
    assert "registrar_momento" not in json.dumps(grupo)
    assert "apresentar_oportunidades" not in json.dumps(grupo)
    salvo = executor.w_state.model_dump()
    for chave in ("ritmo", "momentos", "marcas_jornada", "oportunidades"):
        salvo["mundo"].pop(chave)
    assert painel_imersao(WorldState.model_validate(salvo)) == {"momentos": [], "marcas": [], "oportunidades": []}
