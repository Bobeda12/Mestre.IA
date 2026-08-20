"""Métricas determinísticas (Etapa 6, PLANO_MESTRE.md item 2) — nenhuma
delas chama um LLM. Cada uma recebe `list[ResultadoCenario]` (produzido por
`evals/harness.py::rodar_cenario`) e devolve um número ou uma pequena
tabela. `tool_call_accuracy` promove a lógica de
`scripts/tool_call_accuracy.py` (Etapa 4) para o dataset de 60 cenários."""

from __future__ import annotations

import json
from dataclasses import dataclass

from evals.harness import ResultadoCenario


def _bate(valor_modelo: object, valor_esperado: object) -> bool:
    if isinstance(valor_esperado, str):
        return isinstance(valor_modelo, str) and valor_esperado.lower() in valor_modelo.lower()
    return valor_modelo == valor_esperado


def taxa_ferramenta_valida(resultados: list[ResultadoCenario]) -> float:
    """1 - (chamadas malformadas / chamadas totais). O `ToolExecutor` já
    garante que nenhum JSON quebrado passa (ver `tools.py::executar`) —
    esta métrica só torna visível o quanto isso acontece na prática."""
    total = sum(len(r.chamadas) for r in resultados)
    if total == 0:
        return 1.0
    validas = sum(1 for r in resultados for c in r.chamadas if c.sucesso)
    return validas / total


def tool_call_accuracy(resultados: list[ResultadoCenario]) -> tuple[float | None, float | None]:
    """(% ferramenta certa, % ferramenta+args certos), só entre cenários com
    `ferramenta_esperada` definido — `None` no cenário significa "não
    avaliar tool-call accuracy aqui" (ex: `injecao_prompt`, onde o
    comportamento certo pode ser não chamar ferramenta nenhuma). Devolve
    `(None, None)` se nenhum cenário do lote for aplicável."""
    aplicaveis = [r for r in resultados if r.cenario.ferramenta_esperada]
    if not aplicaveis:
        return None, None

    acertos_ferramenta = 0
    acertos_completos = 0
    for r in aplicaveis:
        primeira = r.chamadas[0] if r.chamadas else None
        if primeira is None:
            continue
        nome_ok = primeira.nome == r.cenario.ferramenta_esperada
        try:
            args = json.loads(primeira.args) if primeira.args else {}
        except json.JSONDecodeError:
            args = {}
        args_ok = nome_ok and all(_bate(args.get(k), v) for k, v in r.cenario.args_esperados.items())
        acertos_ferramenta += int(nome_ok)
        acertos_completos += int(args_ok)

    n = len(aplicaveis)
    return acertos_ferramenta / n, acertos_completos / n


def taxa_violacao_estado(resultados: list[ResultadoCenario]) -> float:
    """% de cenários cuja narrativa final contradiz o estado — reusa o
    guardrail da Etapa 4 (`services/guardrail.py::validar_narrativa`), já
    aplicado dentro de `evals/harness.py::rodar_cenario`."""
    if not resultados:
        return 0.0
    return sum(1 for r in resultados if r.violacoes) / len(resultados)


def taxa_erro_execucao(resultados: list[ResultadoCenario]) -> float:
    """% de cenários em que o turno nem terminou (ErroMestre, falha de
    API) — distinto de violação de estado: aqui não houve narrativa nenhuma."""
    if not resultados:
        return 0.0
    return sum(1 for r in resultados if r.erro) / len(resultados)


def _percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, round(p * (len(ordenados) - 1)))
    return ordenados[indice]


def latencia_p50_p95(resultados: list[ResultadoCenario]) -> tuple[float, float]:
    tempos = [c.latencia_s for r in resultados for c in r.chamadas_llm]
    return _percentil(tempos, 0.5), _percentil(tempos, 0.95)


def tokens_totais(resultados: list[ResultadoCenario]) -> tuple[int, int]:
    """(tokens de prompt, tokens de completion) somados em toda a rodada.
    Não converte para custo em R$/US$: não há tabela de preço da Groq
    confiável o bastante para publicar no relatório — ver ADR-0011."""
    prompt = sum(c.prompt_tokens for r in resultados for c in r.chamadas_llm)
    completion = sum(c.completion_tokens for r in resultados for c in r.chamadas_llm)
    return prompt, completion


@dataclass
class MetricasAgregadas:
    n_cenarios: int
    taxa_ferramenta_valida: float
    tool_call_ferramenta_certa: float | None
    tool_call_args_certos: float | None
    taxa_violacao_estado: float
    taxa_erro_execucao: float
    latencia_p50_s: float
    latencia_p95_s: float
    tokens_prompt_total: int
    tokens_completion_total: int


def agregar(resultados: list[ResultadoCenario]) -> MetricasAgregadas:
    ferramenta_certa, args_certos = tool_call_accuracy(resultados)
    p50, p95 = latencia_p50_p95(resultados)
    prompt_tok, completion_tok = tokens_totais(resultados)
    return MetricasAgregadas(
        n_cenarios=len(resultados),
        taxa_ferramenta_valida=taxa_ferramenta_valida(resultados),
        tool_call_ferramenta_certa=ferramenta_certa,
        tool_call_args_certos=args_certos,
        taxa_violacao_estado=taxa_violacao_estado(resultados),
        taxa_erro_execucao=taxa_erro_execucao(resultados),
        latencia_p50_s=p50,
        latencia_p95_s=p95,
        tokens_prompt_total=prompt_tok,
        tokens_completion_total=completion_tok,
    )
