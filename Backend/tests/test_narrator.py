"""Testa app/services/narrator.py:montar_contexto — em especial a Etapa 5:
as seções de memória (longo prazo, resumo rolante, reputação) só aparecem
no prompt quando há algo para mostrar, e a bíblia inteira não é mais
despejada incondicionalmente (isso agora é `regras_relevantes`, já filtrado
por quem chama)."""

import json

from app.domain.character import CharacterCreationRequest
from app.domain.memoria import ResumoRolante
from app.domain.state import Ato, CombatState, QuestLog, WorldState
from app.infra import llm_client
from app.infra.db import Personagem
from app.services.narrator import ATOS_PADRAO, _validar_atos, gerar_epitafio, gerar_prologo_missao, montar_contexto
from app.services.tools import RELOGIO_MAXIMO, RELOGIO_URGENCIA


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

    def test_sem_atos_nenhuma_secao_de_ato_aparece(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[ATO ATUAL]" not in prompt

    def test_ato_atual_aparece_no_prompt(self):
        # Fase 4 da revisão de gameplay — só o Ato ATUAL entra, nunca o
        # esqueleto inteiro (o Ato 2 não deveria aparecer aqui).
        c_state, w_state, q_state = _contexto_base()
        q_state.atos = [
            Ato(titulo="O Chamado", objetivo="Achar o mapa"),
            Ato(titulo="A Jornada", objetivo="Atravessar a floresta"),
        ]
        q_state.ato_atual = 0
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[ATO ATUAL] O Chamado: Achar o mapa" in prompt
        assert "A Jornada" not in prompt

    def test_indice_de_ato_fora_do_intervalo_e_clampado(self):
        c_state, w_state, q_state = _contexto_base()
        q_state.atos = [Ato(titulo="Único Ato", objetivo="Terminar")]
        q_state.ato_atual = 99  # QuestLog salvo antes desta fase, ou índice nunca revisto
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[ATO ATUAL] Único Ato: Terminar" in prompt

    def test_aviso_de_avancar_ato_so_aparece_quando_ha_proximo_ato(self):
        c_state, w_state, q_state = _contexto_base()
        q_state.atos = [Ato(titulo="Único", objetivo="Terminar")]
        q_state.ato_atual = 0
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "avancar_ato" not in prompt  # já é o último Ato, nada pra avançar

    def test_sem_relogio_maximo_nenhum_evento_global_aparece(self):
        c_state, w_state, q_state = _contexto_base()
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[EVENTO GLOBAL]" not in prompt

    def test_relogio_no_maximo_injeta_evento_global(self):
        # Fase 6 (revisão de gameplay) — relógio de facção.
        c_state, w_state, q_state = _contexto_base()
        w_state.relogios[RELOGIO_URGENCIA] = RELOGIO_MAXIMO
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[EVENTO GLOBAL]" in prompt

    def test_relogio_abaixo_do_maximo_nao_injeta(self):
        c_state, w_state, q_state = _contexto_base()
        w_state.relogios[RELOGIO_URGENCIA] = RELOGIO_MAXIMO - 1
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        assert "[EVENTO GLOBAL]" not in prompt


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
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Ruínas de Gralhoth",  # não existe no catálogo
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vila de Phandalin"

    def test_local_novo_com_descricao_e_aceito(self, monkeypatch):
        # Rodada de conserto (Parte 2, item J) — "chega de goblins" também
        # pro ponto de partida: um lugar fora do catálogo é aceito QUANDO
        # vem com descrição de verdade (mesmo padrão de `mover`, Fase 5).
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Vilarejo de Corvoceu",
                "local_inicial_descricao": "Um vilarejo de pescadores encravado num penhasco.",
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vilarejo de Corvoceu"
        assert "penhasco" in roteiro["local_inicial_descricao"]

    def test_local_novo_sem_descricao_ainda_cai_no_padrao(self, monkeypatch):
        # A rede de segurança original continua valendo: um nome fora do
        # catálogo SEM descrição não vira lugar nenhum — cai no padrão.
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Vilarejo de Corvoceu",
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vila de Phandalin"
        assert roteiro["local_inicial_descricao"] is None

    def test_local_valido_do_modelo_e_mantido(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Floresta das Sombras",
                "clima_inicial": "Nublado",
                "nome_missao": "Missão",
                "objetivo_missao": "Objetivo",
                "intro_narrativa": "Texto.",
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Floresta das Sombras"

    def test_sem_client_cai_no_local_padrao_do_catalogo(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["local_inicial"] == "Vila de Phandalin"


class TestValidarAtos:
    """Fase 4 da revisão de gameplay — mesma fronteira de confiança do
    `local_inicial`: pedir com educação não garante o formato."""

    def _corpo(self, n: int) -> list[dict]:
        return [{"titulo": f"Ato {i}", "objetivo": f"Objetivo {i}"} for i in range(n)]

    def test_lista_valida_de_tres_a_cinco_e_aceita(self):
        assert _validar_atos(self._corpo(3)) == self._corpo(3)
        assert _validar_atos(self._corpo(5)) == self._corpo(5)

    def test_lista_curta_ou_longa_demais_cai_no_padrao(self):
        assert _validar_atos(self._corpo(2)) == ATOS_PADRAO
        assert _validar_atos(self._corpo(6)) == ATOS_PADRAO

    def test_nao_e_lista_cai_no_padrao(self):
        assert _validar_atos("não é uma lista") == ATOS_PADRAO
        assert _validar_atos(None) == ATOS_PADRAO

    def test_item_sem_titulo_ou_objetivo_cai_no_padrao(self):
        corpo = self._corpo(3)
        del corpo[1]["objetivo"]
        assert _validar_atos(corpo) == ATOS_PADRAO

    def test_titulo_vazio_cai_no_padrao(self):
        corpo = self._corpo(3)
        corpo[0]["titulo"] = "   "
        assert _validar_atos(corpo) == ATOS_PADRAO


class TestGerarPrologoMissaoAtos:
    def test_atos_validos_do_modelo_sao_mantidos(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        atos = [
            {"titulo": "O Chamado", "objetivo": "Achar o mapa"},
            {"titulo": "A Jornada", "objetivo": "Atravessar a floresta"},
            {"titulo": "O Confronto", "objetivo": "Derrotar o culto"},
        ]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Vila de Phandalin", "clima_inicial": "Nublado",
                "nome_missao": "Missão", "objetivo_missao": "Objetivo", "intro_narrativa": "Texto.",
                "atos": atos,
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["atos"] == atos

    def test_atos_malformados_do_modelo_caem_no_padrao(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIA[0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({
                "local_inicial": "Vila de Phandalin", "clima_inicial": "Nublado",
                "nome_missao": "Missão", "objetivo_missao": "Objetivo", "intro_narrativa": "Texto.",
                "atos": "não é uma lista",
            })},
        )
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["atos"] == ATOS_PADRAO

    def test_sem_client_cai_nos_atos_padrao(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        roteiro = gerar_prologo_missao(_personagem_criacao())
        assert roteiro["atos"] == ATOS_PADRAO


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
