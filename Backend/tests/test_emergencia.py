"""Ciclo real de ferramentas: intenção → fato → iniciativa → intervenção → aprendizado."""

import json

import pytest

from app.domain.living_world import CenaPersistente, EntidadeCena, PessoaMundo
from app.domain.state import WorldState
from app.services.emergencia import painel_emergente
from app.services.living_world import avancar_tempo
from app.services.tools import ToolExecutor, tools_para
from tests.helpers import RngFixo
from tests.test_tools import _executor


@pytest.fixture
def executor():
    ex = _executor(rng=RngFixo([20]))
    ex.heroi.dificuldade = "Normal"
    ex.w_state.mundo.cenas[ex.w_state.local] = CenaPersistente(entidades={
        "sino": EntidadeCena(id="sino", nome="Sino rachado"),
    })
    ex.w_state.mundo.pessoas["zelador"] = PessoaMundo(
        id="zelador", nome="Ivo", local=ex.w_state.local, objetivo="Preservar o sino",
        medo="Maldições", limite="Não abandona a filha", segredo="A chave está na cripta",
    )
    return ex


def chamar(executor, nome, **args):
    return executor.executar(nome, json.dumps(args, ensure_ascii=False))


def proximo(executor, dado=20):
    executor.w_state.turno += 1
    return ToolExecutor(executor.heroi, executor.c_state, executor.w_state, executor.q_state, RngFixo([dado]))


def proposta(**kwargs):
    return {
        "intencao": "Imitar o som do sino para distrair Ivo", "alvo": "zelador",
        "abordagem": "Produzir a ressonância com a lâmina", "atributo": "carisma",
        "fundamento": "Ivo reconhece o som do sino que protege", "meio": "Cimitarra",
        "sucesso": [{"tipo": "condicao", "alvo": "zelador", "texto": "Ivo procura o som no pátio"}],
        "falha": [{"tipo": "relacao", "alvo": "zelador", "texto": "Ivo percebeu a imitação", "valor": -1}],
        **kwargs,
    }


def test_intencao_persiste_e_consome_uma_acao(executor):
    resposta, valido = chamar(executor, "resolver_intencao", proposta=proposta())
    assert valido and resposta["sucesso"]
    assert resposta["acontecimento_id"] == "evento_1"
    assert executor.w_state.mundo.minutos == 10
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert salvo.mundo.condicoes["zelador"] == ["Ivo procura o som no pátio"]
    assert salvo.mundo.acontecimentos[0].descricao.startswith("Imitar")
    _, valido = chamar(executor, "resolver_intencao", proposta=proposta())
    assert not valido and len(salvo.mundo.acontecimentos) == 1


def test_falha_deixa_memoria_sem_aplicar_sucesso_e_bloqueia_repeticao(executor):
    executor.rng = RngFixo([1])
    resposta, valido = chamar(executor, "resolver_intencao", proposta=proposta())
    assert valido and not resposta["sucesso"]
    assert "zelador" not in executor.w_state.mundo.condicoes
    assert executor.w_state.mundo.pessoas["zelador"].confianca == -5
    assert executor.w_state.mundo.pessoas["zelador"].lembrancas == ["Ivo percebeu a imitação"]
    ex = proximo(executor)
    antes = ex.w_state.model_dump_json()
    _, valido = chamar(ex, "resolver_intencao", proposta=proposta())
    assert not valido and antes == ex.w_state.model_dump_json()
    _, valido = chamar(ex, "resolver_intencao", proposta=proposta(meio="sino"))
    assert valido


@pytest.mark.parametrize("mudanca", [
    {"alvo": "fantasma"}, {"meio": "Dragão portátil"}, {"atributo": "sorte"},
    {"falha": [{"tipo": "relacao", "alvo": "sino", "texto": "Amizade"}]},
    {"sucesso": [{"tipo": "dano", "alvo": "zelador", "valor": 9000}]},
    {"sucesso": [{"tipo": "remover_condicao", "alvo": "zelador", "texto": "Inexistente"}]},
    {"particularidades": ["inventada"]},
])
def test_proposta_invalida_nao_muda_estado_nem_gasta_acao(executor, mudanca):
    antes = executor.w_state.model_dump_json()
    _, valido = chamar(executor, "resolver_intencao", proposta=proposta(**mudanca))
    assert not valido and antes == executor.w_state.model_dump_json()
    assert not executor._acao_gasta and not executor.eventos


def test_particularidade_imutavel_segredo_e_descoberta(executor):
    regra = {"id": "ressonancia", "alvo": "sino", "regra": "O sino responde a sussurros", "pista": "O bronze vibra"}
    assert chamar(executor, "registrar_particularidade", particularidade=regra)[1]
    chamar(executor, "registrar_particularidade", particularidade={**regra, "regra": "Imune a tudo"})
    publico = painel_emergente(executor.w_state)
    assert "sussurros" not in json.dumps(publico)
    assert painel_emergente(executor.w_state, True)["particularidades"][0]["regra"] == regra["regra"]
    assert chamar(executor, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "revelar", "alvo": "ressonancia"}],
    ))[1]
    assert painel_emergente(executor.w_state)["particularidades"][0]["regra"] == regra["regra"]


def test_consequencia_causal_prazo_interrupcao_e_privacidade(executor):
    resposta, _ = chamar(executor, "resolver_intencao", proposta=proposta())
    plano = {
        "id": "investigar", "origem": resposta["acontecimento_id"], "agente": "zelador",
        "motivo": "Ivo ouviu uma imitação do sino", "iniciativa": "Buscar um especialista secreto",
        "sinal": "Ivo prepara uma carta", "local": executor.w_state.local, "apos_minutos": 10,
        "estado": "encerrada", "vence_em": 0,
    }
    assert chamar(executor, "desenvolver_consequencia", consequencia=plano)[1]
    c = executor.w_state.mundo.consequencias["investigar"]
    assert c.estado == "pendente" and c.vence_em == 20
    assert "especialista secreto" not in json.dumps(painel_emergente(executor.w_state))
    assert not chamar(executor, "desenvolver_consequencia", consequencia={**plano, "id": "duplicado"})[1]
    avancar_tempo(executor, 10)
    assert c.estado == "disponivel"
    assert executor.w_state.mundo.pessoas["zelador"].local == executor.w_state.local
    ex = proximo(executor)
    assert chamar(ex, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "encerrar_consequencia", "alvo": "investigar", "texto": "Ivo aceita ouvir a explicação"}],
    ))[1]
    avancar_tempo(ex, 100)
    assert c.estado == "encerrada"


def test_nao_aceita_causa_inventada(executor):
    _, valido = chamar(executor, "desenvolver_consequencia", consequencia={
        "id": "reacao", "origem": "inventado", "agente": "zelador", "motivo": "Vingança",
        "iniciativa": "Buscar ajuda", "sinal": "Uma carta", "local": executor.w_state.local,
    })
    assert not valido and not executor.w_state.mundo.consequencias


def test_aprendizado_requer_experiencia_escolha_e_tem_bonus_limitado(executor):
    primeira, _ = chamar(executor, "resolver_intencao", proposta=proposta())
    ex = proximo(executor)
    segunda, _ = chamar(ex, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "informacao", "alvo": "zelador", "texto": "Ivo reconhece harmônicos"}],
    ))
    oferta = {
        "id": "harmonia", "nome": "Voz do bronze", "descricao": "Você aprendeu a conversar com Ivo por sons",
        "origens": [primeira["acontecimento_id"], segunda["acontecimento_id"]],
        "atributo": "carisma", "alvo": "zelador", "ativo": True,
    }
    assert chamar(ex, "propor_aprendizado", aprendizado=oferta)[1]
    assert not ex.w_state.mundo.aprendizados["harmonia"].ativo
    assert chamar(ex, "escolher_aprendizado", aprendizado="harmonia")[1]
    ex = proximo(ex)
    chamar(ex, "resolver_intencao", proposta=proposta())
    # Carisma 8: -1, proficiência +2 e aprendizado +1.
    assert ex.eventos_estruturados[0]["bonus"] == 2
    assert "escolher_aprendizado" not in {t["function"]["name"] for t in tools_para(ex.c_state)}


def test_saves_anteriores_carregam_sem_migracao():
    estado = WorldState.model_validate({"local": "Vila", "mundo": {}})
    assert not estado.mundo.acontecimentos and not estado.mundo.aprendizados


def test_reacao_inimiga_ocorre_uma_vez(executor, monkeypatch):
    executor.c_state.ativo = True
    chamadas = []
    monkeypatch.setattr(executor, "_resolver_reacao_inimiga", lambda: chamadas.append(True) or {})
    assert chamar(executor, "resolver_intencao", proposta=proposta())[1]
    assert not chamar(executor, "resolver_intencao", proposta=proposta())[1]
    assert chamadas == [True] and executor.w_state.mundo.minutos == 1


def test_inimigo_real_pode_ser_alvo_de_intencao(executor, monkeypatch):
    from app.domain.state import Inimigo

    executor.c_state.ativo = True
    executor.c_state.inimigos = [Inimigo(nome="Sentinela", hp=10, max_hp=10, ca=12)]
    monkeypatch.setattr(executor, "_resolver_reacao_inimiga", lambda: {})
    resposta, valido = chamar(executor, "resolver_intencao", proposta=proposta(
        alvo="Sentinela", sucesso=[{"tipo": "condicao", "alvo": "Sentinela", "texto": "Coberto de fuligem"}],
    ))
    assert valido and resposta["sucesso"]


def test_replanejamento_exige_nova_causa_e_preserva_historico(executor):
    resposta, _ = chamar(executor, "resolver_intencao", proposta=proposta())
    plano = {
        "id": "carta", "origem": resposta["acontecimento_id"], "agente": "zelador",
        "motivo": "Ivo ouviu um som estranho", "iniciativa": "Pedir ajuda por carta",
        "sinal": "Ivo busca papel", "local": executor.w_state.local,
    }
    assert chamar(executor, "desenvolver_consequencia", consequencia=plano)[1]
    assert not chamar(executor, "desenvolver_consequencia", consequencia={
        **plano, "id": "visita", "substitui": "carta",
    })[1]
    ex = proximo(executor)
    nova, _ = chamar(ex, "resolver_intencao", proposta=proposta())
    assert chamar(ex, "desenvolver_consequencia", consequencia={
        **plano, "id": "visita", "substitui": "carta", "origem": nova["acontecimento_id"],
        "iniciativa": "Procurar ajuda pessoalmente",
    })[1]
    assert ex.w_state.mundo.consequencias["carta"].estado == "encerrada"
    assert ex.w_state.mundo.consequencias["visita"].estado == "pendente"


def test_modelo_recebe_resultado_real_no_loop(executor):
    from app.services.agent_loop import executar_turno
    from tests.test_agent_loop import _LLMFalso, _MensagemFalsa, _ToolCallFalso

    llm = _LLMFalso([
        _MensagemFalsa(tool_calls=[_ToolCallFalso(
            "livre_1", "resolver_intencao", json.dumps({"proposta": proposta()}),
        )]),
        _MensagemFalsa(content="Ivo se volta para o pátio, procurando a origem do som."),
    ])
    msgs = [{"role": "user", "content": "Imito o sino com minha lâmina para distrair Ivo"}]
    narrativa, _, chamadas = executar_turno(msgs, executor, chamar_fn=llm, tools=tools_para(executor.c_state))
    assert "pátio" in narrativa and len(chamadas) == 1
    retorno = json.loads(next(m["content"] for m in msgs if m["role"] == "tool"))
    assert retorno["sucesso"] and retorno["acontecimento_id"] == "evento_1"


def test_limite_condicoes_valida_o_ramo_inteiro(executor):
    executor.w_state.mundo.condicoes["zelador"] = [f"Condição {i}" for i in range(11)]
    antes = executor.w_state.model_dump_json()
    _, valido = chamar(executor, "resolver_intencao", proposta=proposta(sucesso=[
        {"tipo": "condicao", "alvo": "zelador", "texto": "Uma nova condição"},
        {"tipo": "condicao", "alvo": "zelador", "texto": "Outra nova condição"},
    ]))
    assert not valido and executor.w_state.model_dump_json() == antes
