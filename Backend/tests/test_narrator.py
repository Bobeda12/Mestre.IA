"""Testa app/services/narrator.py:montar_contexto — em especial a Etapa 5:
as seções de memória (longo prazo, resumo rolante, reputação) só aparecem
no prompt quando há algo para mostrar, e a bíblia inteira não é mais
despejada incondicionalmente (isso agora é `regras_relevantes`, já filtrado
por quem chama)."""

import json

from app.domain.character import CharacterCreationRequest
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra import llm_client
from app.infra.db import Personagem
from app.services.narrator import gerar_epitafio, gerar_prologo_missao, montar_contexto


def _heroi() -> Personagem:
    return Personagem(
        nome="TesteNarrador", classe="Guerreiro", hp_atual=8, hp_max=10, ouro=5, inventario=[]
    )


def _contexto_base() -> tuple[CombatState, WorldState, QuestLog]:
    return CombatState(), WorldState(local="Vila", clima="Ensolarado"), QuestLog()


class TestMontarContexto:
    def test_tracos_de_raca_e_classe_aparecem_no_prompt(self):
        # Rodada de conserto (Parte 2, item H) — antes disto, o narrador só
        # recebia o rótulo "Anão Guerreiro"; agora sabe quais traços e
        # proficiências vêm do catálogo (data/races.json/classes.json).
        heroi = Personagem(
            nome="TesteNarrador", raca="Anão", classe="Guerreiro", hp_atual=8, hp_max=10, ouro=5, inventario=[]
        )
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(heroi, w_state, c_state, q_state)
        assert "[TRAÇOS]" in prompt
        assert "Resistência a Veneno" in prompt
        assert "Todas as Armaduras" in prompt  # proficiência de Guerreiro

    def test_raca_desconhecida_nao_quebra_o_prompt(self):
        heroi = Personagem(
            nome="TesteNarrador", raca="Isso não existe", classe="Guerreiro",
            hp_atual=8, hp_max=10, ouro=5, inventario=[],
        )
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(heroi, w_state, c_state, q_state)
        assert "nenhum catalogado" in prompt

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
    "forca": 15, "destreza": 14, "constituicao": 13, "inteligencia": 12, "sabedoria": 10, "carisma": 8,
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
    def test_sem_ia_tem_local_coerente_e_saida_livre(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)
        cena = roteiro["mundo_inicial"]["cenas"][roteiro["local_inicial"]]
        assert any(e["tipo"] == "saida" for e in cena["entidades"].values())
        assert "atos" not in roteiro  # Fase 0 (ADR-0032): o prólogo não gera roteiro

    def test_modelo_pode_criar_outro_mundo_coerente(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        local_antigo = corpo["local_inicial"]
        local_novo = "Observatório de Vidro"
        corpo["local_inicial"] = local_novo
        corpo["mundo_inicial"]["cenas"][local_novo] = corpo["mundo_inicial"]["cenas"].pop(local_antigo)
        for pessoa in corpo["mundo_inicial"]["pessoas"].values():
            pessoa["local"] = local_novo
        for conflito in corpo["mundo_inicial"]["conflitos"].values():
            conflito["local"] = local_novo
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIA[0][0]: _ClienteFalso(corpo)})
        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)
        assert roteiro["local_inicial"] == local_novo
        assert roteiro["mundo_inicial"]["cenas"][local_novo]

    def test_local_sem_mundo_coerente_cai_na_origem_validada(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["local_inicial"] = "Observatório sem registro"
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIA[0][0]: _ClienteFalso(corpo)})
        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)
        assert roteiro["local_inicial"] in roteiro["mundo_inicial"]["cenas"]
        assert roteiro["local_inicial"] != "Observatório sem registro"




def _heroi_morto() -> Personagem:
    return Personagem(
        nome="Vorag", raca="Anão", classe="Bárbaro", hp_atual=0, hp_max=15, ouro=5,
        inventario=[], background="Um exilado em busca de redenção.", objetivo="Recuperar sua honra.",
    )


class TestGerarEpitafio:
    """Fase 7 da revisão de gameplay (Etapa 12/13) — chamada isolada, uma
    vez por morte. Mesmo padrão de teste de `gerar_prologo_missao`."""

    def test_retrospectiva_e_epitafio_do_modelo_sao_mantidos(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "retrospectiva": "Vorag caiu nas Criptas de Ashgrave, machado em punho até o fim.",
                "epitafio_curto": "Aqui jaz Vorag, que nunca recuou.",
            })},
        )
        resultado = gerar_epitafio(_heroi_morto(), ["O goblin emboscou Vorag."], ResumoRolante())
        assert resultado["retrospectiva"] == "Vorag caiu nas Criptas de Ashgrave, machado em punho até o fim."
        assert resultado["epitafio_curto"] == "Aqui jaz Vorag, que nunca recuou."

    def test_retrospectiva_vazia_do_modelo_cai_no_padrao(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({"retrospectiva": "   ", "epitafio_curto": ""})},
        )
        resultado = gerar_epitafio(_heroi_morto(), [], ResumoRolante())
        assert resultado["retrospectiva"] == "Vorag caiu, e o mundo seguiu em frente."
        assert resultado["epitafio_curto"] == "Aqui jaz Vorag."

    def test_campo_ausente_do_modelo_cai_no_padrao(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({"retrospectiva": "Uma retrospectiva válida."})},
        )
        resultado = gerar_epitafio(_heroi_morto(), [], ResumoRolante())
        assert resultado["retrospectiva"] == "Uma retrospectiva válida."
        assert resultado["epitafio_curto"] == "Aqui jaz Vorag."

    def test_sem_client_cai_no_epitafio_padrao(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        resultado = gerar_epitafio(_heroi_morto(), [], ResumoRolante())
        assert resultado["epitafio_curto"] == "Aqui jaz Vorag."
        assert "Vorag" in resultado["retrospectiva"]
