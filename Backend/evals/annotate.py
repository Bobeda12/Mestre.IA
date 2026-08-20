"""CLI de anotação humana (Etapa 6) — para calibrar o LLM-as-judge contra
~30 exemplos anotados por uma pessoa de verdade, com a concordância juiz×
humano reportada em `evals/calibracao.py`. Não anota nada sozinho: lê
narrativas já rodadas (um cache JSON produzido por
`run_eval.py --salvar-cache`), pergunta 4 notas por teclado, uma de cada
vez, e grava incrementalmente em `evals/annotations/humanas.yaml` — pode ser
interrompido (Ctrl+C ou 'q') e retomado depois sem perder o que já foi feito.

Uso:
    uv run python -m evals.run_eval --salvar-cache evals/cache/resultados.json
    uv run python -m evals.annotate --cache evals/cache/resultados.json --anotador breno
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from evals.judge import EIXOS

ANOTACOES_PATH = Path(__file__).parent / "annotations" / "humanas.yaml"


def _carregar_cache(caminho: Path) -> list[dict]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _carregar_anotacoes() -> list[dict]:
    if not ANOTACOES_PATH.exists():
        return []
    return yaml.safe_load(ANOTACOES_PATH.read_text(encoding="utf-8")) or []


def _salvar_anotacoes(anotacoes: list[dict]) -> None:
    ANOTACOES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANOTACOES_PATH.write_text(yaml.dump(anotacoes, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _pedir_nota(rotulo: str) -> int:
    while True:
        bruto = input(f"  {rotulo} (1-5): ").strip()
        if bruto.isdigit() and 1 <= int(bruto) <= 5:
            return int(bruto)
        print("  precisa ser um número inteiro de 1 a 5.")


def rodar(caminho_cache: Path, anotador: str, limite: int | None = None) -> None:
    itens = _carregar_cache(caminho_cache)
    anotacoes = _carregar_anotacoes()
    ja_anotados = {(a["id"], a["anotador"]) for a in anotacoes}

    feitos = 0
    for item in itens:
        if limite is not None and feitos >= limite:
            break
        if (item["id"], anotador) in ja_anotados:
            continue

        print("\n" + "=" * 70)
        print(f"[{item['categoria']}] {item['id']} — {item['descricao']}")
        print(f"Ação do jogador: {item['acao_jogador']}")
        print(f"Resultado mecânico esperado: {item.get('resultado_mecanico_esperado') or '(não especificado)'}")
        print("-" * 70)
        print(item["narrativa"])
        print("-" * 70)

        resposta = input("Anotar este cenário? [s/N/q para sair] ").strip().lower()
        if resposta == "q":
            break
        if resposta != "s":
            continue

        notas = {eixo: _pedir_nota(eixo) for eixo in EIXOS}
        anotacoes.append({"id": item["id"], "anotador": anotador, **notas})
        _salvar_anotacoes(anotacoes)
        feitos += 1
        print(f"  salvo. ({feitos} anotados nesta sessão)")

    print(f"\nSessão encerrada — {feitos} cenário(s) anotado(s) por '{anotador}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True, help="JSON produzido por run_eval.py --salvar-cache")
    parser.add_argument("--anotador", required=True, help="Seu identificador (ex: 'breno'). Não use 'piloto-ia'.")
    parser.add_argument("--limite", type=int, default=None, help="Parar depois de N cenários novos anotados.")
    args = parser.parse_args()

    if args.anotador == "piloto-ia":
        raise SystemExit(
            "'piloto-ia' é reservado para o piloto do autor do harness (evals/annotations/humanas.yaml) "
            "— use seu próprio identificador para a anotação valer para calibração de verdade."
        )

    rodar(args.cache, args.anotador, args.limite)


if __name__ == "__main__":
    main()
