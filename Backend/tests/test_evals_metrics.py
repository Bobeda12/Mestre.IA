"""Testa evals/metrics.py com ResultadoCenario sintéticos — sem harness,
sem LLM, sem rede. Cada teste isola uma métrica."""

from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.db import Personagem
from app.services.agent_loop import ChamadaFerramenta
from evals import metrics
from evals.harness import ChamadaLLMRegistrada, ResultadoCenario
from evals.schema import CenarioAvaliacao, EstadoInicialCenario


def _cenario(**overrides) -> CenarioAvaliacao:
    base = dict(
        id="cenario_teste",
        categoria="combate",
        descricao="",
        estado_inicial=EstadoInicialCenario(
            heroi={"nome": "X", "classe": "Guerreiro", "hp_atual": 10, "hp_max": 10, "defesa": 10},
            combate=CombatState(),
            mundo=WorldState(local="Teste"),
            missao=QuestLog(),
        ),
        acao_jogador="ação",
        ferramenta_esperada=None,
        args_esperados={},
    )
    base.update(overrides)
    return CenarioAvaliacao(**base)


def _resultado(**overrides) -> ResultadoCenario:
    base = dict(
        cenario=_cenario(),
        narrativa="narrativa qualquer",
        chamadas=[],
        violacoes=[],
        heroi_final=Personagem(nome="X", classe="Guerreiro", hp_atual=10, hp_max=10, defesa=10),
        chamadas_llm=[],
        erro=None,
    )
    base.update(overrides)
    return ResultadoCenario(**base)


class TestTaxaFerramentaValida:
    def test_sem_chamada_nenhuma_e_100_por_cento(self):
        assert metrics.taxa_ferramenta_valida([_resultado()]) == 1.0

    def test_metade_das_chamadas_falhando(self):
        r = _resultado(
            chamadas=[
                ChamadaFerramenta("atacar", "{}", sucesso=True),
                ChamadaFerramenta("mover", "{}", sucesso=False),
            ]
        )
        assert metrics.taxa_ferramenta_valida([r]) == 0.5


class TestToolCallAccuracy:
    def test_sem_cenario_aplicavel_devolve_none(self):
        r = _resultado(cenario=_cenario(ferramenta_esperada=None))
        assert metrics.tool_call_accuracy([r]) == (None, None)

    def test_ferramenta_e_args_certos(self):
        r = _resultado(
            cenario=_cenario(ferramenta_esperada="atacar", args_esperados={"alvo": "Goblin"}),
            chamadas=[ChamadaFerramenta("atacar", '{"alvo": "Goblin"}', sucesso=True)],
        )
        assert metrics.tool_call_accuracy([r]) == (1.0, 1.0)

    def test_ferramenta_certa_mas_args_errados(self):
        r = _resultado(
            cenario=_cenario(ferramenta_esperada="atacar", args_esperados={"alvo": "Goblin"}),
            chamadas=[ChamadaFerramenta("atacar", '{"alvo": "Esqueleto"}', sucesso=True)],
        )
        assert metrics.tool_call_accuracy([r]) == (1.0, 0.0)

    def test_nenhuma_ferramenta_chamada(self):
        r = _resultado(cenario=_cenario(ferramenta_esperada="atacar"), chamadas=[])
        assert metrics.tool_call_accuracy([r]) == (0.0, 0.0)

    def test_args_json_invalido_nao_quebra(self):
        r = _resultado(
            cenario=_cenario(ferramenta_esperada="atacar", args_esperados={"alvo": "Goblin"}),
            chamadas=[ChamadaFerramenta("atacar", "não é json", sucesso=True)],
        )
        ferramenta_certa, args_certos = metrics.tool_call_accuracy([r])
        assert ferramenta_certa == 1.0
        assert args_certos == 0.0


class TestTaxaViolacaoEstado:
    def test_sem_violacoes(self):
        assert metrics.taxa_violacao_estado([_resultado(violacoes=[])]) == 0.0

    def test_com_violacao(self):
        assert metrics.taxa_violacao_estado([_resultado(violacoes=["algo errado"])]) == 1.0


class TestTaxaErroExecucao:
    def test_sem_erro(self):
        assert metrics.taxa_erro_execucao([_resultado(erro=None)]) == 0.0

    def test_com_erro(self):
        assert metrics.taxa_erro_execucao([_resultado(erro="ErroMestre: falhou")]) == 1.0


class TestLatenciaETokens:
    def test_percentis_e_tokens(self):
        r = _resultado(
            chamadas_llm=[
                ChamadaLLMRegistrada(modelo="m", prompt_tokens=100, completion_tokens=20, latencia_s=0.5),
                ChamadaLLMRegistrada(modelo="m", prompt_tokens=200, completion_tokens=40, latencia_s=1.5),
            ]
        )
        p50, p95 = metrics.latencia_p50_p95([r])
        assert p50 in (0.5, 1.5)
        assert p95 == 1.5
        assert metrics.tokens_totais([r]) == (300, 60)

    def test_sem_chamada_llm_nenhuma(self):
        assert metrics.latencia_p50_p95([_resultado()]) == (0.0, 0.0)
        assert metrics.tokens_totais([_resultado()]) == (0, 0)


def test_agregar_produz_todos_os_campos():
    r = _resultado(
        cenario=_cenario(ferramenta_esperada="atacar", args_esperados={}),
        chamadas=[ChamadaFerramenta("atacar", "{}", sucesso=True)],
        chamadas_llm=[ChamadaLLMRegistrada(modelo="m", prompt_tokens=10, completion_tokens=5, latencia_s=0.1)],
    )
    agregadas = metrics.agregar([r])
    assert agregadas.n_cenarios == 1
    assert agregadas.taxa_ferramenta_valida == 1.0
    assert agregadas.tool_call_ferramenta_certa == 1.0
    assert agregadas.taxa_violacao_estado == 0.0
    assert agregadas.taxa_erro_execucao == 0.0
    assert agregadas.tokens_prompt_total == 10
