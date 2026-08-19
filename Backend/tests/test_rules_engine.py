"""Caracteriza o comportamento de app/services/rules_engine.py.

Estes testes existiam antes (Backend/tests/test_dados.py, importando de
`api`) e migraram para cá na Etapa 2, quando a lógica de regras foi
extraída para services/rules_engine.py. Na Etapa 3 ("O juiz"),
rolar_dado() passou a levantar ValueError em entrada inválida em vez de
devolver 0 em silêncio — exatamente como o diário da Etapa 2 previu.
"""

import random

import pytest

from app.services.rules_engine import (
    BONUS_PROFICIENCIA,
    calcular_dano,
    calcular_modificador,
    parse_ataque_monstro,
    resolver_ataque,
    rolar_dado,
    rolar_iniciativa,
    rolar_teste_morte,
    validar_point_buy,
)


class RngFixo(random.Random):
    """Um `random.Random` cujas próximas N chamadas a randint() são
    conhecidas de antemão — é o que torna um sistema estocástico testável
    com um resultado exato, sem depender de sorte ou de rodar 200 vezes."""

    def __init__(self, valores: list[int]) -> None:
        super().__init__()
        self._valores = iter(valores)

    def randint(self, a: int, b: int) -> int:
        return next(self._valores)


class TestCalcularModificador:
    @pytest.mark.parametrize(
        "valor,esperado",
        [
            (10, 0),
            (11, 0),
            (12, 1),
            (8, -1),
            (20, 5),
            (1, -5),
            (15, 2),
        ],
    )
    def test_formula_dnd_5e(self, valor, esperado):
        assert calcular_modificador(valor) == esperado


class TestRolarDado:
    def test_um_dado_fica_no_intervalo(self):
        for _ in range(200):
            assert 1 <= rolar_dado("1d20") <= 20

    def test_multiplos_dados_com_modificador(self):
        for _ in range(200):
            assert 5 <= rolar_dado("2d6+3") <= 15

    def test_multiplos_dados_sem_modificador(self):
        for _ in range(200):
            assert 3 <= rolar_dado("3d4") <= 12

    @pytest.mark.parametrize("expressao", ["lixo", "", "d20", "1d", "2x6"])
    def test_entrada_invalida_levanta_value_error(self, expressao):
        """Até a Etapa 2, isto devolvia 0 em silêncio (PLANO_MESTRE.md
        §2.2) — um "1d" digitado errado em vez de "1d20" virava dano zero
        sem aviso nenhum. Agora é uma exceção, não uma rolagem fantasma."""
        with pytest.raises(ValueError, match="não é uma expressão de dado válida"):
            rolar_dado(expressao)

    def test_semente_fixa_reproduz_o_mesmo_resultado(self):
        assert rolar_dado("2d6+3", RngFixo([4, 5])) == 12


class TestCalcularDano:
    def test_soma_dados_e_modificador(self):
        assert calcular_dano("1d6+2", rng=RngFixo([4])) == 6

    def test_critico_dobra_os_dados_nao_o_modificador(self):
        # 1d6+2 crítico -> 2d6+2, não (1d6+2)*2. Cada dado sai 4.
        assert calcular_dano("1d6+2", critico=True, rng=RngFixo([4, 4])) == 10


class TestResolverAtaque:
    def test_acerto_quando_total_bate_a_ca(self):
        resultado = resolver_ataque(bonus_ataque=4, ca_alvo=15, rng=RngFixo([12]))
        assert resultado.total == 16
        assert resultado.acerto is True
        assert resultado.critico is False

    def test_erro_quando_total_nao_bate_a_ca(self):
        resultado = resolver_ataque(bonus_ataque=4, ca_alvo=15, rng=RngFixo([5]))
        assert resultado.acerto is False

    def test_natural_20_sempre_acerta_e_e_critico(self):
        # bônus negativo enorme: sem a regra do natural 20, isto erraria.
        resultado = resolver_ataque(bonus_ataque=-10, ca_alvo=15, rng=RngFixo([20]))
        assert resultado.acerto is True
        assert resultado.critico is True

    def test_natural_1_sempre_erra_mesmo_com_bonus_enorme(self):
        resultado = resolver_ataque(bonus_ataque=99, ca_alvo=15, rng=RngFixo([1]))
        assert resultado.acerto is False
        assert resultado.falha_critica is True


class TestRolarIniciativa:
    def test_soma_d20_ao_modificador_de_destreza(self):
        assert rolar_iniciativa(mod_destreza=3, rng=RngFixo([10])) == 13


class TestRolarTesteMorte:
    @pytest.mark.parametrize(
        "rolagem,esperado",
        [
            (1, "falha_critica"), (5, "falha"), (9, "falha"),
            (10, "sucesso"), (19, "sucesso"), (20, "estabilizado_critico"),
        ],
    )
    def test_faixas_do_resultado(self, rolagem, esperado):
        assert rolar_teste_morte(RngFixo([rolagem])).resultado == esperado


class TestParseAtaqueMonstro:
    def test_extrai_nome_bonus_e_dado_de_dano(self):
        nome, bonus, dano = parse_ataque_monstro("Cimitarra (+4 para acertar, 1d6+2 dano)")
        assert (nome, bonus, dano) == ("Cimitarra", 4, "1d6+2")

    def test_formato_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="não está no formato esperado"):
            parse_ataque_monstro("Cimitarra ataca forte")


def test_bonus_proficiencia_e_fixo_no_nivel_1():
    # Nível 1 fixo até a Etapa 7 (XP e progressão) existir.
    assert BONUS_PROFICIENCIA == 2


class TestValidarPointBuy:
    """Antes da Etapa 2 isto só era testado indiretamente via HTTP
    (test_smoke.py). Aqui vira teste de unidade — zero I/O, sem subir
    o FastAPI inteiro — e conta para a meta de 60% de cobertura em
    app/services (PLANO_MESTRE.md, Etapa 2)."""

    def _atributos(self, **overrides):
        base = {
            "forca": 15, "destreza": 14, "constituicao": 13,
            "inteligencia": 12, "sabedoria": 10, "carisma": 8,
        }
        base.update(overrides)
        return base

    def test_distribuicao_valida_nao_levanta(self):
        # Todos em 8 (custo 0) -> bem abaixo do limite, só confere que uma
        # distribuição correta não levanta nada.
        validar_point_buy(self._atributos(
            forca=8, destreza=8, constituicao=8,
            inteligencia=8, sabedoria=8, carisma=8,
        ))

    def test_falta_de_atributo_e_rejeitada(self):
        valores = self._atributos()
        del valores["carisma"]
        with pytest.raises(ValueError, match="atributos precisa ter exatamente as chaves"):
            validar_point_buy(valores)

    def test_atributo_fora_do_intervalo_e_rejeitado(self):
        with pytest.raises(ValueError, match="fora do intervalo de point-buy"):
            validar_point_buy(self._atributos(forca=20))

    def test_custo_acima_do_limite_e_rejeitado(self):
        with pytest.raises(ValueError, match="o limite é 27"):
            validar_point_buy(self._atributos(
                forca=15, destreza=15, constituicao=15,
                inteligencia=15, sabedoria=15, carisma=15,
            ))

    def test_gasto_no_limite_exato_e_aceito(self):
        # 15/14/13/12/10/8 -> custo 9+7+5+4+2+0 = 27, exatamente o limite.
        validar_point_buy(self._atributos())
