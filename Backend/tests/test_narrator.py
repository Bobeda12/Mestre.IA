"""Testa app/services/narrator.py:montar_contexto — em especial a Etapa 5:
as seções de memória (longo prazo, resumo rolante, reputação) só aparecem
no prompt quando há algo para mostrar, e a bíblia inteira não é mais
despejada incondicionalmente (isso agora é `regras_relevantes`, já filtrado
por quem chama)."""

from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.db import Personagem
from app.services.narrator import montar_contexto


def _heroi() -> Personagem:
    return Personagem(
        nome="TesteNarrador", classe="Guerreiro", hp_atual=8, hp_max=10, ouro=5, inventario=[]
    )


def _contexto_base() -> tuple[CombatState, WorldState, QuestLog]:
    return CombatState(), WorldState(local="Vila", clima="Ensolarado"), QuestLog()


class TestMontarContexto:
    def test_sem_memoria_nenhuma_secao_extra_aparece(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[MEMÓRIAS RELEVANTES]" not in prompt
        assert "[FATOS ESTABELECIDOS]" not in prompt
        assert "[REPUTAÇÃO" not in prompt

    def test_memorias_relevantes_aparecem_no_prompt(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(
            _heroi(), w_state, c_state, q_state, memorias=["O herói ofendeu o taverneiro no turno 5."]
        )
        assert "[MEMÓRIAS RELEVANTES]" in prompt
        assert "ofendeu o taverneiro" in prompt

    def test_resumo_rolante_aparece_por_campo(self):
        c_state, w_state, q_state = _contexto_base()
        resumo = ResumoRolante(fatos_estabelecidos=["o reino está em guerra"], npcs_conhecidos=["Gundren"])
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state, resumo=resumo)
        assert "[FATOS ESTABELECIDOS]" in prompt
        assert "o reino está em guerra" in prompt
        assert "[NPCS CONHECIDOS]" in prompt
        assert "Gundren" in prompt
        assert "[PROMESSAS FEITAS]" not in prompt  # campo vazio não aparece

    def test_reputacao_aparece_com_sinal(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state, reputacoes={"Ferreiro": -20})
        assert "Ferreiro: -20" in prompt

    def test_regras_relevantes_substitui_a_biblia_inteira(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(
            _heroi(), w_state, c_state, q_state, regras_relevantes=["[SEÇÃO ÚNICA]\nconteúdo filtrado"]
        )
        assert "[SEÇÃO ÚNICA]" in prompt
        assert "conteúdo filtrado" in prompt
