"""
Caracteriza o comportamento ATUAL de api.py:rolar_dado e
api.py:calcular_modificador — inclusive o bug conhecido.

Estes testes existem para dar uma base estável antes de qualquer
refatoração (ver PLANO_MESTRE.md, Etapa 0: "provar que roda" antes de
"consertar"). A correção de rolar_dado — levantar exceção em vez de
devolver 0 — é escopo da Etapa 3 ("O juiz"). Quando ela chegar,
test_entrada_invalida_devolve_zero_em_silencio vai quebrar de
propósito: é o sinal para atualizá-lo.
"""

import pytest

from api import calcular_modificador, rolar_dado


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
        Bug conhecido (ver PLANO_MESTRE.md §2.2, item de gravidade
        média): o `except:` nu em rolar_dado engole qualquer erro de
        parsing. Um "1d" digitado errado em vez de "1d20" vira 0 de
        dano sem aviso nenhum — não é uma exceção corrigível, é uma
        rolagem que nunca aconteceu.
        """
        assert rolar_dado(expressao) == 0
