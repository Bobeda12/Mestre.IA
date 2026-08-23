"""Testa app/services/narrator.py:montar_contexto — em especial a Etapa 5:
as seções de memória (longo prazo, resumo rolante, reputação) só aparecem
no prompt quando há algo para mostrar, e a bíblia inteira não é mais
despejada incondicionalmente (isso agora é `regras_relevantes`, já filtrado
por quem chama)."""

import json

from app.domain.character import CharacterCreationRequest
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.db import Personagem
from app.services import narrator
from app.services.narrator import gerar_prologo_missao, montar_contexto


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


_ATRIBUTOS_MINIMOS = {
    "forca": 8, "destreza": 8, "constituicao": 8, "inteligencia": 8, "sabedoria": 8, "carisma": 8,
}


def _personagem_criacao(**overrides) -> CharacterCreationRequest:
    base = dict(
        nome="TestePrologo", raca="Humano", classe="Guerreiro", alinhamento="Neutro",
        background="Andarilho", objetivo="Testar o prólogo", atributos=dict(_ATRIBUTOS_MINIMOS),
    )
    base.update(overrides)
    return CharacterCreationRequest(**base)


class _MensagemFalsa:
    def __init__(self, content: str) -> None:
        self.content = content


class _EscolhaFalsa:
    def __init__(self, content: str) -> None:
        self.message = _MensagemFalsa(content)


class _RespostaFalsa:
    def __init__(self, content: str) -> None:
        self.choices = [_EscolhaFalsa(content)]


class _ClienteFalso:
    """Só o suficiente de `client.chat.completions.create(...)` pra
    `chamar_mestre` (narrator.py) funcionar sem rede — devolve sempre o
    mesmo JSON, não importa o prompt."""

    def __init__(self, corpo: dict) -> None:
        self._resposta = _RespostaFalsa(json.dumps(corpo, ensure_ascii=False))
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **_kwargs):
        return self._resposta


class TestGerarPrologoMissaoLocalInicial:
    """Etapa 11 (B-7, resolve P-5) — o prólogo criava o herói num local que
    `mover` não reconhecia (reproduzido ao vivo: "Ruínas de Gralhoth" e
    "Ruínas de Acheron", nenhum dos dois no catálogo). O prompt pede um
    local do catálogo, mas quem garante é a checagem no servidor."""

    def test_local_invalido_do_modelo_e_substituido_pelo_padrao(self, monkeypatch):
        monkeypatch.setattr(
            narrator, "client",
            _ClienteFalso({
                "local_inicial": "Ruínas de Gralhoth",  # não existe no catálogo
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            }),
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vila de Phandalin"

    def test_local_valido_do_modelo_e_mantido(self, monkeypatch):
        monkeypatch.setattr(
            narrator, "client",
            _ClienteFalso({
                "local_inicial": "Floresta das Sombras",
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            }),
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Floresta das Sombras"

    def test_sem_client_cai_no_local_padrao_do_catalogo(self, monkeypatch):
        monkeypatch.setattr(narrator, "client", None)
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vila de Phandalin"
