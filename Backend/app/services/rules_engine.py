"""Regras determinísticas de D&D 5e — zero I/O, zero LLM.

O motor de combate de verdade (dano, iniciativa, testes de morte) é escopo
da Etapa 3 ("O Juiz"). Por ora isto reúne o que api.py já calculava sem
depender de rede ou banco: modificador de atributo, rolagem de dado, e a
validação de point-buy usada por domain/character.py."""

import random

ATRIBUTOS_VALIDOS = {"forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"}
CUSTO_PONTOS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
PONTOS_DISPONIVEIS = 27


def calcular_modificador(valor: int) -> int:
    return (valor - 10) // 2


def rolar_dado(expressao: str) -> int:
    """Aceita "NdF" ou "NdF+M". Entrada inválida devolve 0 em silêncio —
    bug conhecido (PLANO_MESTRE.md §2.2); a correção (levantar exceção)
    é escopo da Etapa 3."""
    try:
        dados, mod = expressao.split("+") if "+" in expressao else (expressao, 0)
        qtd, faces = map(int, dados.split("d"))
        return sum(random.randint(1, faces) for _ in range(qtd)) + int(mod)
    except ValueError:
        return 0


def validar_point_buy(valores: dict[str, int]) -> None:
    """Levanta ValueError se `valores` não é uma distribuição válida de
    point-buy de 27 pontos entre os seis atributos de D&D 5e."""
    if set(valores.keys()) != ATRIBUTOS_VALIDOS:
        raise ValueError(f"atributos precisa ter exatamente as chaves {sorted(ATRIBUTOS_VALIDOS)}")
    custo_total = 0
    for attr, valor in valores.items():
        if valor not in CUSTO_PONTOS:
            raise ValueError(f"{attr}={valor} está fora do intervalo de point-buy (8 a 15)")
        custo_total += CUSTO_PONTOS[valor]
    if custo_total > PONTOS_DISPONIVEIS:
        raise ValueError(f"point-buy gastaria {custo_total} pontos; o limite é {PONTOS_DISPONIVEIS}")
