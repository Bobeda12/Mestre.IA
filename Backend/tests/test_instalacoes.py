"""Conquistas físicas, inauguração, descanso e preparação finita pelo caminho real."""

import pytest

from app.domain.state import LocalDescoberto, WorldState
from app.services.instalacoes import painel_instalacoes
from app.services.living_world import avancar_tempo
from app.services.tools import tools_para
from tests.test_emergencia import chamar, proposta, proximo
from tests.test_emergencia import executor as executor
from tests.test_projetos import iniciar


def conquistar(ex, tipo="oficina"):
    pid = iniciar(ex)
    fato = "A sala do campanário está equipada e segura para uso"
    resultado, _ = chamar(ex, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "condicao", "alvo": "sino", "texto": fato}],
    ))
    chamar(ex, "registrar_avanco_projeto", projeto=pid, condicao="acesso",
           origem=resultado["acontecimento_id"], evidencia=fato)
    assert chamar(ex, "gerir_projeto", projeto=pid, operacao="concluir")[1]
    dados = {"id": "sala", "projeto": pid, "condicao": "acesso", "nome": "Sala dos ecos",
             "descricao": "A sala que você recuperou no campanário", "tipo": tipo, "atributo": "carisma"}
    assert chamar(ex, "propor_instalacao", instalacao=dados)[1]
    return dados


def inaugurar(ex):
    assert chamar(ex, "usar_instalacao", instalacao="sala", operacao="inaugurar")[1]


def test_sem_projeto_concluido_nao_cria_servico(executor):
    pid = iniciar(executor)
    assert not chamar(executor, "propor_instalacao", instalacao={
        "id": "sala", "projeto": pid, "condicao": "acesso", "nome": "Sala", "descricao": "Abrigo",
        "tipo": "abrigo", "ativa": True,
    })[1]
    assert not executor.w_state.mundo.instalacoes


def test_inauguracao_exclusiva_do_jogador_e_projeto_nao_duplica(executor):
    dados = conquistar(executor)
    assert not executor.w_state.mundo.instalacoes["sala"].ativa
    assert not chamar(executor, "propor_instalacao", instalacao={**dados, "id": "outra"})[1]
    assert "usar_instalacao" not in {t["function"]["name"] for t in tools_para(executor.c_state)}
    inaugurar(executor)
    assert not chamar(executor, "usar_instalacao", instalacao="sala", operacao="inaugurar")[1]


def test_abrigo_habilita_descanso_em_local_gerado_sem_parar_tempo(executor):
    conquistar(executor, "abrigo")
    executor.w_state.locais_descobertos[executor.w_state.local] = LocalDescoberto(descricao="Campanário")
    assert not executor._local_seguro()
    inaugurar(executor)
    executor = proximo(executor)
    executor.heroi.hp_atual = 1
    antes = executor.w_state.mundo.minutos
    assert chamar(executor, "descansar", tipo="longo")[1]
    assert executor.heroi.hp_atual == executor.heroi.hp_max
    assert executor.w_state.mundo.minutos == antes + 480
    executor = proximo(executor)
    assert not chamar(executor, "descansar", tipo="longo")[1]


@pytest.mark.parametrize("estado", ["bloqueado", "destruido"])
def test_perda_de_acesso_desativa_uso_sem_apagar_conquista(executor, estado):
    conquistar(executor, "abrigo")
    inaugurar(executor)
    executor.w_state.mundo.cenas[executor.w_state.local].entidades["sino"].estado = estado
    publico = painel_instalacoes(executor.w_state)["lugares"][0]
    assert publico["ativa"] and not publico["disponivel"]
    executor.w_state.mundo.cenas[executor.w_state.local].entidades["sino"].estado = "intacto"
    assert painel_instalacoes(executor.w_state)["lugares"][0]["disponivel"]


@pytest.mark.parametrize("dado", [1, 20])
def test_preparacao_custa_tempo_aplica_bonus_e_consumida_na_rolagem(executor, dado):
    conquistar(executor)
    inaugurar(executor)
    executor = proximo(executor)
    antes = executor.w_state.mundo.minutos
    assert chamar(executor, "usar_instalacao", instalacao="sala", operacao="preparar")[1]
    assert executor.w_state.mundo.minutos == antes + 60
    assert executor.w_state.mundo.preparacao.expira_em == antes + 1500
    executor = proximo(executor, dado)
    antes_invalida = executor.w_state.model_dump_json()
    assert not chamar(executor, "resolver_intencao", proposta=proposta(alvo="inexistente"))[1]
    assert executor.w_state.model_dump_json() == antes_invalida
    assert chamar(executor, "resolver_intencao", proposta=proposta())[1]
    assert executor.eventos_estruturados[0]["bonus"] == 2  # carisma -1 + proficiência 2 + preparação 1
    assert executor.w_state.mundo.preparacao is None


def test_preparacao_nao_acumula_expira_e_sobrevive_viagem(executor):
    conquistar(executor)
    inaugurar(executor)
    executor = proximo(executor)
    chamar(executor, "usar_instalacao", instalacao="sala", operacao="preparar")
    executor = proximo(executor)
    antes = executor.w_state.model_dump_json()
    assert not chamar(executor, "usar_instalacao", instalacao="sala", operacao="preparar")[1]
    assert executor.w_state.model_dump_json() == antes
    executor.w_state.local = "Estrada"
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert painel_instalacoes(salvo)["preparacao"]
    assert not painel_instalacoes(salvo)["lugares"][0]["disponivel"]
    avancar_tempo(executor, 1440)
    assert executor.w_state.mundo.preparacao is None


def test_preparacao_preservada_em_outro_atributo(executor):
    conquistar(executor)
    inaugurar(executor)
    executor = proximo(executor)
    chamar(executor, "usar_instalacao", instalacao="sala", operacao="preparar")
    executor = proximo(executor)
    assert chamar(executor, "resolver_intencao", proposta=proposta(atributo="forca"))[1]
    assert executor.w_state.mundo.preparacao is not None


def test_save_antigo_sem_instalacoes(executor):
    dados = executor.w_state.model_dump()
    for chave in ("instalacoes", "preparacao"):
        dados["mundo"].pop(chave)
    assert painel_instalacoes(WorldState.model_validate(dados)) == {"lugares": [], "preparacao": None}
