"""Testa app/services/agent_loop.py — o controle do loop em si (quantos
passos, quando para, o que faz com ferramenta malformada), sem depender da
API da Groq de verdade nem das ferramentas reais de tools.py. Um `_FakeLLM`
substitui `chamar_com_fallback`; um `FakeExecutor` substitui `ToolExecutor`."""

from app.services import agent_loop


class _FuncaoFalsa:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCallFalso:
    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id = id
        self.function = _FuncaoFalsa(name, arguments)


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
