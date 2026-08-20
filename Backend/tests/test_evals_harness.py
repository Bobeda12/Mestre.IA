"""Testa evals/harness.py — o caminho real de produção (montar_contexto +
agent_loop.executar_turno + ToolExecutor + guardrail), mas com um chamar_fn
falso (mesmo _LLMFalso de test_agent_loop.py) para nunca chamar a Groq de
verdade. Cobre: narrativa direta, uma ferramenta disparada, erro do
"modelo", e a semeadura de memória de longo prazo (montar_memorias)."""

import hashlib

from app.domain.state import CombatState, Inimigo, QuestLog, WorldState
from app.infra.llm_client import ErroMestre
from evals.harness import montar_memorias, rodar_cenario
from evals.schema import CenarioAvaliacao, EstadoInicialCenario, EventoMemoriaSemente
from tests.test_agent_loop import _LLMFalso, _MensagemFalsa, _ToolCallFalso

ATRIBUTOS_HEROI = {"forca": 14, "destreza": 12, "constituicao": 13, "inteligencia": 10, "sabedoria": 10, "carisma": 8}


def _embed_fn_falso(texto: str) -> list[float]:
    digest = hashlib.sha256(texto.encode("utf-8")).digest()
    return [b / 255 for b in digest[:8]]


def _cenario_combate() -> CenarioAvaliacao:
    return CenarioAvaliacao(
        id="teste_combate",
        categoria="combate",
        descricao="cenário de teste",
        estado_inicial=EstadoInicialCenario(
            heroi={
                "nome": "Kael",
                "classe": "Guerreiro",
                "hp_atual": 10,
                "hp_max": 10,
                "defesa": 15,
                "ouro": 10,
                "atributos": ATRIBUTOS_HEROI,
                "inventario": ["Cimitarra"],
                "reputacao_npcs": {},
            },
            combate=CombatState(
                ativo=True,
                inimigos=[
                    Inimigo(
                        nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
                    )
                ],
            ),
            mundo=WorldState(local="Masmorra Esquecida", clima="Frio", turno=5),
            missao=QuestLog(),
        ),
        acao_jogador="Eu ataco o goblin com minha cimitarra!",
        ferramenta_esperada="atacar",
        args_esperados={"alvo": "Goblin"},
    )


def _cenario_sem_combate() -> CenarioAvaliacao:
    return CenarioAvaliacao(
        id="teste_sem_combate",
        categoria="regra_ambigua",
        descricao="cenário de teste",
        estado_inicial=EstadoInicialCenario(
            heroi={
                "nome": "Kael",
                "classe": "Guerreiro",
                "hp_atual": 10,
                "hp_max": 10,
                "defesa": 15,
                "ouro": 10,
                "atributos": ATRIBUTOS_HEROI,
                "inventario": [],
                "reputacao_npcs": {},
            },
            combate=CombatState(),
            mundo=WorldState(local="Vila de Phandalin", clima="Ensolarado", turno=1),
            missao=QuestLog(),
        ),
        acao_jogador="Eu observo a vila com calma.",
    )


def test_rodar_cenario_sem_tool_call_devolve_narrativa_direta():
    fake = _LLMFalso([_MensagemFalsa(content="A vila está tranquila, sob um céu claro.")])
    resultado = rodar_cenario(_cenario_sem_combate(), chamar_fn=fake)

    assert resultado.erro is None
    assert resultado.narrativa == "A vila está tranquila, sob um céu claro."
    assert resultado.chamadas == []
    assert len(resultado.chamadas_llm) == 1
    assert resultado.chamadas_llm[0].latencia_s >= 0


def test_rodar_cenario_com_ferramenta_disparada():
    fake = _LLMFalso(
        [
            _MensagemFalsa(tool_calls=[_ToolCallFalso("t1", "atacar", '{"alvo": "Goblin"}')]),
            _MensagemFalsa(content="A cimitarra desce num arco certeiro."),
        ]
    )
    resultado = rodar_cenario(_cenario_combate(), chamar_fn=fake)

    assert resultado.erro is None
    assert len(resultado.chamadas) == 1
    assert resultado.chamadas[0].nome == "atacar"
    assert resultado.chamadas[0].sucesso is True
    assert len(resultado.chamadas_llm) == 2  # 1 chamada de ferramenta + 1 narrativa final


def test_rodar_cenario_guardrail_pega_arma_que_o_heroi_nao_tem():
    # inventário vazio (_cenario_sem_combate), narrativa alega posse de uma arma real do jogo.
    fake = _LLMFalso([_MensagemFalsa(content="Você empunha sua cimitarra com firmeza.")])
    resultado = rodar_cenario(_cenario_sem_combate(), chamar_fn=fake)

    assert any("cimitarra" in v.lower() for v in resultado.violacoes)


def test_rodar_cenario_erro_do_modelo_nao_derruba_a_chamada():
    def _chamar_com_erro(msgs, tools=None, tool_choice="auto"):
        raise ErroMestre("cota estourada")

    resultado = rodar_cenario(_cenario_sem_combate(), chamar_fn=_chamar_com_erro)

    assert resultado.erro == "cota estourada"
    assert resultado.narrativa == ""
    assert resultado.chamadas == []


def test_montar_memorias_sem_eventos_devolve_lista_vazia():
    assert montar_memorias(_cenario_sem_combate(), turno_atual=1) == []


def test_montar_memorias_recupera_evento_semeado():
    cenario = _cenario_sem_combate()
    cenario.estado_inicial.eventos_memoria = [
        EventoMemoriaSemente(turno=5, texto="O taverneiro Gundren reclama dos impostos da vila."),
        EventoMemoriaSemente(turno=8, texto="Um goblin ataca da sombra com uma adaga enferrujada."),
    ]
    memorias = montar_memorias(cenario, turno_atual=10, embed_fn=_embed_fn_falso)

    assert len(memorias) == 2
    assert any("Gundren" in m for m in memorias)
