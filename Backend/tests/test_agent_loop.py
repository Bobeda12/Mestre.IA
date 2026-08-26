"""Testa app/services/agent_loop.py — o controle do loop em si (quantos
passos, quando para, o que faz com ferramenta malformada), sem depender da
API da Groq de verdade nem das ferramentas reais de tools.py. Um `_FakeLLM`
substitui `chamar_com_fallback`; um `FakeExecutor` substitui `ToolExecutor`."""

from app.domain.eventos import DadosRolagem, EventoRolagem
from app.infra.llm_client import ErroMestre
from app.services import agent_loop


class _FuncaoFalsa:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCallFalso:
    def __init__(self, id: str, name: str, arguments: str, extra_content: dict | None = None) -> None:
        self.id = id
        self.function = _FuncaoFalsa(name, arguments)
        # Achado ao vivo — Gemini "thinking" (3.x) assina cada tool_call
        # com `extra_content.google.thought_signature`; o dublê só simula
        # o campo quando o teste passa `extra_content` explicitamente,
        # como o SDK de verdade (getattr sem o campo devolve None).
        if extra_content is not None:
            self.extra_content = extra_content


class _MensagemFalsa:
    def __init__(self, content: str | None = None, tool_calls: list | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _RespostaFalsa:
    def __init__(self, mensagem: _MensagemFalsa) -> None:
        self.choices = [type("Choice", (), {"message": mensagem})()]


class _LLMFalso:
    """Devolve uma resposta roteirizada por chamada, na ordem — se a fila
    acabar antes do loop, o teste tem um bug (IndexError é o sinal certo)."""

    def __init__(self, respostas: list[_MensagemFalsa]) -> None:
        self._respostas = iter(respostas)
        self.chamadas = 0

    def __call__(self, msgs, tools=None, tool_choice="auto"):
        self.chamadas += 1
        return _RespostaFalsa(next(self._respostas))


class FakeExecutor:
    def __init__(self, respostas: dict[str, tuple[dict, bool]]) -> None:
        self._respostas = respostas
        self.eventos: list[str] = []
        self.chamadas_recebidas: list[tuple[str, str]] = []

    def executar(self, nome: str, args_json: str) -> tuple[dict, bool]:
        self.chamadas_recebidas.append((nome, args_json))
        if nome not in self._respostas:
            return {"erro": f"ferramenta '{nome}' não existe"}, False
        resultado, sucesso = self._respostas[nome]
        if sucesso:
            self.eventos.append(f"evento de {nome}")
        return resultado, sucesso


def test_sem_tool_calls_devolve_o_texto_direto(monkeypatch):
    fake = _LLMFalso([_MensagemFalsa(content="Você entra na taverna.")])
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)

    narrativa, eventos, chamadas = agent_loop.executar_turno([], FakeExecutor({}))

    assert narrativa == "Você entra na taverna."
    assert eventos == []
    assert chamadas == []
    assert fake.chamadas == 1


def test_uma_chamada_de_ferramenta_depois_narrativa_final(monkeypatch):
    fake = _LLMFalso(
        [
            _MensagemFalsa(tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta"}')]),
            _MensagemFalsa(content="Vocês chegam à floresta."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})

    narrativa, eventos, chamadas = agent_loop.executar_turno([], executor)

    assert narrativa == "Vocês chegam à floresta."
    assert eventos == ["evento de mover"]
    assert len(chamadas) == 1
    assert chamadas[0].nome == "mover"
    assert chamadas[0].sucesso is True
    assert fake.chamadas == 2


def test_mensagem_de_tool_call_nunca_manda_content_none(monkeypatch):
    # BYOK (Etapa 15) — achado ao vivo: quando o modelo chama uma ferramenta
    # sem escrever texto antes (`mensagem.content is None`, o caso comum),
    # `content: null` nessa mensagem de assistente é aceito pela Groq mas
    # rejeitado com 400 pela camada de compatibilidade OpenAI do Gemini.
    # `msgs` é mutado in-place por `executar_turno` — inspecionar depois da
    # chamada é o jeito de verificar o que teria sido mandado na próxima.
    fake = _LLMFalso(
        [
            _MensagemFalsa(content=None, tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta"}')]),
            _MensagemFalsa(content="Vocês chegam à floresta."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})
    msgs: list[dict] = []

    agent_loop.executar_turno(msgs, executor)

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    assert mensagem_assistente["content"] == ""
    assert mensagem_assistente["content"] is not None


def test_thought_signature_do_gemini_e_ecoada_na_proxima_chamada(monkeypatch):
    # Achado ao vivo (rodada de conserto) — Gemini "thinking" (3.x) assina
    # cada chamada de ferramenta com `extra_content.google.thought_
    # signature`; sem replicar esse campo na mensagem de assistente
    # reconstruída, a PRÓXIMA chamada do mesmo turno é rejeitada com 400
    # ("Function call is missing a thought_signature"), mesmo a primeira
    # tendo funcionado — https://github.com/openai/openai-python/issues/2758.
    assinatura = {"google": {"thought_signature": "abc123"}}
    fake = _LLMFalso(
        [
            _MensagemFalsa(
                content=None,
                tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta"}', extra_content=assinatura)],
            ),
            _MensagemFalsa(content="Vocês chegam à floresta."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})
    msgs: list[dict] = []

    agent_loop.executar_turno(msgs, executor)

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    [tool_call] = mensagem_assistente["tool_calls"]
    assert tool_call["extra_content"] == assinatura


def test_sem_thought_signature_nenhum_campo_extra_e_adicionado(monkeypatch):
    # A Groq (e o Gemini sem "thinking") nunca manda esse campo — não pode
    # aparecer um `extra_content: None`/vazio poluindo a mensagem à toa.
    fake = _LLMFalso(
        [
            _MensagemFalsa(content=None, tool_calls=[_ToolCallFalso("t1", "mover", '{"destino": "Floresta"}')]),
            _MensagemFalsa(content="Vocês chegam à floresta."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})
    msgs: list[dict] = []

    agent_loop.executar_turno(msgs, executor)

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    [tool_call] = mensagem_assistente["tool_calls"]
    assert "extra_content" not in tool_call


def test_multiplas_chamadas_no_mesmo_passo(monkeypatch):
    fake = _LLMFalso(
        [
            _MensagemFalsa(
                tool_calls=[
                    _ToolCallFalso("t1", "rolar_teste", '{"atributo": "destreza", "cd": 10}'),
                    _ToolCallFalso("t2", "consultar_regra", '{"termo": "furtividade"}'),
                ]
            ),
            _MensagemFalsa(content="Você se esgueira pelas sombras."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor(
        {
            "rolar_teste": ({"sucesso": True}, True),
            "consultar_regra": ({"encontrado": False}, True),
        }
    )

    narrativa, eventos, chamadas = agent_loop.executar_turno([], executor)

    assert len(chamadas) == 2
    assert {c.nome for c in chamadas} == {"rolar_teste", "consultar_regra"}
    assert len(eventos) == 2


def test_argumento_malformado_nao_derruba_o_turno(monkeypatch):
    fake = _LLMFalso(
        [
            _MensagemFalsa(tool_calls=[_ToolCallFalso("t1", "ferramenta_fantasma", "{}")]),
            _MensagemFalsa(content="O mestre segue em frente mesmo assim."),
        ]
    )
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({})  # nenhuma ferramenta reconhecida

    narrativa, _eventos, chamadas = agent_loop.executar_turno([], executor)

    assert narrativa == "O mestre segue em frente mesmo assim."
    assert chamadas[0].sucesso is False
    assert fake.chamadas == 2  # não travou depois do erro


def test_limite_de_passos_estourado_devolve_narrativa_de_recuperacao(monkeypatch):
    sempre_chama_ferramenta = [
        _MensagemFalsa(tool_calls=[_ToolCallFalso(f"t{i}", "mover", '{"destino": "Floresta"}')]) for i in range(10)
    ]
    fake = _LLMFalso(sempre_chama_ferramenta)
    monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})

    narrativa, _eventos, chamadas = agent_loop.executar_turno([], executor, max_passos=3)

    assert "perdeu o fio" in narrativa
    assert len(chamadas) == 3
    assert fake.chamadas == 3


# -- executar_turno_stream (Etapa 7) -------------------------------------


class _DeltaFuncaoFalsa:
    def __init__(self, name: str | None = None, arguments: str | None = None) -> None:
        self.name = name
        self.arguments = arguments


class _DeltaToolCallFalso:
    def __init__(
        self,
        index: int,
        id: str | None = None,
        name: str | None = None,
        arguments: str | None = None,
        extra_content: dict | None = None,
    ) -> None:
        self.index = index
        self.id = id
        self.function = _DeltaFuncaoFalsa(name, arguments)
        if extra_content is not None:
            self.extra_content = extra_content


class _DeltaFalso:
    def __init__(self, content: str | None = None, tool_calls: list | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _ChunkFalso:
    def __init__(self, delta: _DeltaFalso) -> None:
        self.choices = [type("Choice", (), {"delta": delta})()]


class _StreamLLMFalso:
    """Uma fila de "passos" — cada passo é a lista de chunks que
    `chamar_stream_com_fallback` devolveria pra uma chamada do loop."""

    def __init__(self, passos: list[list[_ChunkFalso] | Exception]) -> None:
        self._passos = iter(passos)
        self.chamadas = 0

    def __call__(self, msgs, tools=None, tool_choice="auto"):
        self.chamadas += 1
        proximo = next(self._passos)
        if isinstance(proximo, Exception):
            raise proximo
        return iter(proximo)


class FakeExecutorEstruturado:
    """Mesmo contrato de `FakeExecutor`, mas gera `EventoRolagem` de verdade
    — necessário pra testar que `executar_turno_stream` emite "tool_event"
    só para eventos com dado estruturado (ver domain/eventos.py)."""

    def __init__(self, respostas: dict[str, tuple[dict, bool]]) -> None:
        self._respostas = respostas
        self.eventos: list[str] = []

    def executar(self, nome: str, args_json: str) -> tuple[dict, bool]:
        resultado, sucesso = self._respostas[nome]
        if sucesso:
            dados = DadosRolagem(tipo="teste", quem="heroi", d20=15, total=17, cd=10, sucesso=True)
            self.eventos.append(EventoRolagem(f"🎲 {nome} deu certo.", dados))
        return resultado, sucesso


def test_stream_sem_tool_calls_gera_so_tokens():
    passo = [_ChunkFalso(_DeltaFalso(content="Você entra ")), _ChunkFalso(_DeltaFalso(content="na taverna."))]
    fake = _StreamLLMFalso([passo])

    eventos = list(agent_loop.executar_turno_stream([], FakeExecutor({}), chamar_fn=fake))

    assert [e.tipo for e in eventos] == ["token", "token"]
    assert "".join(e.dados for e in eventos) == "Você entra na taverna."
    assert fake.chamadas == 1


def test_stream_tool_call_gera_tool_event_antes_da_narrativa_final():
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, id="t1", name="rolar_teste")])),
               _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, arguments='{"atributo": "destreza"}')]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Você se esgueira."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    executor = FakeExecutorEstruturado({"rolar_teste": ({"sucesso": True}, True)})

    eventos = list(agent_loop.executar_turno_stream([], executor, chamar_fn=fake))

    assert [e.tipo for e in eventos] == ["tool_event", "token"]
    assert eventos[0].dados["tipo"] == "teste"
    assert eventos[0].dados["texto"] == "🎲 rolar_teste deu certo."
    assert eventos[1].dados == "Você se esgueira."
    assert fake.chamadas == 2


def test_stream_mensagem_de_tool_call_nunca_manda_content_none():
    # Mesmo achado do teste síncrono acima, no caminho de streaming: aqui
    # `conteudo` começa como `""` (nenhum delta de texto chegou antes da
    # tool_call), e o bug original era `conteudo or None` — que também
    # rebaixava string vazia para `None`.
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, id="t1", name="rolar_teste")])),
               _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, arguments='{"atributo": "destreza"}')]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Você se esgueira."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    executor = FakeExecutorEstruturado({"rolar_teste": ({"sucesso": True}, True)})
    msgs: list[dict] = []

    list(agent_loop.executar_turno_stream(msgs, executor, chamar_fn=fake))

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    assert mensagem_assistente["content"] == ""
    assert mensagem_assistente["content"] is not None


def test_stream_thought_signature_e_ecoada_na_proxima_chamada():
    # Mesmo achado do teste síncrono, no caminho de streaming — a
    # assinatura costuma chegar num delta próprio (sem `id`/`nome`/`args`
    # junto), então precisa ser capturada em QUALQUER delta daquele índice.
    assinatura = {"google": {"thought_signature": "abc123"}}
    passo_1 = [
        _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, id="t1", name="rolar_teste")])),
        _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, arguments='{"atributo": "destreza"}')])),
        _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, extra_content=assinatura)])),
    ]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Você se esgueira."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    executor = FakeExecutorEstruturado({"rolar_teste": ({"sucesso": True}, True)})
    msgs: list[dict] = []

    list(agent_loop.executar_turno_stream(msgs, executor, chamar_fn=fake))

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    [tool_call] = mensagem_assistente["tool_calls"]
    assert tool_call["extra_content"] == assinatura


def test_stream_sem_thought_signature_nenhum_campo_extra_e_adicionado():
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, id="t1", name="rolar_teste")])),
               _ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, arguments='{"atributo": "destreza"}')]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Você se esgueira."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    executor = FakeExecutorEstruturado({"rolar_teste": ({"sucesso": True}, True)})
    msgs: list[dict] = []

    list(agent_loop.executar_turno_stream(msgs, executor, chamar_fn=fake))

    mensagem_assistente = next(m for m in msgs if m["role"] == "assistant")
    [tool_call] = mensagem_assistente["tool_calls"]
    assert "extra_content" not in tool_call


def test_stream_ferramenta_sem_evento_estruturado_nao_gera_tool_event():
    # FakeExecutor "comum" (do resto deste arquivo) só produz string solta,
    # sem EventoRolagem — não deve virar card.
    tc = _DeltaToolCallFalso(0, id="t1", name="mover", arguments='{"destino": "Floresta"}')
    passo_1 = [_ChunkFalso(_DeltaFalso(tool_calls=[tc]))]
    passo_2 = [_ChunkFalso(_DeltaFalso(content="Vocês chegam."))]
    fake = _StreamLLMFalso([passo_1, passo_2])
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})

    eventos = list(agent_loop.executar_turno_stream([], executor, chamar_fn=fake))

    assert [e.tipo for e in eventos] == ["token"]
    assert eventos[0].dados == "Vocês chegam."


def test_stream_erro_do_modelo_vira_evento_de_erro():
    fake = _StreamLLMFalso([ErroMestre("todos os modelos falharam")])

    eventos = list(agent_loop.executar_turno_stream([], FakeExecutor({}), chamar_fn=fake))

    assert len(eventos) == 1
    assert eventos[0].tipo == "erro"
    assert eventos[0].dados == "todos os modelos falharam"


def test_stream_limite_de_passos_estourado_gera_evento_de_erro():
    sempre_chama_ferramenta = [
        [_ChunkFalso(_DeltaFalso(tool_calls=[_DeltaToolCallFalso(0, id=f"t{i}", name="mover", arguments="{}")]))]
        for i in range(5)
    ]
    fake = _StreamLLMFalso(sempre_chama_ferramenta)
    executor = FakeExecutor({"mover": ({"local": "Floresta"}, True)})

    eventos = list(agent_loop.executar_turno_stream([], executor, max_passos=3, chamar_fn=fake))

    # Etapa 10 (A-7) tira o padrão `*(...)*` de todo frame de sistema — este
    # era o único lugar que ainda chegava como "token" em vez de "erro".
    assert eventos[-1].tipo == "erro"
    assert "perdeu o fio" in eventos[-1].dados
    assert fake.chamadas == 3
