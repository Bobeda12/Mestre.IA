"""Eficiência com retenção: arquivo íntegro, recorte limitado e ferramentas sob demanda."""

import json

import pytest

from app.infra import embeddings
from app.infra.byok import ChaveUsuario
from app.infra.llm_client import ErroMestre
from app.infra.settings import settings
from app.services.agent_loop import executar_turno, executar_turno_stream
from app.services.contexto_ia import consultar_contexto, contexto_mundo, selecionar, serializar
from app.services.memory import contexto_recente
from app.services.orcamento_ia import OrcamentoTurno, resultado_compacto
from app.services.tools import ToolExecutor, tools_para
from scripts.auditar_contexto import cenario, medir
from tests.test_agent_loop import (
    _ChunkFalso,
    _DeltaFalso,
    _DeltaToolCallFalso,
    _LLMFalso,
    _MensagemFalsa,
    _StreamLLMFalso,
    _ToolCallFalso,
)


@pytest.fixture
def executor():
    h, w, c, q, _ = cenario()
    return ToolExecutor(h, c, w, q)


def test_benchmark_nao_cresce_com_resumo_inteiro():
    inicio, longo = medir()
    assert inicio["ferramentas"] == 4
    assert inicio["entrada_chars"] < 16000
    assert longo["entrada_chars"] < 18000
    assert longo["entrada_chars"] - inicio["entrada_chars"] < 3000


def test_benchmark_multi_gatilho_fica_dentro_do_orcamento(executor):
    """Achado da auditoria pré-lançamento: `test_benchmark_nao_cresce_com_resumo_inteiro`
    só media o caso baseline (4 ferramentas). Um turno realista com vários
    tópicos de uma vez (a mesma classe de ação que já derrubou produção uma
    vez, ver Diário 0026) precisa continuar cabendo no teto real da Groq
    (8000 tokens/minuto), não só no teto local (`agent_limite_entrada_estimado`)."""
    from app.services.narrator import montar_contexto

    acao = ("Quero negociar um acordo com a guilda, fundar uma organizacao e "
            "planejar meu projeto de reconstrucao, comprando uma pocao antes de ir")
    schemas = tools_para(executor.c_state, acao, executor.w_state)
    prompt = montar_contexto(executor.heroi, executor.w_state, executor.c_state, executor.q_state, acao=acao)
    entrada_chars = len(prompt) + len(serializar(schemas))
    # chars/3 é a mesma régua conservadora de `OrcamentoTurno.registrar`; o
    # teto local (settings.agent_limite_entrada_estimado) já reflete que a
    # contagem real da Groq (chars/4, medida ao vivo) fica bem abaixo disso.
    assert entrada_chars // 3 < settings.agent_limite_entrada_estimado


def test_selecao_prioriza_relevancia_sem_cortar_frase():
    frases = ["A promessa do faroleiro continua pendente.", "O dia amanheceu."]
    assert selecionar(frases, "faroleiro", 45) == frases[:1]
    assert selecionar(["Nunca entregue a chave. " * 20], "chave", 40) == []


def test_regra_e_limite_nao_sao_truncados(executor):
    npc = next(iter(executor.w_state.mundo.pessoas.values()))
    npc.limite = "Não abandona ninguém, " * 12 + "sobretudo sua filha."
    antes = executor.w_state.model_dump_json()
    contexto = contexto_mundo(executor.w_state, npc.nome)
    registro = next(r for r in contexto["registros"] if r["ref"] == f"pessoas/{npc.id}")
    assert registro["dados"]["limite"] == npc.limite
    assert len(serializar(contexto)) <= 6500
    assert executor.w_state.model_dump_json() == antes


def test_memoria_antiga_fora_do_recorte_continua_consultavel(executor):
    segredo = "A senha do faroleiro é Andorinha Azul."
    executor.heroi.historico_chat = [{"role": "assistant", "content": segredo}] + [
        {"role": "assistant", "content": "A viagem continua."} for _ in range(350)
    ]
    assert segredo not in serializar(contexto_recente(executor.heroi.historico_chat))
    resposta = consultar_contexto(executor, "memoria", "senha faroleiro")
    assert segredo in resposta["resultados"][0]["trecho"]
    assert resposta["resultados"][0]["ref"] == "historico/0"
    assert segredo in consultar_contexto(executor, "registro", "historico/0")["fragmento_json"]


def test_consulta_isolada_por_campanha(executor):
    h, w, c, q, _ = cenario()
    outro = ToolExecutor(h, c, w, q)
    executor.heroi.historico_chat = [{"role": "assistant", "content": "Senha Particularíssima"}]
    assert consultar_contexto(outro, "memoria", "Particularíssima")["resultados"] == []


def test_registro_extenso_e_reconstituivel_por_paginas(executor):
    executor.heroi.historia_texto = "Lembrança específica. " * 400
    partes = []
    pagina = 0
    while True:
        resposta = consultar_contexto(executor, "registro", "estado/heroi", pagina)
        assert len(serializar(resposta)) < 3800
        partes.append(resposta["fragmento_json"])
        if resposta["proxima_pagina"] is None:
            break
        pagina = resposta["proxima_pagina"]
    ficha = json.loads("".join(partes))
    assert ficha["dados"]["historia_texto"] == executor.heroi.historia_texto


def test_consulta_nao_gasta_tempo_acao_nem_altera_save(executor):
    antes = executor.w_state.model_dump_json()
    resultado, ok = executor.executar("consultar_contexto", serializar({"assunto": "mundo", "consulta": ""}))
    assert ok and resultado["resultados"]
    assert executor.w_state.model_dump_json() == antes
    assert not executor._acao_gasta


def test_grupos_sao_acessiveis_sem_expor_escolhas_do_jogador(executor):
    iniciais = tools_para(executor.c_state, "Observo", executor.w_state)
    assert "registrar_pessoa" not in {t["function"]["name"] for t in iniciais}
    resultado = consultar_contexto(executor, "ferramentas", "progressao")
    assert "propor_aprendizado" in resultado["habilitar_ferramentas"]
    assert "escolher_aprendizado" not in resultado["habilitar_ferramentas"]
    executor.c_state.ativo = True
    assert consultar_contexto(executor, "ferramentas", "comercio")["habilitar_ferramentas"] == ["equipar", "usar_item"]


@pytest.mark.parametrize("acao", ["Eu vou para a floresta", "Quero ir ao porto", "Vamos à cidade"])
def test_viagem_em_linguagem_natural_carrega_mover(executor, acao):
    nomes = {t["function"]["name"] for t in tools_para(executor.c_state, acao, executor.w_state)}
    assert "mover" in nomes


def test_loop_carrega_schema_e_aguarda_consulta_mesmo_com_texto(executor):
    vistas = []
    llm = _LLMFalso([
        _MensagemFalsa(content="Vou consultar.", tool_calls=[_ToolCallFalso(
            "c1", "consultar_contexto", serializar({"assunto": "ferramentas", "consulta": "criacao"}),
        )]),
        _MensagemFalsa(content="Seu medalhão vibra com os sinos.", tool_calls=[_ToolCallFalso(
            "c2", "registrar_particularidade", serializar({"particularidade": {
                "id": "medalhao", "alvo": "heroi", "regra": "O medalhão ressoa com sinos", "pista": "O metal vibra",
            }}),
        )]),
    ])

    def chamar(msgs, tools, **kwargs):
        vistas.append({t["function"]["name"] for t in tools})
        return llm(msgs, tools=tools, **kwargs)

    narrativa, _, chamadas = executar_turno([], executor, chamar_fn=chamar,
                                          tools=tools_para(executor.c_state, "Observo", executor.w_state))
    assert "medalhão" in narrativa and len(chamadas) == 2
    assert "registrar_particularidade" not in vistas[0]
    assert "registrar_particularidade" in vistas[1]
    assert "medalhao" in executor.w_state.mundo.particularidades


def test_stream_consulta_antes_de_encerrar_e_preserva_texto_final(executor):
    fake = _StreamLLMFalso([
        [_ChunkFalso(_DeltaFalso(content="Consultando. ", tool_calls=[_DeltaToolCallFalso(
            0, id="c1", name="consultar_contexto", arguments=serializar({"assunto": "mundo", "consulta": ""}),
        )]))],
        [_ChunkFalso(_DeltaFalso(content="Você reconhece o lugar."))],
    ])
    eventos = list(executar_turno_stream([], executor, chamar_fn=fake,
                                       tools=tools_para(executor.c_state, "Observo", executor.w_state)))
    assert fake.chamadas == 2 and eventos[-1].dados == "Você reconhece o lugar."
    assert all(e.tipo == "token" for e in eventos)


def test_orcamento_interrompe_antes_da_requisicao(executor, monkeypatch):
    monkeypatch.setattr(settings, "agent_limite_entrada_estimado", 1)
    llm = _LLMFalso([])
    with pytest.raises(ErroMestre, match="orçamento"):
        executar_turno([], executor, chamar_fn=llm)
    assert llm.chamadas == 0 and not executor._acao_gasta


def test_orcamento_acumula_custo_de_todas_as_chamadas(monkeypatch):
    monkeypatch.setattr(settings, "agent_limite_turno_estimado", 50)
    orcamento = OrcamentoTurno()
    msgs = [{"role": "user", "content": "a" * 60}]
    orcamento.registrar(msgs, [])
    with pytest.raises(ErroMestre):
        orcamento.registrar(msgs, [])


def test_resultado_extenso_preserva_erro_dado_e_causa():
    compacto = json.loads(resultado_compacto({
        "sucesso": False, "total": 3, "cd": 15, "acontecimento_id": "evento_12",
        "descricao": "A porta continua fechada.", "catalogo": ["a" * 300] * 80,
    }))
    assert compacto["sucesso"] is False and compacto["total"] == 3
    assert compacto["acontecimento_id"] == "evento_12"
    assert compacto["detalhes_omitidos"] == ["catalogo"]


def test_embedding_da_consulta_e_reutilizado_so_no_request(monkeypatch):
    chamadas = []
    monkeypatch.setattr(embeddings, "embed_um", lambda texto: chamadas.append(texto) or [1.0])
    chave = ChaveUsuario(None)
    assert chave.embed_consulta_fn("Observo") == chave.embed_consulta_fn("Observo")
    assert chamadas == ["Observo"]
    ChaveUsuario(None).embed_consulta_fn("Observo")
    assert chamadas == ["Observo", "Observo"]


def test_historico_limitado_sem_mudar_o_arquivo():
    historico = [{"role": "user", "content": "a" * 6000}, {"role": "assistant", "content": "Olá"}]
    assert contexto_recente(historico, limite_chars=100) == historico[-1:]
    assert len(historico[0]["content"]) == 6000
