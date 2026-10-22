"""Simulação de campanha sem LLM: ritmo de XP, ouro, itens e repetição de
inimigos ao longo dos níveis, pelos mesmos módulos que o jogo usa
(`combat.iniciar_combate`, `loot.gerar_loot`, `rules_engine.XP_POR_NIVEL`).

Não mede se o herói vence (isso é do `simulador.py`): assume vitória e conta
o que a vitória rende. Serve para responder "o jogo recompensa e varia?".

Uso:
    uv run python -m evals.campanha --campanhas 200 --passo-a-cada 3
"""

import argparse
import random
from collections import Counter
from dataclasses import dataclass, field

from app.services import capitulo, combat, living_world
from app.services import rules_engine as motor
from app.services.loot import gerar_loot, recompensa_arco

NIVEL_MAX = max(motor.XP_POR_NIVEL)
ENCONTROS_POS_MAX = 20  # quanto jogar depois do nível máximo, para medir o "teto"


@dataclass
class Nivel:
    encontros: list[int] = field(default_factory=list)  # encontros gastos neste nível, por campanha
    ouro: list[int] = field(default_factory=list)
    itens: list[int] = field(default_factory=list)
    vistos: Counter = field(default_factory=Counter)  # arquétipo -> vezes que apareceu


def _proximo_xp(nivel: int) -> int | None:
    return motor.XP_POR_NIVEL.get(nivel + 1)


def simular(campanhas: int, passo_a_cada: int, semente: int) -> dict[int, Nivel]:
    por_nivel = {n: Nivel() for n in range(1, NIVEL_MAX + 1)}
    for c in range(campanhas):
        rng = random.Random(semente + c)
        nivel, xp = 1, 0
        encontros_no_nivel = ouro_no_nivel = itens_no_nivel = total = 0
        pos_max = 0
        while True:
            total += 1
            # O narrador costuma propor 1 nome; chefe de arco fica de fora.
            estado, _, _ = combat.iniciar_combate([f"Inimigo {total}"], {}, 12, rng=rng, nivel_heroi=nivel)
            for i in estado.inimigos:
                i.hp = 0
                por_nivel[nivel].vistos[i.arquetipo or i.nome] += 1
            saque = gerar_loot(estado.inimigos, rng)
            xp += sum(i.xp for i in estado.inimigos)
            ouro_no_nivel += saque.ouro
            itens_no_nivel += len(saque.itens)
            encontros_no_nivel += 1
            if total % passo_a_cada == 0:
                xp += motor.xp_do_nivel(nivel, capitulo.XP_PASSO_FRACAO)
            # A cada arco (~8 encontros) a recompensa de arco e o XP de fim de arco.
            if total % 8 == 0:
                arco = recompensa_arco(nivel, rng)
                ouro_no_nivel += arco.ouro
                itens_no_nivel += len(arco.itens)
                xp += motor.xp_do_nivel(nivel, living_world.XP_ARCO_FRACAO)
            alvo = _proximo_xp(nivel)
            if alvo is not None and xp >= alvo:
                pn = por_nivel[nivel]
                pn.encontros.append(encontros_no_nivel)
                pn.ouro.append(ouro_no_nivel)
                pn.itens.append(itens_no_nivel)
                nivel += 1
                encontros_no_nivel = ouro_no_nivel = itens_no_nivel = 0
            elif alvo is None:
                pos_max += 1
                if pos_max >= ENCONTROS_POS_MAX:
                    pn = por_nivel[nivel]
                    pn.encontros.append(encontros_no_nivel)
                    pn.ouro.append(ouro_no_nivel)
                    pn.itens.append(itens_no_nivel)
                    break
    return por_nivel


def _media(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def relatorio(por_nivel: dict[int, Nivel], campanhas: int, passo_a_cada: int) -> str:
    linhas = [
        f"# Simulação de campanha ({campanhas} campanhas, 1 passo de trilha a cada {passo_a_cada} encontros)\n",
        "| Nível | Encontros p/ subir | Ouro ganho | Itens ganhos | Arquétipos distintos | Mais frequente (% dos encontros) |",  # noqa: E501
        "|---|---|---|---|---|---|",
    ]
    for n, d in por_nivel.items():
        total = sum(d.vistos.values())
        top = d.vistos.most_common(1)
        topo = f"{top[0][0]} ({100 * top[0][1] / total:.0f}%)" if top and total else "-"
        rotulo = f"{n}+ (teto, {ENCONTROS_POS_MAX} enc.)" if n == NIVEL_MAX else str(n)
        linhas.append(
            f"| {rotulo} | {_media(d.encontros):.1f} | {_media(d.ouro):.0f} | {_media(d.itens):.1f} | {len(d.vistos)} | {topo} |"  # noqa: E501
        )
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campanhas", type=int, default=200)
    parser.add_argument("--passo-a-cada", type=int, default=3)
    parser.add_argument("--semente", type=int, default=0)
    args = parser.parse_args()
    print(relatorio(simular(args.campanhas, args.passo_a_cada, args.semente), args.campanhas, args.passo_a_cada))


if __name__ == "__main__":
    main()
