"""O loop de agente (Etapa 4, ADR-0007): troca o "uma chamada, um JSON" da
Etapa 3 por "chame ferramentas até terminar, ou até estourar o limite de
passos". `services/narrator.py` monta o prompt; este módulo só orquestra a
ida e volta com o modelo e o despacho de ferramentas via `tools.ToolExecutor`
— zero regra de jogo aqui, isso é `rules_engine.py`/`combat.py`."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.infra.llm_client import chamar_com_fallback
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
