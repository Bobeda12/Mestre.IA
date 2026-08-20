"""Testa evals/judge.py com um chamar_fn falso — nunca chama a Groq de
verdade. Cobre o parse da resposta do juiz (sucesso, JSON quebrado, campo
fora do schema) e as métricas de lote (taxa de parse válido, média por
eixo)."""

import json

from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.db import Personagem
from app.infra.llm_client import ErroMestre
from evals import judge
from evals.harness import ResultadoCenario
from evals.schema import CenarioAvaliacao, EstadoInicialCenario


def _cenario() -> CenarioAvaliacao:
    return CenarioAvaliacao(
        id="cenario_teste",
        categoria="combate",
        descricao="descrição de teste",
        estado_inicial=EstadoInicialCenario(
            heroi={"nome": "X", "classe": "Guerreiro", "hp_atual": 10, "hp_max": 10, "defesa": 10},
            combate=CombatState(),
            mundo=WorldState(local="Teste"),
            missao=QuestLog(),
        ),
        acao_jogador="ação de teste",
    )


def _resultado(narrativa: str = "Uma narrativa qualquer com bastante detalhe sensorial.") -> ResultadoCenario:
    return ResultadoCenario(
        cenario=_cenario(),
        narrativa=narrativa,
        chamadas=[],
        violacoes=[],
        heroi_final=Personagem(nome="X", classe="Guerreiro", hp_atual=10, hp_max=10, defesa=10),
    )


class _RespostaFalsaJuiz:
    def __init__(self, conteudo: str) -> None:
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": conteudo})()})()]


def _chamar_fn_fixo(conteudo: str):
    def _chamar(modelo, msgs, tools=None, tool_choice="auto", response_format=None):
        return _RespostaFalsaJuiz(conteudo)

    return _chamar


def test_julgar_com_json_valido():
    conteudo = json.dumps(
        {
            "aderencia_regras": 5,
            "consistencia_memoria": 4,
            "qualidade_sensorial": 3,
            "sem_alucinacao_inventario": 5,
            "justificativa": "boa narrativa",
        }
    )
    nota = judge.julgar(_resultado(), chamar_fn=_chamar_fn_fixo(conteudo))
    assert nota is not None
    assert nota.aderencia_regras == 5
    assert nota.media == (5 + 4 + 3 + 5) / 4


def test_julgar_com_json_quebrado_devolve_none():
    nota = judge.julgar(_resultado(), chamar_fn=_chamar_fn_fixo("isto não é JSON"))
    assert nota is None


def test_julgar_com_nota_fora_do_range_devolve_none():
    conteudo = json.dumps(
        {
            "aderencia_regras": 9,  # fora de 1-5
            "consistencia_memoria": 4,
            "qualidade_sensorial": 3,
            "sem_alucinacao_inventario": 5,
        }
    )
    nota = judge.julgar(_resultado(), chamar_fn=_chamar_fn_fixo(conteudo))
    assert nota is None


def test_julgar_com_narrativa_vazia_nao_chama_o_juiz():
    chamadas = []

    def _chamar(modelo, msgs, tools=None, tool_choice="auto", response_format=None):
        chamadas.append(1)
        return _RespostaFalsaJuiz("{}")

    nota = judge.julgar(_resultado(narrativa=""), chamar_fn=_chamar)
    assert nota is None
    assert chamadas == []


def test_julgar_com_erro_mestre_devolve_none():
    def _chamar(modelo, msgs, tools=None, tool_choice="auto", response_format=None):
        raise ErroMestre("cota estourada")

    assert judge.julgar(_resultado(), chamar_fn=_chamar) is None


def test_julgar_lote_e_metricas_agregadas():
    conteudo_ok = json.dumps(
        {"aderencia_regras": 4, "consistencia_memoria": 4, "qualidade_sensorial": 4, "sem_alucinacao_inventario": 4}
    )
    resultados = [_resultado(), _resultado()]
    resultados[0].cenario.id = "a"
    resultados[1].cenario.id = "b"

    notas = judge.julgar_lote(resultados, chamar_fn=_chamar_fn_fixo(conteudo_ok))
    assert set(notas) == {"a", "b"}
    assert judge.taxa_parse_valido(notas) == 1.0
    assert judge.media_por_eixo(notas) == {
        "aderencia_regras": 4.0,
        "consistencia_memoria": 4.0,
        "qualidade_sensorial": 4.0,
        "sem_alucinacao_inventario": 4.0,
    }


def test_taxa_parse_valido_com_lote_vazio_e_1():
    assert judge.taxa_parse_valido({}) == 1.0


def test_media_por_eixo_sem_notas_validas_e_zero():
    assert judge.media_por_eixo({"a": None}) == dict.fromkeys(judge.EIXOS, 0.0)
