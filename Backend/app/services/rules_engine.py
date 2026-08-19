"""Regras determinísticas de D&D 5e — zero I/O, zero LLM.

O motor de combate (dano, iniciativa, testes de morte) chegou na Etapa 3
("O Juiz", ADR-0006): o LLM (services/narrator.py) não arbitra mais nada
disso — ele propõe alvo e arma, este módulo decide acerto, dano e HP.

Toda função aleatória aceita um `rng: random.Random` opcional (default: o
gerador global do módulo `random`). Isso é o que torna um sistema estocástico
testável: os testes passam um `random.Random` com semente fixa e conferem um
resultado exato, sem flakiness."""

import random
import re as _re
from dataclasses import dataclass
from typing import Literal

ATRIBUTOS_VALIDOS = {"forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"}
CUSTO_PONTOS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
PONTOS_DISPONIVEIS = 27

# Nível 1 fixo — todo personagem tem o mesmo bônus de proficiência até a
# progressão de nível chegar (Etapa 7, XP e nível).
BONUS_PROFICIENCIA = 2

_PADRAO_DADO = _re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")
_PADRAO_ATAQUE_MONSTRO = _re.compile(r"^(.*?)\s*\(([+-]\d+)\s*para acertar,\s*([^)]+?)\s*dano\)$")


def calcular_modificador(valor: int) -> int:
    return (valor - 10) // 2


def _parse_dado(expressao: str) -> tuple[int, int, int]:
    m = _PADRAO_DADO.match(expressao.strip())
    if not m:
        raise ValueError(f"'{expressao}' não é uma expressão de dado válida (ex: '1d20', '2d6+3').")
    qtd, faces, mod = m.groups()
    return int(qtd), int(faces), int(mod) if mod else 0


def rolar_dado(expressao: str, rng: random.Random | None = None) -> int:
    """Aceita "NdF" ou "NdF±M" (ex: "1d20", "2d6+3"). Levanta ValueError em
    entrada inválida — até a Etapa 2 isso devolvia 0 em silêncio
    (PLANO_MESTRE.md §2.2); a correção é o próprio ponto desta etapa."""
    dado = rng or random
    qtd, faces, mod = _parse_dado(expressao)
    return sum(dado.randint(1, faces) for _ in range(qtd)) + mod


def calcular_dano(dado_dano: str, critico: bool = False, rng: random.Random | None = None) -> int:
    """Dano de uma arma ou ataque. Um crítico dobra os DADOS rolados, não o
    modificador — é a regra do livro, não "dobra o total"."""
    dado = rng or random
    qtd, faces, mod = _parse_dado(dado_dano)
    if critico:
        qtd *= 2
    return sum(dado.randint(1, faces) for _ in range(qtd)) + mod


@dataclass
class ResultadoAtaque:
    rolagem: int
    bonus: int
    total: int
    ca_alvo: int
    critico: bool
    falha_critica: bool
    acerto: bool


def resolver_ataque(bonus_ataque: int, ca_alvo: int, rng: random.Random | None = None) -> ResultadoAtaque:
    """d20 + bônus contra a CA do alvo. Natural 20 sempre acerta (e é
    crítico); natural 1 sempre erra, mesmo que o total bata a CA."""
    dado = rng or random
    rolagem = dado.randint(1, 20)
    total = rolagem + bonus_ataque
    critico = rolagem == 20
    falha_critica = rolagem == 1
    acerto = critico or (not falha_critica and total >= ca_alvo)
    return ResultadoAtaque(rolagem, bonus_ataque, total, ca_alvo, critico, falha_critica, acerto)


def rolar_iniciativa(mod_destreza: int, rng: random.Random | None = None) -> int:
    dado = rng or random
    return dado.randint(1, 20) + mod_destreza


@dataclass
class ResultadoTeste:
    rolagem: int
    bonus: int
    total: int
    cd: int
    sucesso: bool


def resolver_teste_atributo(modificador: int, cd: int, rng: random.Random | None = None) -> ResultadoTeste:
    """d20 + modificador de atributo contra uma Classe de Dificuldade — a
    forma genérica de teste (furtividade, persuasão, percepção...) que a
    Etapa 3 previu em `PLANO_MESTRE.md` mas nunca chegou a escrever: só
    ataque (`resolver_ataque`) e teste de morte (`rolar_teste_morte`) tinham
    resolução própria até a Etapa 4 precisar de uma ferramenta `rolar_teste`
    genérica para o modelo chamar."""
    dado = rng or random
    rolagem = dado.randint(1, 20)
    total = rolagem + modificador
    return ResultadoTeste(rolagem, modificador, total, cd, sucesso=total >= cd)


@dataclass
class ResultadoMorte:
    rolagem: int
    resultado: Literal["sucesso", "falha", "estabilizado_critico", "falha_critica"]


def rolar_teste_morte(rng: random.Random | None = None) -> ResultadoMorte:
    """Teste de resistência contra a morte: o herói está a 0 PV. Natural 1
    conta como duas falhas; natural 20 recupera 1 PV na hora e acaba o
    teste; 10-19 é sucesso; o resto é falha. Três falhas = morte, três
    sucessos = estabilizado (ver services/combat.py)."""
    dado = rng or random
    rolagem = dado.randint(1, 20)
    if rolagem == 1:
        resultado: Literal["sucesso", "falha", "estabilizado_critico", "falha_critica"] = "falha_critica"
    elif rolagem == 20:
        resultado = "estabilizado_critico"
    elif rolagem >= 10:
        resultado = "sucesso"
    else:
        resultado = "falha"
    return ResultadoMorte(rolagem, resultado)


def parse_ataque_monstro(texto: str) -> tuple[str, int, str]:
    """Extrai (nome_da_arma, bônus_de_ataque, dado_de_dano) do formato usado
    em data/monsters.json: "Cimitarra (+4 para acertar, 1d6+2 dano)"."""
    m = _PADRAO_ATAQUE_MONSTRO.match(texto.strip())
    if not m:
        raise ValueError(f"'{texto}' não está no formato esperado de ataque de monstro.")
    nome, bonus, dano = m.groups()
    return nome, int(bonus), dano.strip()


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
