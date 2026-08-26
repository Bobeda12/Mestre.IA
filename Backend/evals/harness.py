"""Harness (Etapa 6): roda um `CenarioAvaliacao` pelo caminho de produção
real — `narrator.montar_contexto` + `agent_loop.executar_turno` +
`tools.ToolExecutor` + `guardrail.validar_narrativa` — em vez de uma
simulação paralela. As únicas coisas que `routers/game.py` faz e este
harness NÃO replica: persistência em banco, e o desvio especial para
`heroi.hp_atual <= 0` (que troca para um prompt sem ferramentas) — ver a
nota no topo de `evals/golden/caso_limite.yaml`."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.domain.state import QuestLog
from app.infra import embeddings
from app.infra.db import Personagem
from app.infra.llm_client import chamar_com_fallback
from app.services import agent_loop
from app.services.agent_loop import ChamadaFerramenta
from app.services.guardrail import validar_narrativa
from app.services.hybrid_search import Documento, buscar
from app.services.narrator import montar_contexto
from app.services.tools import ToolExecutor
from evals.schema import CenarioAvaliacao


@dataclass
class ChamadaLLMRegistrada:
    modelo: str | None
    prompt_tokens: int
    completion_tokens: int
    latencia_s: float


@dataclass
class ResultadoCenario:
    cenario: CenarioAvaliacao
    narrativa: str
    chamadas: list[ChamadaFerramenta]
    violacoes: list[str]
    heroi_final: Personagem
    chamadas_llm: list[ChamadaLLMRegistrada] = field(default_factory=list)
    erro: str | None = None


def _com_registro(chamar_base: Callable[..., Any], registros: list[ChamadaLLMRegistrada]) -> Callable[..., Any]:
    """Envolve qualquer `chamar_fn` (chamar_com_fallback ou um
    chamar_modelo_unico parcial) para capturar latência e tokens de cada
    chamada, sem `agent_loop.py` precisar saber nada sobre avaliação."""

    def _wrapped(msgs: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> Any:
        inicio = time.perf_counter()
        resp = chamar_base(msgs, tools=tools, tool_choice=tool_choice)
        latencia = time.perf_counter() - inicio
        usage = getattr(resp, "usage", None)
        registros.append(
            ChamadaLLMRegistrada(
                modelo=getattr(resp, "model", None),
                prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                latencia_s=latencia,
            )
        )
        return resp

    return _wrapped


def montar_heroi(cenario: CenarioAvaliacao) -> Personagem:
    """Objeto solto, nunca persistido — mesmo padrão de
    `tests/test_tools.py::_heroi` (Etapa 4)."""
    return Personagem(**cenario.estado_inicial.heroi)


def montar_memorias(
    cenario: CenarioAvaliacao,
    turno_atual: int,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> list[str]:
    """Semeia a memória de longo prazo do cenário como `Documento`s em
    memória e devolve o resultado da busca híbrida — exatamente o que
    `routers/game.py` injeta em `montar_contexto`, só sem precisar de um
    banco (`services/memory.memorias_relevantes` é a versão com banco)."""
    eventos = cenario.estado_inicial.eventos_memoria
    if not eventos:
        return []
    embed_fn = embed_fn or embeddings.embed_um
    documentos = [
        Documento(id=i, texto=evento.texto, embedding=embed_fn(evento.texto), turno=evento.turno)
        for i, evento in enumerate(eventos)
    ]
    encontrados = buscar(cenario.acao_jogador, documentos, turno_atual=turno_atual, embed_fn=embed_fn)
    return [d.texto for d in encontrados]


def rodar_cenario(
    cenario: CenarioAvaliacao,
    chamar_fn: Callable[..., Any] | None = None,
    rng: random.Random | None = None,
    embed_fn: Callable[[str], list[float]] | None = None,
    max_passos: int = 6,
) -> ResultadoCenario:
    """Roda 1 cenário pelo caminho real de produção (sem persistência).
    `chamar_fn` default é `chamar_com_fallback`; o bake-off passa um
    `chamar_modelo_unico` parcial para mirar um modelo específico — ver
    `evals/run_eval.py`. Objetos do estado inicial são copiados (nunca o
    cenário original é mutado), porque o mesmo `CenarioAvaliacao` é reusado
    entre modelos no bake-off."""
    heroi = montar_heroi(cenario)
    combate = cenario.estado_inicial.combate.model_copy(deep=True)
    mundo = cenario.estado_inicial.mundo.model_copy(deep=True)
    missao = cenario.estado_inicial.missao.model_copy(deep=True)
    resumo = cenario.estado_inicial.resumo_rolante.model_copy(deep=True)

    memorias = montar_memorias(cenario, mundo.turno, embed_fn=embed_fn)
    nomes_na_cena = {i.nome for i in combate.inimigos} | set(resumo.npcs_conhecidos)
    reputacoes = {nome: valor for nome, valor in heroi.reputacao_npcs.items() if nome in nomes_na_cena}

    contexto = montar_contexto(heroi, mundo, combate, missao, memorias=memorias, resumo=resumo, reputacoes=reputacoes)
    msgs = [{"role": "system", "content": contexto}, {"role": "user", "content": cenario.acao_jogador}]

    registros: list[ChamadaLLMRegistrada] = []
    chamada_registrada = _com_registro(chamar_fn or chamar_com_fallback, registros)
    executor = ToolExecutor(heroi, combate, mundo, QuestLog(), rng=rng)

    try:
        narrativa, _eventos, chamadas = agent_loop.executar_turno(
            msgs, executor, max_passos=max_passos, chamar_fn=chamada_registrada
        )
    except Exception as e:  # ErroMestre ou qualquer falha de API — 1 cenário não derruba a suíte inteira
        return ResultadoCenario(
            cenario=cenario,
            narrativa="",
            chamadas=[],
            violacoes=[],
            heroi_final=heroi,
            chamadas_llm=registros,
            erro=str(e),
        )

    violacoes = validar_narrativa(narrativa, heroi, combate, mundo)
    return ResultadoCenario(
        cenario=cenario,
        narrativa=narrativa,
        chamadas=chamadas,
        violacoes=violacoes,
        heroi_final=heroi,
        chamadas_llm=registros,
    )
