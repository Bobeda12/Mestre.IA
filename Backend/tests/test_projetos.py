"""Projeto livre só avança com mudanças executadas e persiste ao retornar."""

import pytest

from app.domain.state import WorldState
from app.services.tools import tools_para
from tests.test_emergencia import chamar, proposta, proximo
from tests.test_emergencia import executor as executor


def iniciar(ex):
    resposta, ok = chamar(ex, "gerir_projeto", operacao="iniciar", ambicao="Reabrir o campanário")
    assert ok
    pid = resposta["projeto"]["id"]
    assert chamar(ex, "planejar_projeto", projeto=pid, condicoes=[
        {"id": "acesso", "descricao": "O campanário pode receber visitantes", "alvo": "sino"},
    ])[1]
    return pid


@pytest.mark.parametrize("superada", [False, True])
def test_ciclo_real_com_meios_livres_conquista_e_save(executor, superada):
    pid = iniciar(executor)
    assert not chamar(executor, "gerir_projeto", operacao="concluir", projeto=pid)[1]
    fato = "O acesso ao sino está seguro para visitantes"
    resposta, ok = chamar(executor, "resolver_intencao", proposta=proposta(
        alvo="sino", sucesso=[{"tipo": "condicao", "alvo": "sino", "texto": fato}],
    ))
    assert ok and resposta["sucesso"]
    assert chamar(executor, "registrar_avanco_projeto", projeto=pid, condicao="acesso",
                  origem=resposta["acontecimento_id"], evidencia=fato, superada=superada)[1]
    assert chamar(executor, "gerir_projeto", operacao="concluir", projeto=pid)[1]
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert salvo.mundo.projetos[pid].estado == "concluido"
    assert salvo.mundo.projetos[pid].condicoes[0].evidencia == fato
    executor = proximo(executor)
    executor.w_state.local = "Outro lugar"
    assert executor.w_state.mundo.projetos[pid].estado == "concluido"


def test_projeto_pertence_ao_jogador_e_nao_pode_ser_duplicado(executor):
    assert not chamar(executor, "planejar_projeto", projeto="inventado", condicoes=[])[1]
    pid = iniciar(executor)
    assert not chamar(executor, "gerir_projeto", operacao="iniciar", ambicao="Outra ambição")[1]
    assert "gerir_projeto" not in {t["function"]["name"] for t in tools_para(executor.c_state)}
    assert chamar(executor, "gerir_projeto", operacao="abandonar", projeto=pid)[1]
    assert executor.w_state.mundo.projetos[pid].condicoes
    assert chamar(executor, "gerir_projeto", operacao="iniciar", ambicao="Outra ambição")[1]


def test_plano_preservado_e_estado_injetado_ignorado(executor):
    r, _ = chamar(executor, "gerir_projeto", operacao="iniciar", ambicao="Abrir o campanário")
    pid = r["projeto"]["id"]
    assert chamar(executor, "planejar_projeto", projeto=pid, condicoes=[
        {"id": "acesso", "alvo": "sino", "descricao": "Acesso seguro", "estado": "satisfeita",
         "evidencia": "Inventada", "origem": "inventada"},
    ])[1]
    c = executor.w_state.mundo.projetos[pid].condicoes[0]
    assert c.estado == "aberta" and not c.evidencia and not c.origem
    chamar(executor, "planejar_projeto", projeto=pid, condicoes=[])
    assert executor.w_state.mundo.projetos[pid].condicoes == [c]


@pytest.mark.parametrize("caso", ["inventado", "so_texto", "falha", "outro_alvo"])
def test_evidencia_invalida_nao_avanca(executor, caso):
    pid = iniciar(executor)
    fato = "O sino está acessível"
    tipo = "informacao" if caso == "so_texto" else "condicao"
    alvo = "zelador" if caso == "outro_alvo" else "sino"
    resposta, _ = chamar(executor, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": tipo, "alvo": alvo, "texto": fato}],
    ))
    evento = executor.w_state.mundo.acontecimentos[-1]
    if caso == "falha":
        evento.sucesso = False
    antes = executor.w_state.model_dump_json()
    assert not chamar(executor, "registrar_avanco_projeto", projeto=pid, condicao="acesso",
                      origem="inventado" if caso == "inventado" else resposta["acontecimento_id"], evidencia=fato)[1]
    assert executor.w_state.model_dump_json() == antes


def test_save_antigo_e_grupo_sob_demanda(executor):
    dados = executor.w_state.model_dump()
    dados["mundo"].pop("projetos")
    assert WorldState.model_validate(dados).mundo.projetos == {}
    nomes = {t["function"]["name"] for t in tools_para(executor.c_state, "Observo", executor.w_state)}
    assert "planejar_projeto" not in nomes


def test_ferramentas_de_projeto_recusam_combate_mesmo_chamadas_direto(executor):
    # Achado da auditoria pré-lançamento — segunda linha de defesa: mesmo que
    # `tools_para` já esconda a ferramenta do narrador em combate, a função
    # em si precisa recusar se for chamada de qualquer outro jeito.
    pid = iniciar(executor)
    antes = executor.w_state.model_dump_json()
    executor.c_state.ativo = True
    assert not chamar(executor, "planejar_projeto", projeto=pid, condicoes=[
        {"id": "outro", "descricao": "x", "alvo": "sino"},
    ])[1]
    assert not chamar(executor, "registrar_avanco_projeto", projeto=pid, condicao="acesso",
                     origem="inventado", evidencia="x")[1]
    assert not chamar(executor, "cumprir_acordo_projeto", projeto=pid, acordo="inventado",
                     origem="inventado", evidencia="x")[1]
    assert executor.w_state.model_dump_json() == antes
