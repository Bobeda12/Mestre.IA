"""CLI principal da suíte de avaliação (Etapa 6). Roda o golden dataset
(`evals/golden/*.yaml`) pelo caminho de produção real (`evals/harness.py`),
agrega métricas determinísticas (`evals/metrics.py`) e, por padrão, também
o LLM-as-judge (`evals/judge.py`). É o script usado por três consumidores:

  1. Uso manual, ao vivo, contra a Groq de verdade — mesma prática de
     "testar ao vivo cedo" das Etapas 4 e 5.
  2. O job `avaliacao` do CI (`.github/workflows/ci.yml`, `workflow_dispatch`
     manual — não roda em todo PR, ver ADR-0011), com `--comparar-baseline`.
  3. O bake-off de modelos (`--bake-off`), que gera a tabela de
     `docs/relatorios/0001-avaliacao-v1.md`.

Uso:
    uv run python -m evals.run_eval
    uv run python -m evals.run_eval --categoria combate --amostra-por-categoria 2
    uv run python -m evals.run_eval --bake-off --sem-juiz
    uv run python -m evals.run_eval --comparar-baseline
    uv run python -m evals.run_eval --salvar-cache evals/cache/resultados.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.infra.llm_client import chamar_com_fallback, chamar_modelo_unico
from app.infra.settings import settings
from evals import metrics
from evals.harness import ResultadoCenario, rodar_cenario
from evals.judge import julgar_lote, media_por_eixo, taxa_parse_valido
from evals.metrics import MetricasAgregadas
from evals.schema import CenarioAvaliacao, carregar_cenarios

BASELINE_PATH = Path(__file__).parent / "baseline.json"
# Pesos da pontuação agregada de 0 a 1 usada pelo gate de CI — ver
# ADR-0011 para a justificativa de cada termo. Tool-call accuracy só entra
# se houver cenário aplicável na amostra rodada.
_PESO_JUIZ = 0.4
_PESO_FERRAMENTA_VALIDA = 0.15
_PESO_TOOL_CALL = 0.25
_PESO_SEM_VIOLACAO = 0.15
_PESO_SEM_ERRO = 0.05


def _fixar_modelo(modelo: str) -> Callable[..., Any]:
    def _chamar(msgs: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> Any:
        return chamar_modelo_unico(modelo, msgs, tools=tools, tool_choice=tool_choice)

    return _chamar


def _selecionar_cenarios(
    categorias: list[str] | None,
    amostra_por_categoria: int | None,
    seed: int,
) -> list[CenarioAvaliacao]:
    todos = carregar_cenarios()
    if categorias:
        todos = [c for c in todos if c.categoria in categorias]
    if amostra_por_categoria is None:
        return todos

    rng = random.Random(seed)
    por_categoria: dict[str, list[CenarioAvaliacao]] = {}
    for c in todos:
        por_categoria.setdefault(c.categoria, []).append(c)
    selecionados: list[CenarioAvaliacao] = []
    for lista in por_categoria.values():
        selecionados.extend(rng.sample(lista, min(amostra_por_categoria, len(lista))))
    return selecionados


def rodar_suite(
    cenarios: list[CenarioAvaliacao],
    chamar_fn: Callable[..., Any] | None,
    com_juiz: bool,
    juiz_modelo: str | None = None,
) -> tuple[list[ResultadoCenario], MetricasAgregadas, dict[str, float], float]:
    """Devolve (resultados, métricas determinísticas, média do juiz por
    eixo, taxa de parse válido do juiz). Se `com_juiz` for False, os dois
    últimos valores são `{}`/`1.0` (não avaliados, não "zero")."""
    resultados = [rodar_cenario(c, chamar_fn=chamar_fn) for c in cenarios]
    agregadas = metrics.agregar(resultados)
    if not com_juiz:
        return resultados, agregadas, {}, 1.0

    notas = julgar_lote(resultados, modelo=juiz_modelo)
    return resultados, agregadas, media_por_eixo(notas), taxa_parse_valido(notas)


def pontuacao_agregada(agregadas: MetricasAgregadas, media_eixos_juiz: dict[str, float]) -> float:
    """Um único número em [0, 1] — usado pelo gate de CI para comparar
    contra `evals/baseline.json`. Pesos documentados em ADR-0011; a nota do
    juiz é normalizada de 1-5 para 0-1 antes de entrar na média ponderada."""
    partes: list[tuple[float, float]] = [
        (_PESO_FERRAMENTA_VALIDA, agregadas.taxa_ferramenta_valida),
        (_PESO_SEM_VIOLACAO, 1 - agregadas.taxa_violacao_estado),
        (_PESO_SEM_ERRO, 1 - agregadas.taxa_erro_execucao),
    ]
    if agregadas.tool_call_ferramenta_certa is not None:
        partes.append((_PESO_TOOL_CALL, agregadas.tool_call_ferramenta_certa))
    if media_eixos_juiz:
        media_juiz_normalizada = (sum(media_eixos_juiz.values()) / len(media_eixos_juiz) - 1) / 4
        partes.append((_PESO_JUIZ, media_juiz_normalizada))

    peso_total = sum(p for p, _ in partes)
    if peso_total == 0:
        return 0.0
    return sum(p * v for p, v in partes) / peso_total


def _imprimir_relatorio(agregadas: MetricasAgregadas, media_eixos_juiz: dict[str, float], taxa_parse: float) -> None:
    print(f"Cenários rodados: {agregadas.n_cenarios}")
    print(f"Taxa de ferramenta válida: {agregadas.taxa_ferramenta_valida:.0%}")
    if agregadas.tool_call_ferramenta_certa is not None:
        print(f"Tool-call accuracy (ferramenta certa): {agregadas.tool_call_ferramenta_certa:.0%}")
        print(f"Tool-call accuracy (ferramenta+args certos): {agregadas.tool_call_args_certos:.0%}")
    print(f"Taxa de violação de estado (guardrail): {agregadas.taxa_violacao_estado:.0%}")
    print(f"Taxa de erro de execução: {agregadas.taxa_erro_execucao:.0%}")
    print(f"Latência p50/p95: {agregadas.latencia_p50_s:.2f}s / {agregadas.latencia_p95_s:.2f}s")
    print(f"Tokens (prompt/completion): {agregadas.tokens_prompt_total} / {agregadas.tokens_completion_total}")
    if media_eixos_juiz:
        print(f"Juiz — taxa de parse válido: {taxa_parse:.0%}")
        for eixo, media in media_eixos_juiz.items():
            print(f"  {eixo}: {media:.2f}/5")
    print(f"Pontuação agregada: {pontuacao_agregada(agregadas, media_eixos_juiz):.3f}")


def _salvar_cache(caminho: Path, resultados: list[ResultadoCenario]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    itens = [
        {
            "id": r.cenario.id,
            "categoria": r.cenario.categoria,
            "descricao": r.cenario.descricao,
            "acao_jogador": r.cenario.acao_jogador,
            "resultado_mecanico_esperado": r.cenario.resultado_mecanico_esperado,
            "notas_rubrica": r.cenario.notas_rubrica,
            "narrativa": r.narrativa,
        }
        for r in resultados
    ]
    caminho.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--categoria", action="append", help="Filtra por categoria; repita a flag para várias.")
    parser.add_argument("--amostra-por-categoria", type=int, default=None, help="Amostra N cenários por categoria.")
    parser.add_argument("--seed", type=int, default=42, help="Seed da amostragem (--amostra-por-categoria).")
    parser.add_argument(
        "--modelo", default=None, help="Mira um modelo específico ('provedor:modelo', bypassa a cadeia)."
    )
    parser.add_argument("--bake-off", action="store_true", help="Roda contra cada elo de settings.cadeia_llm.")
    parser.add_argument("--sem-juiz", action="store_true", help="Pula o LLM-as-judge (só métricas).")
    parser.add_argument("--juiz-modelo", default=None, help="Modelo do juiz (default: settings.modelo_barato).")
    parser.add_argument("--comparar-baseline", action="store_true", help="Sai com 1 se ficar abaixo do baseline.")
    parser.add_argument("--salvar-baseline", action="store_true", help="Grava a pontuação atual em baseline.json.")
    parser.add_argument("--margem", type=float, default=0.05, help="Margem tolerada ao salvar o baseline.")
    parser.add_argument("--nota-baseline", default="", help="Anotação de proveniência gravada com o baseline.")
    parser.add_argument("--salvar-cache", type=Path, default=None, help="Salva narrativas p/ evals/annotate.py.")
    parser.add_argument("--salvar-relatorio", type=Path, default=None, help="Salva o relatório completo em JSON.")
    args = parser.parse_args()

    cenarios = _selecionar_cenarios(args.categoria, args.amostra_por_categoria, args.seed)
    if not cenarios:
        print("Nenhum cenário selecionado — confira --categoria.")
        sys.exit(1)

    modelos_alvo = settings.cadeia_llm if args.bake_off else [args.modelo] if args.modelo else [None]
    relatorio: dict[str, Any] = {"n_cenarios": len(cenarios), "modelos": {}}
    ultima_pontuacao = 0.0
    ultimos_resultados: list[ResultadoCenario] = []

    for modelo in modelos_alvo:
        rotulo = modelo or "cadeia_de_fallback"
        print(f"\n=== {rotulo} ({len(cenarios)} cenários) ===")
        chamar_fn = _fixar_modelo(modelo) if modelo else chamar_com_fallback
        resultados, agregadas, media_eixos_juiz, taxa_parse = rodar_suite(
            cenarios, chamar_fn, com_juiz=not args.sem_juiz, juiz_modelo=args.juiz_modelo
        )
        _imprimir_relatorio(agregadas, media_eixos_juiz, taxa_parse)
        ultima_pontuacao = pontuacao_agregada(agregadas, media_eixos_juiz)
        ultimos_resultados = resultados
        relatorio["modelos"][rotulo] = {
            "metricas": asdict(agregadas),
            "juiz_media_por_eixo": media_eixos_juiz,
            "juiz_taxa_parse_valido": taxa_parse,
            "pontuacao_agregada": ultima_pontuacao,
        }

    if args.salvar_cache:
        _salvar_cache(args.salvar_cache, ultimos_resultados)
        print(f"\nCache salvo em {args.salvar_cache}")

    if args.salvar_relatorio:
        args.salvar_relatorio.parent.mkdir(parents=True, exist_ok=True)
        args.salvar_relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Relatório salvo em {args.salvar_relatorio}")

    if args.salvar_baseline:
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "pontuacao_agregada": ultima_pontuacao,
                    "margem_tolerada": args.margem,
                    "n_cenarios": len(cenarios),
                    "nota": args.nota_baseline,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nBaseline salvo em {BASELINE_PATH}: {ultima_pontuacao:.3f} (margem {args.margem}).")

    if args.comparar_baseline:
        if not BASELINE_PATH.exists():
            print(f"\nSem baseline salvo em {BASELINE_PATH} — nada para comparar (rode com --salvar-baseline antes).")
            sys.exit(1)
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        limiar = baseline["pontuacao_agregada"] - baseline.get("margem_tolerada", 0.05)
        print(f"\nPontuação atual: {ultima_pontuacao:.3f} — limiar do baseline: {limiar:.3f}")
        if ultima_pontuacao < limiar:
            print("REPROVADO: pontuação caiu abaixo do baseline.")
            sys.exit(1)
        print("Aprovado.")


if __name__ == "__main__":
    main()
