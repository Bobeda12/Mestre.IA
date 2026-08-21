"""O loop de agente (Etapa 4, ADR-0007): troca o "uma chamada, um JSON" da
Etapa 3 por "chame ferramentas até terminar, ou até estourar o limite de
passos". `services/narrator.py` monta o prompt; este módulo só orquestra a
ida e volta com o modelo e o despacho de ferramentas via `tools.ToolExecutor`
— zero regra de jogo aqui, isso é `rules_engine.py`/`combat.py`."""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.domain.eventos import EventoRolagem
from app.infra.llm_client import ErroMestre, chamar_com_fallback, chamar_stream_com_fallback
from app.services.tools import TOOLS_SCHEMA


class ExecutorFerramentas(Protocol):
    """O loop só precisa disto de um executor — `tools.ToolExecutor` é a
    implementação real; testes usam um `FakeExecutor` mais simples que
    também satisfaz este contrato, sem precisar herdar de nada."""

    eventos: list[str]

    def executar(self, nome: str, args_json: str) -> tuple[dict, bool]: ...


@dataclass
class ChamadaFerramenta:
    nome: str
    args: str
    sucesso: bool


def executar_turno(
    msgs: list[dict],
    executor: ExecutorFerramentas,
    max_passos: int = 6,
    chamar_fn: Callable[..., Any] | None = None,
) -> tuple[str, list[str], list[ChamadaFerramenta]]:
    """Devolve (narrativa final, eventos das ferramentas, chamadas feitas).
    `msgs` é mutado (mensagens de assistant/tool são anexadas) — é uma lista
    de turno único, descartada depois; só a narrativa final entra no
    histórico persistido (mesmo contrato de antes, ver routers/game.py).

    `chamar_fn` (Etapa 6): por padrão é `chamar_com_fallback` (comportamento
    de produção inalterado), mas `evals/harness.py` injeta uma variante que
    (a) mira um modelo específico, para o bake-off, e/ou (b) registra
    latência e tokens de cada chamada — sem este módulo precisar saber nada
    sobre avaliação. O default é resolvido dentro do corpo da função, não no
    cabeçalho (`chamar_fn or chamar_com_fallback`), para que
    `monkeypatch.setattr(agent_loop, "chamar_com_fallback", fake)` (usado em
    tests/test_agent_loop.py desde a Etapa 4) continue funcionando — um
    default vinculado no cabeçalho capturaria a função original na
    definição do módulo, antes de qualquer monkeypatch."""
    chamar_fn = chamar_fn or chamar_com_fallback
    chamadas: list[ChamadaFerramenta] = []

    for _passo in range(max_passos):
        resp = chamar_fn(msgs, tools=TOOLS_SCHEMA, tool_choice="auto")
        mensagem = resp.choices[0].message

        if not mensagem.tool_calls:
            return mensagem.content or "", executor.eventos, chamadas

        msgs.append(
            {
                "role": "assistant",
                "content": mensagem.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in mensagem.tool_calls
                ],
            }
        )

        for tc in mensagem.tool_calls:
            resultado, sucesso = executor.executar(tc.function.name, tc.function.arguments)
            chamadas.append(ChamadaFerramenta(tc.function.name, tc.function.arguments, sucesso))
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(resultado, ensure_ascii=False)})

    return (
        "*(O mestre perdeu o fio da meada tentando decidir o que fazer — tente uma ação mais simples.)*",
        executor.eventos,
        chamadas,
    )


@dataclass
class EventoStream:
    """Um pedaço do turno, na ordem em que sai de `executar_turno_stream`.

    `tipo`: "token" (um pedaço de texto de narração — `dados` é `str`),
    "tool_event" (uma ferramenta resolveu — `dados` é o dict estruturado da
    rolagem, pronto pro card do frontend) ou "erro" (o turno não se
    recupera sozinho — `dados` é a mensagem, ver `ErroMestre`)."""

    tipo: Literal["token", "tool_event", "erro"]
    dados: Any


def executar_turno_stream(
    msgs: list[dict],
    executor: ExecutorFerramentas,
    max_passos: int = 6,
    chamar_fn: Callable[..., Any] | None = None,
) -> Iterator[EventoStream]:
    """Mesma orquestração de `executar_turno` (chame ferramentas até
    terminar, ou até `max_passos`), em streaming (Etapa 7, ADR-0012) — não
    substitui a versão síncrona: `evals/harness.py` e o `/chat` de sempre
    continuam usando `executar_turno`, sem risco pro framework de avaliação
    da Etapa 6.

    Deltas de `tool_calls` NUNCA viram evento "token" — só texto de
    narração é mostrado ao vivo; o JSON dos argumentos de uma ferramenta
    ainda em montagem não interessa ao jogador, só o resultado final dela
    (o "tool_event", emitido depois que `executor.executar` já rodou)."""
    chamar_fn = chamar_fn or chamar_stream_com_fallback

    for _passo in range(max_passos):
        conteudo = ""
        chamadas_parciais: dict[int, dict[str, str]] = {}

        try:
            for chunk in chamar_fn(msgs, tools=TOOLS_SCHEMA, tool_choice="auto"):
                delta = chunk.choices[0].delta
                if delta.content:
                    conteudo += delta.content
                    yield EventoStream("token", delta.content)
                for tc in delta.tool_calls or []:
                    slot = chamadas_parciais.setdefault(tc.index, {"id": "", "nome": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["nome"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
        except ErroMestre as e:
            yield EventoStream("erro", e.mensagem)
            return

        if not chamadas_parciais:
            return

        msgs.append(
            {
                "role": "assistant",
                "content": conteudo or None,
                "tool_calls": [
                    {
                        "id": slot["id"],
                        "type": "function",
                        "function": {"name": slot["nome"], "arguments": slot["args"]},
                    }
                    for slot in chamadas_parciais.values()
                ],
            }
        )

        for slot in chamadas_parciais.values():
            len_antes = len(executor.eventos)
            resultado, _sucesso = executor.executar(slot["nome"], slot["args"])
            for evento in executor.eventos[len_antes:]:
                if isinstance(evento, EventoRolagem) and evento.dados is not None:
                    yield EventoStream("tool_event", {"texto": str(evento), **evento.dados.to_dict()})
            msgs.append(
                {"role": "tool", "tool_call_id": slot["id"], "content": json.dumps(resultado, ensure_ascii=False)}
            )

    yield EventoStream(
        "token", "*(O mestre perdeu o fio da meada tentando decidir o que fazer — tente uma ação mais simples.)*"
    )
