"""Testa app/services/narrator.py:montar_contexto — em especial a Etapa 5:
as seções de memória (longo prazo, resumo rolante, reputação) só aparecem
no prompt quando há algo para mostrar, e a bíblia inteira não é mais
despejada incondicionalmente (isso agora é `regras_relevantes`, já filtrado
por quem chama)."""

import json

import httpx
import openai
import pytest

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

    def test_prompt_nao_carrega_mais_o_combate_ativo(self):
        # Combate por turnos (ADR-0040/0041): em luta o chat fica fechado e
        # quem resolve é `/game/action`. O prompt do narrador só fala de
        # combate para dizer como abrir um (`iniciar_combate`).
        c_state, w_state, q_state = _contexto_base()
        c_state.efeitos_heroi = {"furia": 2}
        prompt = montar_contexto(_heroi(), w_state, c_state, q_state)
        for trecho in ("[COMBATE ATIVO]", "[ESTADO DO HERÓI]", "[TÉCNICAS DA CLASSE]", "[CENÁRIO INTERATIVO]"):
            assert trecho not in prompt
        assert "iniciar_combate" in prompt and "[DESAFIO SUGERIDO]" in prompt

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


class _ClienteQueFalha:
    """Simula um provedor recusando o pedido (400) — mesmo formato de erro
    usado por tests/test_llm_client.py para testar a cadeia de fallback."""

    def __init__(self) -> None:
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **_kwargs):
        req = httpx.Request("POST", "https://example.com/x")
        resp = httpx.Response(400, request=req)
        raise openai.APIStatusError("recusado", response=resp, body=None)


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
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})
        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)
        assert roteiro["local_inicial"] == local_novo
        assert roteiro["mundo_inicial"]["cenas"][local_novo]

    def test_cena_com_outro_nome_assume_o_do_local_inicial(self, monkeypatch):
        # Quinto achado ao vivo (05/10/2026, Gemini 2.5 Flash): a cena
        # existia, mas a chave dela não era o `local_inicial`. Antes isto
        # descartava a resposta inteira ("Origem sem cena coerente").
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["local_inicial"] = "Observatório sem registro"
        corpo["intro_narrativa"] = "Texto original numa cena cujo nome não batia com o local."
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Texto original numa cena cujo nome não batia com o local."
        assert roteiro["local_inicial"] == "Observatório sem registro"
        mundo = roteiro["mundo_inicial"]
        assert list(mundo["cenas"]) == ["Observatório sem registro"]
        assert {p["local"] for p in mundo["pessoas"].values()} == {"Observatório sem registro"}
        assert {c["local"] for c in mundo["conflitos"].values()} == {"Observatório sem registro"}

    def test_chave_sem_aspas_no_json_e_lida_mesmo_assim(self, monkeypatch):
        # Achado ao vivo (05/10/2026): o "modo JSON" do Gemini devolveu
        # 3.500 caracteres perfeitos exceto por `name_missao: "..."` — chave
        # sem aspas e com o nome errado. Custava o prólogo inteiro.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["intro_narrativa"] = "Texto original que veio num JSON quase válido."
        del corpo["nome_missao"]
        texto = json.dumps(corpo, ensure_ascii=False, indent=2)
        texto = texto.replace('  "clima_inicial"', '  name_missao: "O Rastro do Corvo",\n  "clima_inicial"', 1)
        with pytest.raises(json.JSONDecodeError):
            json.loads(texto)
        cliente = _ClienteFalso({})
        cliente._resposta = _RespostaFalsa(texto)
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: cliente})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Texto original que veio num JSON quase válido."
        # A chave errada que o modelo escreveu é aproveitada como título.
        assert roteiro["nome_missao"] == "O Rastro do Corvo"

    def test_campo_nulo_e_texto_longo_demais_nao_derrubam_o_prologo(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["intro_narrativa"] = "Texto original com um mundo que só precisava de aparo."
        pessoa = next(iter(corpo["mundo_inicial"]["pessoas"].values()))
        pessoa["medo"] = None  # o schema tem padrão "", mas recusa null
        pessoa["descricao"] = "x" * 2000  # limite do schema: 500
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Texto original com um mundo que só precisava de aparo."
        salva = roteiro["mundo_inicial"]["pessoas"][pessoa["id"]]
        assert salva["medo"] == "" and len(salva["descricao"]) == 500

    def test_mundo_acima_do_teto_e_cortado_em_vez_de_descartado(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["intro_narrativa"] = "Texto original com gente demais na cena."
        local = corpo["local_inicial"]
        modelo_de_pessoa = next(iter(corpo["mundo_inicial"]["pessoas"].values()))
        for i in range(12):
            corpo["mundo_inicial"]["pessoas"][f"extra_{i}"] = {
                **modelo_de_pessoa, "id": f"extra_{i}", "nome": f"Figurante {i}", "local": "Lugar que não existe",
            }
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        pessoas = roteiro["mundo_inicial"]["pessoas"]
        assert roteiro["intro_narrativa"] == "Texto original com gente demais na cena."
        assert len(pessoas) == 8
        assert {p["local"] for p in pessoas.values()} == {local}
        # As duas pessoas que o modelo pôs no local inicial ficam; o corte pega os figurantes.
        assert {"interlocutora", "responsavel"} <= set(pessoas)

    def test_opcoes_invalidas_viram_opcoes_da_cena_criada_pelo_modelo(self, monkeypatch):
        # Antes caíam nas opções da origem determinística: "Examinar
        # Registro de entregas" numa cena que não tinha registro nenhum.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        local = corpo["local_inicial"]
        entidades = corpo["mundo_inicial"]["cenas"][local]["entidades"]
        entidades["registro"]["nome"] = "Mapa lacrado"
        corpo["opcoes"] = ["só uma"]
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["opcoes"][0] == "Examinar Mapa lacrado"
        assert len(roteiro["opcoes"]) == 3

    def test_resposta_irreparavel_ganha_nova_tentativa_com_o_motivo(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        bom = criar_origem(_personagem_criacao(), 9)
        bom["intro_narrativa"] = "Texto original que só veio na segunda tentativa."
        ruim = {**bom, "intro_narrativa": "<os 3 parágrafos>"}  # o modelo devolveu o molde
        respostas = [_RespostaFalsa(json.dumps(ruim)), _RespostaFalsa(json.dumps(bom))]
        pedidos: list[str] = []

        def _falso(msgs, **kwargs):
            pedidos.append(msgs[0]["content"])
            return respostas.pop(0)

        monkeypatch.setattr(llm_client, "clients", {"gemini": object()})
        monkeypatch.setattr(llm_client, "chamar_com_fallback", _falso)

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Texto original que só veio na segunda tentativa."
        assert "[CORREÇÃO]" not in pedidos[0]
        assert "[CORREÇÃO]" in pedidos[1] and "molde entre < >" in pedidos[1]

    def test_tentativas_param_quando_o_prazo_do_prologo_acaba(self, monkeypatch):
        # O jogador não pode esperar minutos: perto dos 100 s um proxy de
        # hospedagem corta a requisição, e isso é pior que o texto de reserva.
        from app.services import narrator
        from app.services.emergent_start import criar_origem
        agora = [0.0]
        monkeypatch.setattr(narrator.time, "monotonic", lambda: agora[0])
        prazos: list[float] = []

        def _lento(msgs, **kwargs):
            prazos.append(kwargs["prazo"])
            agora[0] += 50  # cada chamada consome 50 s e falha
            raise llm_client.ErroMestre("Todos os modelos configurados falharam ao responder.")

        monkeypatch.setattr(llm_client, "clients", {"gemini": object()})
        monkeypatch.setattr(llm_client, "chamar_com_fallback", _lento)
        heroi = _personagem_criacao()

        roteiro = gerar_prologo_missao(heroi, semente=5)

        assert roteiro["intro_narrativa"] == criar_origem(heroi, 5)["intro_narrativa"]
        assert prazos == [narrator._PRAZO_PROLOGO, narrator._PRAZO_PROLOGO - 50]

    def test_cenas_pessoas_conflitos_soltos_no_topo_sao_aceitos(self, monkeypatch):
        # Achado ao vivo (Groq): o modelo às vezes devolve cenas/pessoas/
        # conflitos como chaves irmãs de local_inicial em vez de aninhadas
        # em mundo_inicial. Antes disto, validar_mundo_inicial via um
        # mundo_inicial vazio e o roteiro inteiro (intro_narrativa original
        # incluída) era descartado — o jogo caía no fallback determinístico,
        # que cita o objetivo do jogador literalmente.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        mundo = corpo.pop("mundo_inicial")
        soltas = {"cenas", "pessoas", "conflitos"}
        corpo["mundo_inicial"] = {k: v for k, v in mundo.items() if k not in soltas}
        corpo.update({k: v for k, v in mundo.items() if k in soltas})
        intro_original = "Um texto original que o modelo escreveu, sem citar o objetivo literalmente."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original
        cena = roteiro["mundo_inicial"]["cenas"][roteiro["local_inicial"]]
        assert any(e["tipo"] == "saida" for e in cena["entidades"].values())

    def test_cena_sem_pessoa_ganha_uma_generica_em_vez_de_cair_no_padrao(self, monkeypatch):
        # Segundo achado ao vivo, depois do aninhamento: o modelo às vezes
        # aninha tudo certo mas esquece de colocar QUALQUER pessoa no local
        # inicial — validar_mundo_inicial recusa isso (emergent_start.py:26)
        # e, sem o reparo, o roteiro inteiro (intro original incluída) era
        # descartado pelo mesmo motivo do teste de aninhamento acima.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["mundo_inicial"]["pessoas"] = {}
        corpo["mundo_inicial"]["conflitos"] = {}  # dependiam da pessoa removida
        corpo["mundo_inicial"]["arcos"] = []
        intro_original = "Um texto original sem nenhuma pessoa na cena, mas com uma saída."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original
        pessoas = roteiro["mundo_inicial"]["pessoas"]
        assert any(p["local"] == roteiro["local_inicial"] for p in pessoas.values())

    def test_cena_sem_saida_ganha_uma_generica_em_vez_de_cair_no_padrao(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        local = corpo["local_inicial"]
        entidades = corpo["mundo_inicial"]["cenas"][local]["entidades"]
        corpo["mundo_inicial"]["cenas"][local]["entidades"] = {
            k: v for k, v in entidades.items() if v.get("tipo") != "saida"
        }
        # O conflito bloqueava a saída removida — cai fora do reparo (agente
        # e local continuam válidos, só o alvo some), sem quebrar o resto.
        intro_original = "Um texto original sem nenhuma saída na cena, mas com gente."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original
        cena = roteiro["mundo_inicial"]["cenas"][roteiro["local_inicial"]]
        assert any(e["tipo"] == "saida" for e in cena["entidades"].values())

    def test_barra_n_literal_vira_quebra_de_linha_de_verdade(self, monkeypatch):
        # Achado ao vivo (Groq): o modelo às vezes escreve "\n" como dois
        # caracteres literais dentro da string JSON, em vez de uma quebra
        # de linha de verdade — aparecia cru na tela em vez de parágrafos.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["intro_narrativa"] = "Primeiro parágrafo.\\n\\nSegundo parágrafo."
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Primeiro parágrafo.\n\nSegundo parágrafo."

    def test_disposicao_fora_do_vocabulario_e_substituida_em_vez_de_derrubar_tudo(self, monkeypatch):
        # Terceiro achado ao vivo (Groq): o modelo escreveu "cauteloso" numa
        # pessoa em vez de um dos 4 valores do vocabulário fechado
        # (reservado/cooperativo/hostil/ausente) — isso derruba a validação
        # Pydantic ANTES de validar_mundo_inicial rodar sua própria lógica
        # (é um ValueError igual, então o roteiro inteiro — prosa original
        # incluída — era descartado por um campo secundário de um NPC.)
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        alguma_pessoa = next(iter(corpo["mundo_inicial"]["pessoas"].values()))
        alguma_pessoa["disposicao"] = "cauteloso"
        intro_original = "Um texto original, só a disposição de um NPC veio fora do vocabulário."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original
        disposicoes = {p["disposicao"] for p in roteiro["mundo_inicial"]["pessoas"].values()}
        assert disposicoes <= {"reservado", "cooperativo", "hostil", "ausente"}

    def test_propriedade_de_entidade_fora_do_vocabulario_e_descartada(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        local = corpo["local_inicial"]
        alguma_entidade = next(iter(corpo["mundo_inicial"]["cenas"][local]["entidades"].values()))
        alguma_entidade["propriedades"] = ["movel", "reluzente"]  # "reluzente" não existe no vocabulário
        intro_original = "Outro texto original, só uma propriedade de entidade veio inventada."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original

    def test_primeiro_provedor_falhando_ainda_usa_o_proximo_da_cadeia(self, monkeypatch):
        # Achado ao vivo (rodada de melhorias pós-Fase-6): sem chamar_fn, o
        # prólogo usava chamar_modelo_unico (só o 1º elo de CADEIA, sem
        # fallback) — um 400/429 nesse elo único derrubava o prólogo
        # inteiro mesmo com o resto da cadeia disponível. Agora usa
        # chamar_com_fallback, o mesmo caminho resiliente do turno de jogo.
        provedores = {p for p, _m in llm_client.CADEIAS["destaque"]}
        if len(provedores) < 2:
            import pytest
            pytest.skip("cadeia configurada com um provedor só neste ambiente")
        primeiro_provedor = llm_client.CADEIAS["destaque"][0][0]
        segundo_provedor = next(p for p, _m in llm_client.CADEIAS["destaque"] if p != primeiro_provedor)
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        intro_original = "Texto original — só chegou porque o fallback tentou o próximo provedor."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(
            llm_client, "clients",
            {primeiro_provedor: _ClienteQueFalha(), segundo_provedor: _ClienteFalso(corpo)},
        )

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original

    def test_id_com_acento_vira_slug_valido_em_vez_de_derrubar_tudo(self, monkeypatch):
        # Quarto achado ao vivo (Groq): o modelo escreveu "ferreiro_anão"
        # como id de pessoa — o schema exige `^[a-z0-9_-]{1,60}$` (sem
        # acento). Igual aos casos de enum: um ValueError do Pydantic
        # descartava o roteiro inteiro por causa de um id secundário.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        pessoas = corpo["mundo_inicial"]["pessoas"]
        chave_antiga = next(iter(pessoas))
        pessoa = pessoas.pop(chave_antiga)
        pessoa["id"] = "ferreiro_anão"
        pessoas["ferreiro_anão"] = pessoa
        # Um conflito referenciando o id antigo precisa acompanhar a troca.
        for conflito in corpo["mundo_inicial"]["conflitos"].values():
            if conflito.get("agente") == chave_antiga:
                conflito["agente"] = "ferreiro_anão"
        intro_original = "Um texto original, só o id de uma pessoa veio com acento."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original
        ids = {p["id"] for p in roteiro["mundo_inicial"]["pessoas"].values()}
        assert all(id_.replace("_", "").replace("-", "").isascii() for id_ in ids)
        agentes = {c["agente"] for c in roteiro["mundo_inicial"]["conflitos"].values()}
        assert agentes <= set(roteiro["mundo_inicial"]["pessoas"])

    def test_mundo_inicial_ja_aninhado_continua_funcionando(self, monkeypatch):
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        intro_original = "Outro texto original, mundo já vem aninhado direitinho."
        corpo["intro_narrativa"] = intro_original
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == intro_original

    def test_mundo_inicial_ausente_e_sem_chave_solta_cai_no_padrao(self, monkeypatch):
        # Resposta genuinamente truncada/vazia — sem mundo_inicial e sem
        # nenhuma chave de MundoVivo solta no topo — continua caindo no
        # fallback determinístico (comportamento antigo preservado).
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        del corpo["mundo_inicial"]
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        cena = roteiro["mundo_inicial"]["cenas"][roteiro["local_inicial"]]
        assert any(e["tipo"] == "saida" for e in cena["entidades"].values())

    def test_json_quebrado_ganha_uma_segunda_chamada(self, monkeypatch):
        # Achado ao vivo (05/10/2026): o Flash Lite devolveu um JSON quebrado
        # no prólogo e acertou na chamada seguinte, com o mesmo prompt.
        from app.services.emergent_start import criar_origem
        corpo = criar_origem(_personagem_criacao(), 9)
        corpo["intro_narrativa"] = "Texto original que só chegou na segunda chamada."
        respostas = [_RespostaFalsa('{"local_inicial": "Cortado no mei'), _RespostaFalsa(json.dumps(corpo))]
        papeis: list[str] = []

        def _falso(msgs, **kwargs):
            papeis.append(kwargs["papel"])
            return respostas.pop(0)

        monkeypatch.setattr(llm_client, "clients", {"gemini": object()})
        monkeypatch.setattr(llm_client, "chamar_com_fallback", _falso)

        roteiro = gerar_prologo_missao(_personagem_criacao(), semente=5)

        assert roteiro["intro_narrativa"] == "Texto original que só chegou na segunda chamada."
        assert papeis == ["destaque", "destaque"]

    def test_prompt_parte_da_ficha_e_nao_da_cena_de_reserva(self, monkeypatch):
        # Achado de uso (05/10/2026): o "exemplo de formato" do prompt era a
        # origem determinística inteira, e o modelo copiava a cena dela em
        # vez de escrever uma abertura para a ficha do jogador.
        from app.services.emergent_start import criar_origem
        heroi = _personagem_criacao(
            background="Ferreira de um templo nas montanhas", objetivo="Achar o martelo roubado",
            historia_texto="O ladrão deixou uma luva com um corvo bordado.",
        )
        reserva = criar_origem(heroi, 5)
        pedidos: list[dict] = []

        class _ClienteEspiao(_ClienteFalso):
            def create(self, **kwargs):
                pedidos.append(kwargs)
                return super().create(**kwargs)

        provedor = llm_client.CADEIAS["destaque"][0][0]
        monkeypatch.setattr(llm_client, "clients", {provedor: _ClienteEspiao(criar_origem(heroi, 9))})

        gerar_prologo_missao(heroi, semente=5)

        prompt = pedidos[0]["messages"][0]["content"]
        for trecho in (heroi.background, heroi.objetivo, heroi.historia_texto):
            assert trecho in prompt
        assert reserva["local_inicial"] not in prompt
        assert all(p["nome"] not in prompt for p in reserva["mundo_inicial"]["pessoas"].values())

    def test_cenario_do_prompt_e_sorteado_pelo_servidor_a_partir_da_semente(self, monkeypatch):
        # A IA escolhendo entre opções repetia sempre a mesma. Quem decide o
        # tipo de lugar, o nome, o clima e a hora é o servidor; mesma semente,
        # mesmo cenário.
        from app.services import narrator
        from app.services.emergent_start import criar_origem
        heroi = _personagem_criacao()
        pedidos: list[str] = []

        def _falso(msgs, **kwargs):
            pedidos.append(msgs[0]["content"])
            return _RespostaFalsa(json.dumps(criar_origem(heroi, 9)))

        monkeypatch.setattr(llm_client, "clients", {"gemini": object()})
        monkeypatch.setattr(llm_client, "chamar_com_fallback", _falso)

        for semente in (5, 5, 6, 7, 8, 9, 10, 11):
            gerar_prologo_missao(heroi, semente=semente)

        cenario = narrator._cenario_sorteado(criar_origem(heroi, 5))
        for trecho in cenario.values():
            assert trecho in pedidos[0]
        assert pedidos[0] == pedidos[1]
        tipos = {narrator._cenario_sorteado(criar_origem(heroi, s))["tipo"] for s in range(5, 12)}
        assert len(tipos) >= 4  # sementes diferentes espalham os cenários

    def test_chefe_do_arco_e_objetivo_sao_do_servidor(self, monkeypatch):
        # O modelo não vê mais a origem determinística, então não tem de
        # onde copiar um chefe válido do catálogo — o servidor preenche.
        from app.services.emergent_start import criar_origem
        heroi = _personagem_criacao()
        corpo = criar_origem(heroi, 9)
        corpo["mundo_inicial"]["arcos"][0]["chefe"] = "Dragão Inventado"
        corpo["mundo_inicial"]["objetivos"] = []
        monkeypatch.setattr(llm_client, "clients", {llm_client.CADEIAS["destaque"][0][0]: _ClienteFalso(corpo)})

        roteiro = gerar_prologo_missao(heroi, semente=5)

        chefe_do_servidor = criar_origem(heroi, 5)["mundo_inicial"]["arcos"][0]["chefe"]
        assert [a["chefe"] for a in roteiro["mundo_inicial"]["arcos"]] == [chefe_do_servidor]
        assert roteiro["mundo_inicial"]["objetivos"] == [heroi.objetivo]

    def test_texto_de_reserva_apresenta_heroi_e_pessoas_antes_da_cena(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        heroi = _personagem_criacao(nome="Kaela", objetivo="Encontrar meu irmão Teo.")

        roteiro = gerar_prologo_missao(heroi, semente=5)

        paragrafos = roteiro["intro_narrativa"].split("\n\n")
        assert len(paragrafos) == 3
        assert paragrafos[0].startswith("Kaela,")
        assert "“Encontrar meu irmão Teo”" in paragrafos[0]
        assert roteiro["local_inicial"] in paragrafos[0]
        for pessoa in roteiro["mundo_inicial"]["pessoas"].values():
            assert f"chamam-se {pessoa['nome']}" in paragrafos[2] or f"e {pessoa['nome']}." in paragrafos[2]




def _heroi_morto() -> Personagem:
    return Personagem(
        nome="Vorag", raca="Anão", classe="Bárbaro", hp_atual=0, hp_max=15, ouro=5,
        inventario=[], background="Um exilado em busca de redenção.", objetivo="Recuperar sua honra.",
    )


class TestGerarEpitafio:
    """Fase 7 da revisão de gameplay (Etapa 12/13) — chamada isolada, uma
    vez por morte. Mesmo padrão de teste de `gerar_prologo_missao`."""

    def test_retrospectiva_e_epitafio_do_modelo_sao_mantidos(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIAS["destaque"][0]
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
        provedor_principal, _ = llm_client.CADEIAS["destaque"][0]
        monkeypatch.setattr(
            llm_client, "clients",
            {provedor_principal: _ClienteFalso({"retrospectiva": "   ", "epitafio_curto": ""})},
        )
        resultado = gerar_epitafio(_heroi_morto(), [], ResumoRolante())
        assert resultado["retrospectiva"] == "Vorag caiu, e o mundo seguiu em frente."
        assert resultado["epitafio_curto"] == "Aqui jaz Vorag."

    def test_campo_ausente_do_modelo_cai_no_padrao(self, monkeypatch):
        provedor_principal, _ = llm_client.CADEIAS["destaque"][0]
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
