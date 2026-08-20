"""Calibração do LLM-as-judge (Etapa 6, PLANO_MESTRE.md item 3): compara
`evals/annotations/humanas.yaml` (anotação humana real — `anotador !=
"piloto-ia"`) contra as notas do juiz nos mesmos cenários, e reporta
concordância: weighted Cohen's kappa quadrático, calculado à mão (sem
scikit-learn — o projeto evita dependências grandes por princípio, mesmo
espírito do ADR-0010, e o cálculo é ~15 linhas).

Se não houver nenhuma anotação humana real ainda (só piloto, ou nada),
`concordancia()` devolve `RelatorioConcordancia(n_pares=0, kappa_por_eixo={})`
— quem gera o relatório final imprime isso como "pendente", nunca inventa
um número (ver docs/adr/0011-estrategia-de-avaliacao.md)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from evals.judge import EIXOS, NotaJuiz

ANOTACOES_PATH = Path(__file__).parent / "annotations" / "humanas.yaml"


def carregar_anotacoes_humanas(caminho: Path | None = None) -> list[dict]:
    """Só as anotações de gente de verdade — `anotador == "piloto-ia"` é o
    piloto que valida o formato (ver evals/annotate.py), nunca conta como
    calibração real."""
    caminho = caminho or ANOTACOES_PATH
    if not caminho.exists():
        return []
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
    return [a for a in bruto if a.get("anotador") != "piloto-ia"]


def _kappa_quadratico(pares: list[tuple[int, int]], k: int = 5) -> float:
    """Weighted Cohen's kappa (peso quadrático), categorias inteiras 1..k."""
    n = len(pares)
    if n == 0:
        return 0.0
    matriz = [[0] * k for _ in range(k)]
    for a, b in pares:
        matriz[a - 1][b - 1] += 1
    marg_linha = [sum(matriz[i]) for i in range(k)]
    marg_coluna = [sum(matriz[i][j] for i in range(k)) for j in range(k)]

    peso_max = (k - 1) ** 2
    do = 0.0
    de = 0.0
    for i in range(k):
        for j in range(k):
            peso = (i - j) ** 2 / peso_max
            do += matriz[i][j] * peso
            de += (marg_linha[i] * marg_coluna[j] / n) * peso
    if de == 0:
        return 1.0  # todo mundo deu a mesma nota nos dois lados — concordância perfeita degenerada
    return 1 - do / de


@dataclass
class RelatorioConcordancia:
    n_pares: int
    kappa_por_eixo: dict[str, float]


def concordancia(anotacoes_humanas: list[dict], notas_juiz: dict[str, NotaJuiz | None]) -> RelatorioConcordancia:
    comuns = [a for a in anotacoes_humanas if notas_juiz.get(a["id"]) is not None]
    if not comuns:
        return RelatorioConcordancia(n_pares=0, kappa_por_eixo={})

    kappa_por_eixo = {}
    for eixo in EIXOS:
        pares = [(a[eixo], getattr(notas_juiz[a["id"]], eixo)) for a in comuns]
        kappa_por_eixo[eixo] = _kappa_quadratico(pares)
    return RelatorioConcordancia(n_pares=len(comuns), kappa_por_eixo=kappa_por_eixo)
