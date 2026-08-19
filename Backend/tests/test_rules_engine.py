"""Caracteriza o comportamento de app/services/rules_engine.py — inclusive
o bug conhecido de rolar_dado.

Estes testes existiam antes (Backend/tests/test_dados.py, importando de
`api`) e migram aqui após a Etapa 2 extrair a lógica de regras para
services/rules_engine.py. A correção de rolar_dado — levantar exceção em
vez de devolver 0 — segue sendo escopo da Etapa 3 ("O juiz"). Quando ela
chegar, test_entrada_invalida_devolve_zero_em_silencio vai quebrar de
propósito: é o sinal para atualizá-lo.
"""

import pytest

from app.services.rules_engine import calcular_modificador, rolar_dado, validar_point_buy


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
    def test_entrada_invalida_devolve_zero_em_silencio(self, expressao):
        """
        Bug conhecido (PLANO_MESTRE.md §2.2, item de gravidade média): o
        `except:` engole qualquer erro de parsing. Um "1d" digitado errado
        em vez de "1d20" vira 0 de dano sem aviso nenhum — não é uma
        exceção corrigível, é uma rolagem que nunca aconteceu.
        """
        assert rolar_dado(expressao) == 0


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
