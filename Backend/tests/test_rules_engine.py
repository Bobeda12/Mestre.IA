"""Caracteriza o comportamento de app/services/rules_engine.py.

Estes testes existiam antes (Backend/tests/test_dados.py, importando de
`api`) e migraram para cá na Etapa 2, quando a lógica de regras foi
extraída para services/rules_engine.py. Na Etapa 3 ("O juiz"),
rolar_dado() passou a levantar ValueError em entrada inválida em vez de
devolver 0 em silêncio — exatamente como o diário da Etapa 2 previu.
"""

import pytest

from app.services.rules_engine import (
    NIVEL_MAXIMO,
    XP_POR_NIVEL,
    bonus_proficiencia,
    calcular_dano,
    calcular_modificador,
    desafio_sugerido,
    parse_ataque_monstro,
    resolver_ataque,
    resolver_teste_atributo,
    rolar_dado,
    rolar_iniciativa,
    rolar_teste_morte,
    subir_nivel,
    validar_point_buy,
    vantagem_por_traco,
)
from tests.helpers import RngFixo


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

    def test_sem_vantagem_roda_um_d20_so(self):
        resultado = resolver_ataque(bonus_ataque=4, ca_alvo=15, rng=RngFixo([12]))
        assert resultado.rolagem == 12
        assert resultado.d20_extra is None
        assert resultado.vantagem is None

    def test_vantagem_fica_com_o_maior_dos_dois_d20(self):
        resultado = resolver_ataque(bonus_ataque=4, ca_alvo=15, rng=RngFixo([7, 18]), vantagem=True)
        assert resultado.rolagem == 18
        assert resultado.d20_extra == 7
        assert resultado.vantagem is True

    def test_desvantagem_fica_com_o_menor_dos_dois_d20(self):
        resultado = resolver_ataque(bonus_ataque=4, ca_alvo=15, rng=RngFixo([7, 18]), vantagem=False)
        assert resultado.rolagem == 7
        assert resultado.d20_extra == 18
        assert resultado.vantagem is False


class TestRolarIniciativa:
    def test_soma_d20_ao_modificador_de_destreza(self):
        assert rolar_iniciativa(mod_destreza=3, rng=RngFixo([10])) == 13


class TestVantagemPorTraco:
    """Rodada de conserto (Parte 2, item H) — raça deixa de ser só +2 num
    atributo: um traço com o motivo certo concede vantagem de verdade."""

    def test_sem_motivo_nunca_concede_vantagem(self):
        assert vantagem_por_traco(["Resistência a Veneno"], False, None) is False
        assert vantagem_por_traco(["Resistência a Veneno"], False, "") is False

    def test_traco_presente_e_motivo_compativel_concede_vantagem(self):
        assert vantagem_por_traco(["Resistência a Veneno"], False, "resistir ao veneno da aranha") is True

    def test_traco_ausente_nao_concede_mesmo_com_motivo_compativel(self):
        assert vantagem_por_traco(["Sortudo"], False, "resistir ao veneno da aranha") is False

    def test_motivo_incompativel_nao_concede_mesmo_com_traco(self):
        assert vantagem_por_traco(["Resistência a Veneno"], False, "escalar o muro") is False

    def test_visao_no_escuro_concede_vantagem_em_percepcao_no_escuro(self):
        assert vantagem_por_traco([], True, "perceber a emboscada no escuro") is True

    def test_visao_no_escuro_nao_ajuda_fora_do_escuro(self):
        assert vantagem_por_traco([], True, "perceber a emboscada") is False

    def test_sem_visao_no_escuro_nao_ganha_o_bonus_de_escuridao(self):
        assert vantagem_por_traco([], False, "perceber algo no escuro") is False


class TestResolverTesteAtributo:
    def test_sucesso_quando_total_bate_a_cd(self):
        resultado = resolver_teste_atributo(modificador=2, cd=15, rng=RngFixo([13]))
        assert resultado.total == 15
        assert resultado.sucesso is True

    def test_falha_quando_total_nao_bate_a_cd(self):
        resultado = resolver_teste_atributo(modificador=2, cd=15, rng=RngFixo([5]))
        assert resultado.sucesso is False

    def test_nao_tem_regra_especial_para_natural_20_ou_1(self):
        # Diferente de resolver_ataque: teste de atributo não tem "sempre
        # acerta"/"sempre erra" no d20 — é só a soma contra a CD.
        assert resolver_teste_atributo(modificador=-10, cd=15, rng=RngFixo([20])).sucesso is False
        assert resolver_teste_atributo(modificador=99, cd=15, rng=RngFixo([1])).sucesso is True

    def test_vantagem_fica_com_o_maior_dos_dois_d20(self):
        resultado = resolver_teste_atributo(modificador=2, cd=15, rng=RngFixo([6, 14]), vantagem=True)
        assert resultado.rolagem == 14
        assert resultado.d20_extra == 6

    def test_desvantagem_fica_com_o_menor_dos_dois_d20(self):
        resultado = resolver_teste_atributo(modificador=2, cd=15, rng=RngFixo([6, 14]), vantagem=False)
        assert resultado.rolagem == 6
        assert resultado.d20_extra == 14


class TestDesafioSugerido:
    def test_nivel_1_so_sugere_banda_nivel_1(self):
        assert desafio_sugerido(1) == ["Nivel_1"]

    def test_nivel_5_sugere_nivel_4_e_chefe(self):
        assert desafio_sugerido(5) == ["Nivel_4", "Chefe"]

    def test_nivel_fora_do_intervalo_cai_para_a_banda_mais_proxima(self):
        assert desafio_sugerido(0) == desafio_sugerido(1)
        assert desafio_sugerido(99) == desafio_sugerido(NIVEL_MAXIMO)


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


class TestBonusProficiencia:
    @pytest.mark.parametrize("nivel,esperado", [(1, 2), (4, 2), (5, 3)])
    def test_tabela_srd(self, nivel, esperado):
        assert bonus_proficiencia(nivel) == esperado


class TestSubirNivel:
    def test_xp_insuficiente_nao_sobe(self):
        resultado = subir_nivel(xp_atual=299, nivel_atual=1, dado_vida=10, mod_constituicao=1)
        assert resultado.subiu is False
        assert resultado.nivel_novo == 1

    def test_xp_suficiente_sobe_um_nivel_e_rola_hp(self):
        assert XP_POR_NIVEL[2] == 300
        resultado = subir_nivel(
            xp_atual=300, nivel_atual=1, dado_vida=10, mod_constituicao=1, rng=RngFixo([6])
        )
        assert resultado.subiu is True
        assert resultado.nivel_novo == 2
        assert resultado.hp_ganho == 7  # 1d10 (rolou 6) + mod con 1

    def test_hp_ganho_nunca_fica_abaixo_de_um(self):
        resultado = subir_nivel(xp_atual=300, nivel_atual=1, dado_vida=6, mod_constituicao=-5, rng=RngFixo([1]))
        assert resultado.hp_ganho == 1

    def test_nivel_maximo_nao_sobe_mais(self):
        resultado = subir_nivel(xp_atual=999_999, nivel_atual=NIVEL_MAXIMO, dado_vida=10, mod_constituicao=0)
        assert resultado.subiu is False
        assert resultado.nivel_novo == NIVEL_MAXIMO


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
