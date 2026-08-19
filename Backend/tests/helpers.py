"""`RngFixo` vivia duplicado em test_rules_engine.py e test_combat.py desde a
Etapa 3 — um terceiro teste (test_tools.py, Etapa 4) precisando do mesmo
helper foi o sinal de parar de copiar e colar."""

import random


class RngFixo(random.Random):
    """Um `random.Random` cujas próximas N chamadas a randint() são
    conhecidas de antemão — é o que torna um sistema estocástico testável
    com um resultado exato, sem depender de sorte ou de rodar 200 vezes."""

    def __init__(self, valores: list[int]) -> None:
        super().__init__()
        self._valores = iter(valores)

    def randint(self, a: int, b: int) -> int:
        return next(self._valores)

    def choice(self, seq):  # usado pelo fallback de monstro aleatório
        return seq[0]
