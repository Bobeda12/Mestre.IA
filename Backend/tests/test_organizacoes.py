"""Grupos com causa, capacidade limitada, relógio real e intervenção do jogador."""

import pytest

from app.domain.living_world import Conhecimento, PessoaMundo
from app.domain.state import WorldState
from app.services.living_world import avancar_tempo, painel_mundo
from app.services.organizacoes import painel_organizacoes
from app.services.tools import tools_para
from tests.helpers import RngFixo
from tests.test_emergencia import chamar, proposta, proximo
from tests.test_emergencia import executor as executor
from tests.test_projetos import iniciar


def grupo(**kwargs):
    return {"id": "zeladores", "nome": "Guardiões do campanário", "proposito": "Preservar o acesso ao sino",
            "principio": "O patrimônio pertence aos moradores", "membros": ["zelador"], **kwargs}


def preparar(ex):
    assert chamar(ex, "registrar_organizacao", organizacao=grupo())[1]
    r, ok = chamar(ex, "resolver_intencao", proposta=proposta())
    assert ok
    return r["acontecimento_id"]


def plano(ex, **kwargs):
    return {"id": "isolar", "nome": "Isolar o sino", "agente": "zelador", "local": ex.w_state.local,
            "objetivo": "Evitar novas imitações", "sinal": "Ivo prepara uma barreira ao redor do sino",
            "consequencia": "O acesso ao sino está bloqueado", "efeito": "bloquear", "alvo": "sino",
            "intervalo": 30, "etapas": 2, **kwargs}


def mobilizar(ex, origem, **kwargs):
    return chamar(ex, "mobilizar_organizacao", organizacao="zeladores", origem=origem, iniciativa=plano(ex, **kwargs))


def test_grupo_preserva_identidade_e_nao_admite_heroi(executor):
    assert not chamar(executor, "registrar_organizacao", organizacao=grupo(membros=["heroi"]))[1]
    assert chamar(executor, "registrar_organizacao", organizacao=grupo(local="Outro lugar"))[1]
    chamar(executor, "registrar_organizacao", organizacao=grupo(proposito="Dominar todos"))
    assert executor.w_state.mundo.organizacoes["zeladores"].proposito == grupo()["proposito"]
    assert executor.w_state.mundo.organizacoes["zeladores"].local == executor.w_state.local


def test_relogio_age_fora_da_cena_e_retorno_preserva_mudanca(executor):
    origem = preparar(executor)
    assert mobilizar(executor, origem)[1]
    local = executor.w_state.local
    executor.w_state.local = "Outro lugar"
    executor.eventos.clear()
    avancar_tempo(executor, 59)
    assert executor.w_state.mundo.cenas[local].entidades["sino"].estado == "intacto"
    avancar_tempo(executor, 1)
    assert executor.w_state.mundo.cenas[local].entidades["sino"].estado == "bloqueado"
    assert not executor.eventos
    assert painel_organizacoes(executor.w_state)[0]["iniciativas"] == []
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    salvo.local = local
    assert painel_mundo(salvo, executor.heroi.classe)["organizacoes"][0]["iniciativas"][0]["estado"] == "concretizado"
    executor.w_state.local = local
    avancar_tempo(executor, 480)
    assert executor.w_state.mundo.conflitos["isolar"].progresso == 2


def test_jogador_pode_atrasar_e_negociar_antes_do_desfecho(executor):
    origem = preparar(executor)
    mobilizar(executor, origem)
    executor = proximo(executor)
    prazo = executor.w_state.mundo.conflitos["isolar"].proximo_avanco
    assert chamar(executor, "intervir_conflito", conflito="isolar", abordagem="atrasar",
                  proposta="Ofereço uma explicação antes da obra")[1]
    assert executor.w_state.mundo.conflitos["isolar"].proximo_avanco == prazo + 30
    executor.w_state.mundo.pessoas["zelador"].disposicao = "cooperativo"
    for _ in range(2):
        executor = proximo(executor)
        executor.rng = RngFixo([20, 4, 4, 4])  # teste social e dados de PV se a recompensa subir o nível
        resultado, ok = chamar(executor, "intervir_conflito", conflito="isolar", abordagem="resolver",
                              proposta="Combinamos horários seguros para usar o sino")
        assert ok, resultado
    avancar_tempo(executor, 480)
    assert executor.w_state.mundo.conflitos["isolar"].estado == "resolvido"
    assert executor.w_state.mundo.cenas[executor.w_state.local].entidades["sino"].estado == "intacto"


@pytest.mark.parametrize("motivo", ["agente_ausente", "alvo_recolhido", "alvo_destruido"])
def test_iniciativa_perde_viabilidade_sem_executar_efeito(executor, motivo):
    origem = preparar(executor)
    mobilizar(executor, origem)
    sino = executor.w_state.mundo.cenas[executor.w_state.local].entidades["sino"]
    if motivo == "agente_ausente":
        executor.w_state.mundo.pessoas["zelador"].disposicao = "ausente"
    elif motivo == "alvo_recolhido":
        sino.recolhido = True
    else:
        sino.estado = "destruido"
    avancar_tempo(executor, 60)
    assert executor.w_state.mundo.conflitos["isolar"].estado == "resolvido"
    assert sino.estado != "bloqueado"


def test_origem_real_membro_ocupado_e_limite_de_reacao(executor):
    origem = preparar(executor)
    assert not mobilizar(executor, "inventada")[1]
    assert mobilizar(executor, origem)[1]
    antes = executor.w_state.model_dump_json()
    assert not mobilizar(executor, origem, id="segunda")[1]
    assert executor.w_state.model_dump_json() == antes
    ex = proximo(executor)
    r, _ = chamar(ex, "resolver_intencao", proposta=proposta(meio="sino"))
    assert not mobilizar(ex, r["acontecimento_id"], id="outra")[1]


def test_conhecimento_distante_e_metadados_nao_burlam_validacao(executor):
    origem = preparar(executor)
    evento = executor.w_state.mundo.acontecimentos[-1]
    evento.local = "Outro reino"
    assert not mobilizar(executor, origem)[1]
    executor.w_state.mundo.pessoas["zelador"].conhecimentos.append(Conhecimento(
        texto=evento.descricao, natureza="fato", fonte="Mensageiro",
    ))
    assert mobilizar(executor, origem)[1]
    assert not chamar(executor, "registrar_conflito", conflito=plano(
        executor, id="atalho", organizacao="zeladores", origem=origem,
    ))[1]


def test_representacao_coletiva_exige_membro_e_preserva_nome(executor):
    from tests.test_acordos_projeto import oferta

    chamar(executor, "registrar_organizacao", organizacao=grupo())
    pid = iniciar(executor)
    executor.w_state.mundo.pessoas["lia"] = PessoaMundo(
        id="lia", nome="Lia", local=executor.w_state.local, objetivo="Comerciar",
    )
    assert not chamar(executor, "propor_acordo_projeto", projeto=pid,
                      proposta=oferta("lia", organizacao="zeladores"))[1]
    assert chamar(executor, "propor_acordo_projeto", projeto=pid,
                  proposta=oferta(organizacao="zeladores", nome_organizacao="Falso"))[1]
    assert executor.w_state.mundo.projetos[pid].propostas[0].nome_organizacao == grupo()["nome"]


def test_save_antigo_e_schemas_sob_demanda(executor):
    dados = executor.w_state.model_dump()
    dados["mundo"].pop("organizacoes")
    assert WorldState.model_validate(dados).mundo.organizacoes == {}
    assert "mobilizar_organizacao" not in {
        t["function"]["name"] for t in tools_para(executor.c_state, "Observo", executor.w_state)
    }
