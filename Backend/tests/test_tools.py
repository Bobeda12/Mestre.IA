"""Testa app/services/tools.py — cada ferramenta que o modelo pode chamar
(Etapa 4, ADR-0007), isolada do loop de agente e da API da Groq. Mesmo
padrão de `random.Random` com sequência fixa de test_combat.py/
test_rules_engine.py."""

from app.domain.state import CombatState, Inimigo, WorldState
from app.infra.db import Personagem
from app.services.tools import ToolExecutor
from tests.helpers import RngFixo

ATRIBUTOS_HEROI = {
    "forca": 14, "destreza": 12, "constituicao": 13,
    "inteligencia": 10, "sabedoria": 10, "carisma": 8,
}


def _heroi(**overrides) -> Personagem:
    base = dict(
        nome="TesteFerramentas",
        classe="Guerreiro",
        hp_atual=10,
        hp_max=10,
        defesa=15,
        ouro=10,
        nivel=1,
        xp=0,
        atributos=dict(ATRIBUTOS_HEROI),
        inventario=["Cimitarra"],
        reputacao_npcs={},
    )
    base.update(overrides)
    return Personagem(**base)


def _executor(heroi=None, c_state=None, w_state=None, rng=None) -> ToolExecutor:
    return ToolExecutor(
        heroi or _heroi(),
        c_state or CombatState(),
        w_state or WorldState(local="Vila de Phandalin", clima="Ensolarado"),
        rng=rng,
    )


class TestRolarTeste:
    def test_atributo_invalido_e_rejeitado(self):
        resultado = _executor().rolar_teste("voar", 10)
        assert "erro" in resultado

    def test_sucesso_soma_modificador_certo(self):
        # destreza 12 -> mod +1. d20=14 -> total 15 >= CD 15.
        resultado = _executor(rng=RngFixo([14])).rolar_teste("destreza", 15)
        assert resultado["sucesso"] is True
        assert resultado["total"] == 15

    def test_dados_estruturados_mostram_de_onde_vem_o_bonus(self):
        # Etapa 11 (B-8): o card de rolagem precisa saber QUAL atributo
        # gerou o bônus, não só o número somado.
        executor = _executor(rng=RngFixo([14]))
        executor.rolar_teste("destreza", 15)
        [evento] = executor.eventos
        assert evento.dados.atributo == "destreza"
        assert evento.dados.partes_bonus == [{"rotulo": "Destreza", "valor": 1}]


class TestAtacar:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).atacar("Goblin", "Cimitarra")
        assert "erro" in resultado

    def test_ataque_certeiro_reduz_hp_e_libera_contra_ataque(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4, 1]))
        # bônus herói: proficiência 2 + força(+2) = 4. d20=15 -> 19 >= CA 15 -> acerta, dano 1d6=4+2=6.
        # goblin sobrevive (7-6=1) e contra-ataca: d20=1 -> erra.
        resultado = executor.atacar("Goblin", "Cimitarra")
        assert c_state.inimigos[0].hp == 1
        assert resultado["dano_recebido"] == 0
        assert any("ACERTO" in e for e in executor.eventos)

    def test_dados_estruturados_mostram_arma_e_atributo_do_ataque(self):
        # Etapa 11 (B-8): Cimitarra é "Sutil" — força(+2) vence destreza(+1)
        # nesta ficha, então o card precisa apontar força, não destreza.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4, 1]))
        executor.atacar("Goblin", "Cimitarra")
        [evento_ataque, _contra_ataque] = executor.eventos
        assert evento_ataque.dados.arma == "Cimitarra"
        assert evento_ataque.dados.atributo == "forca"
        assert evento_ataque.dados.partes_bonus == [
            {"rotulo": "Força", "valor": 2},
            {"rotulo": "Proficiência", "valor": 2},
        ]

    def test_vitoria_encerra_o_combate(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4]))
        resultado = executor.atacar("Goblin", "Cimitarra")
        assert resultado["resultado"] == "vitoria"
        assert c_state.ativo is False
        assert c_state.resultado == "vitoria"

    def test_vitoria_concede_xp_do_bestiario(self):
        # Goblin vale 50 XP (data/monsters.json) — não sobe de nível (limiar do 2 é 300).
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)])
        heroi = _heroi(xp=0, nivel=1)
        executor = _executor(heroi=heroi, c_state=c_state, rng=RngFixo([15, 4]))
        resultado = executor.atacar("Goblin", "Cimitarra")
        assert resultado["xp_ganho"] == 50
        assert resultado["xp_total"] == 50
        assert heroi.xp == 50
        assert heroi.nivel == 1
        assert any("XP" in e for e in executor.eventos)

    def test_xp_suficiente_sobe_de_nivel_e_aumenta_hp_max(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)])
        heroi = _heroi(xp=250, nivel=1, hp_max=10, hp_atual=10, classe="Guerreiro")
        # ataque: d20=15, dano d6=4. Subida de nível: 1d10 (dado_vida do Guerreiro) = 7.
        # mod constituição 13 -> +1. hp_ganho = 7+1 = 8.
        executor = _executor(heroi=heroi, c_state=c_state, rng=RngFixo([15, 4, 7]))
        resultado = executor.atacar("Goblin", "Cimitarra")
        assert resultado["xp_total"] == 300  # 250 + 50 do Goblin
        assert resultado["nivel"] == 2
        assert heroi.nivel == 2
        assert heroi.hp_max == 18
        assert heroi.hp_atual == 18
        assert any("nível 2" in e for e in executor.eventos)


class TestAplicarDano:
    def test_dano_no_heroi(self):
        heroi = _heroi(hp_atual=10, hp_max=10)
        executor = _executor(heroi=heroi, rng=RngFixo([4]))
        resultado = executor.aplicar_dano("heroi", "1d6", motivo="queda")
        assert resultado["dano"] == 4
        assert heroi.hp_atual == 6

    def test_alvo_invalido_e_rejeitado(self):
        resultado = _executor(rng=RngFixo([4])).aplicar_dano("Fantasma Que Não Existe", "1d6")
        assert "erro" in resultado

    def test_dano_em_inimigo_vivo(self):
        goblin = Inimigo(
            nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )
        c_state = CombatState(ativo=True, inimigos=[goblin])
        executor = _executor(c_state=c_state, rng=RngFixo([5]))
        resultado = executor.aplicar_dano("Goblin", "1d6", motivo="armadilha")
        assert resultado["dano"] == 5
        assert goblin.hp == 2

    def test_morte_do_inimigo_vira_evento_estruturado(self):
        # Etapa 10 (A-7) — "💀 X cai morto" deixa de ser só texto solto:
        # carrega um EventoStatus, mesmo padrão de card de DadosRolagem.
        goblin = Inimigo(
            nome="Goblin", hp=5, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )
        c_state = CombatState(ativo=True, inimigos=[goblin])
        executor = _executor(c_state=c_state, rng=RngFixo([6]))
        executor.aplicar_dano("Goblin", "1d6", motivo="armadilha")
        assert goblin.hp == 0
        [_evento_dano, evento_morte] = executor.eventos
        assert evento_morte.dados.tipo == "morte_inimigo"
        assert evento_morte.dados.quem == "Goblin"


class TestMover:
    def test_destino_valido_atualiza_local(self):
        w_state = WorldState(local="Vila de Phandalin", clima="Ensolarado")
        executor = _executor(w_state=w_state)
        resultado = executor.mover("Floresta das Sombras")
        assert resultado["local"] == "Floresta das Sombras"
        assert w_state.local == "Floresta das Sombras"

    def test_destino_desconhecido_devolve_locais_validos(self):
        resultado = _executor().mover("Cidade Que Não Existe")
        assert "erro" in resultado
        assert "Vila de Phandalin" in resultado["locais_validos"]

    def test_nao_pode_mover_durante_combate(self):
        resultado = _executor(c_state=CombatState(ativo=True)).mover("Floresta das Sombras")
        assert "erro" in resultado


class TestConsultarRegra:
    def test_encontra_trecho_na_biblia(self):
        resultado = _executor().consultar_regra("ação ardilosa")
        assert resultado["encontrado"] is True
        assert any("Ardilosa" in t for t in resultado["trechos"])

    def test_termo_ausente_nao_encontra(self):
        resultado = _executor().consultar_regra("xenomorfo intergalático")
        assert resultado["encontrado"] is False


class TestUsarItem:
    def test_item_fora_do_inventario_e_rejeitado(self):
        resultado = _executor().usar_item("Poção de Cura")
        assert "erro" in resultado

    def test_pocao_de_cura_recupera_hp_e_e_consumida(self):
        heroi = _heroi(hp_atual=5, hp_max=10, inventario=["Poção de Cura"])
        executor = _executor(heroi=heroi, rng=RngFixo([3, 3]))
        resultado = executor.usar_item("Poção de Cura")
        assert resultado["cura"] == 8  # 2d4+2 com d4=3,3
        assert heroi.hp_atual == 10  # capado no hp_max
        assert "Poção de Cura" not in heroi.inventario

    def test_pocao_de_cura_vira_evento_estruturado(self):
        # Etapa 10 (A-7) — deixa de ser só "🧪 ..." em texto solto.
        heroi = _heroi(hp_atual=5, hp_max=10, inventario=["Poção de Cura"])
        executor = _executor(heroi=heroi, rng=RngFixo([3, 3]))
        executor.usar_item("Poção de Cura")
        [evento] = executor.eventos
        assert evento.dados.tipo == "cura"
        assert evento.dados.quem == "heroi"
        assert evento.dados.valor == 8

    def test_item_sem_efeito_conhecido_so_confirma_posse(self):
        heroi = _heroi(inventario=["Tocha"])
        resultado = _executor(heroi=heroi).usar_item("Tocha")
        assert resultado["usado"] is True
        assert "Tocha" in heroi.inventario  # não é consumível, não some


class TestDarItem:
    def test_adiciona_ao_inventario(self):
        heroi = _heroi(inventario=["Mochila"])
        resultado = _executor(heroi=heroi).dar_item("Poção de Cura")
        assert resultado["inventario"] == ["Mochila", "Poção de Cura"]
        assert heroi.inventario == ["Mochila", "Poção de Cura"]


class TestGastarOuro:
    def test_saldo_insuficiente_e_rejeitado(self):
        heroi = _heroi(ouro=5)
        resultado = _executor(heroi=heroi).gastar_ouro(10)
        assert "erro" in resultado
        assert heroi.ouro == 5

    def test_saldo_suficiente_debita(self):
        heroi = _heroi(ouro=10)
        resultado = _executor(heroi=heroi).gastar_ouro(4)
        assert resultado["ouro_restante"] == 6
        assert heroi.ouro == 6


class TestAjustarReputacaoNpc:
    def test_primeira_interacao_parte_de_zero(self):
        heroi = _heroi()
        resultado = _executor(heroi=heroi).ajustar_reputacao_npc("Taverneiro Gundren", -5, "insultou o taverneiro")
        assert resultado["reputacao"] == -5
        assert heroi.reputacao_npcs == {"Taverneiro Gundren": -5}

    def test_delta_por_chamada_e_clampado(self):
        heroi = _heroi()
        resultado = _executor(heroi=heroi).ajustar_reputacao_npc("Ferreiro", 999, "presente generoso")
        assert resultado["reputacao"] == 10  # clamp de delta em +-10, não +999

    def test_valor_acumulado_e_clampado_no_total(self):
        heroi = _heroi(reputacao_npcs={"Ferreiro": 95})
        resultado = _executor(heroi=heroi).ajustar_reputacao_npc("Ferreiro", 10, "outro presente")
        assert resultado["reputacao"] == 100  # 95+10=105, clamp em 100

    def test_reputacoes_de_npcs_diferentes_nao_se_misturam(self):
        heroi = _heroi()
        executor = _executor(heroi=heroi)
        executor.ajustar_reputacao_npc("Taverneiro", -5, "rude")
        executor.ajustar_reputacao_npc("Ferreiro", 5, "gentil")
        assert heroi.reputacao_npcs == {"Taverneiro": -5, "Ferreiro": 5}


class TestIniciarCombate:
    def test_combate_ja_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=True)).iniciar_combate(["Goblin"])
        assert "erro" in resultado

    def test_monstro_real_do_bestiario(self):
        c_state = CombatState()
        executor = _executor(c_state=c_state, rng=RngFixo([10, 1]))
        resultado = executor.iniciar_combate(["Goblin"])
        assert resultado["inimigos"] == ["Goblin"]
        assert c_state.ativo is True
        assert c_state.inimigos[0].hp == 7

    def test_ordem_de_iniciativa_e_copiada_pro_c_state_do_executor(self):
        # Bug real (Etapa 7): `iniciar_combate` copiava só alguns campos de
        # `novo` pra `self.c_state` campo a campo, e `ordem_iniciativa`/
        # `turno_atual` (adicionados nesta etapa) ficaram de fora — o HUD
        # do frontend nunca via a ordem calculada. Achado ao vivo no
        # browser, não pelos testes (nenhum conferia esse campo até aqui).
        c_state = CombatState()
        executor = _executor(c_state=c_state, rng=RngFixo([10, 1]))
        executor.iniciar_combate(["Goblin"])
        assert c_state.ordem_iniciativa != []
        assert -1 in c_state.ordem_iniciativa  # o herói sempre entra na ordem


class TestExecutar:
    def test_ferramenta_inexistente_devolve_erro_sem_lancar(self):
        resultado, sucesso = _executor().executar("voar", "{}")
        assert sucesso is False
        assert "erro" in resultado

    def test_json_malformado_devolve_erro_sem_lancar(self):
        resultado, sucesso = _executor().executar("mover", "{destino:")
        assert sucesso is False
        assert "erro" in resultado

    def test_argumento_faltando_devolve_erro_sem_lancar(self):
        resultado, sucesso = _executor().executar("gastar_ouro", "{}")
        assert sucesso is False
        assert "erro" in resultado

    def test_chamada_valida_e_bem_sucedida(self):
        resultado, sucesso = _executor(rng=RngFixo([10])).executar("gastar_ouro", '{"qtd": 3}')
        assert sucesso is True
        assert resultado["ouro_restante"] == 7
