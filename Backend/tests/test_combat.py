"""Testa app/services/combat.py — o orquestrador que liga o bestiário real
(data/monsters.json) à resolução determinística do juiz. Estes testes usam
o `random.Random` com semente/sequência fixa: o mesmo padrão de
test_rules_engine.py, para que "um goblin te mata" seja reproduzível."""

from app.domain.state import CombatState, Inimigo
from app.services import combat
from tests.helpers import RngFixo

ATRIBUTOS_HEROI = {
    "forca": 14, "destreza": 12, "constituicao": 13,
    "inteligencia": 10, "sabedoria": 10, "carisma": 8,
}


class TestEscolherArma:
    def test_usa_a_arma_proposta_se_ela_existir_na_mochila(self):
        nome, dados = combat.escolher_arma(["Cimitarra", "Mochila"], "Cimitarra")
        assert nome == "Cimitarra"
        assert dados["dano"] == "1d6"

    def test_ignora_proposta_que_nao_esta_na_mochila(self):
        # "Machado Grande" existe no arsenal, mas não foi levado.
        nome, _ = combat.escolher_arma(["Cimitarra"], "Machado Grande")
        assert nome == "Cimitarra"

    def test_cai_para_desarmado_sem_nenhuma_arma_reconhecida(self):
        nome, dados = combat.escolher_arma(["Mochila", "Tocha"], None)
        assert nome == combat.NOME_ARMA_DESARMADA
        assert dados["dano"] == "1d1"


class TestIniciarCombate:
    def test_spawna_monstro_real_do_bestiario_nao_generico(self):
        # Iniciativa: herói primeiro (nunca é consultada pois só há 1 valor
        # de dado no rng — o goblin não ultrapassa o herói).
        c_state, eventos, dano_surpresa = combat.iniciar_combate(
            ["Goblin"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([10, 1])
        )
        assert c_state.ativo is True
        assert len(c_state.inimigos) == 1
        goblin = c_state.inimigos[0]
        assert goblin.nome == "Goblin"
        assert goblin.hp == 7 and goblin.max_hp == 7 and goblin.ca == 15
        assert goblin.bonus_ataque == 4
        assert goblin.dano_dado == "1d6+2"
        assert dano_surpresa == 0
        assert any("Goblin" in e for e in eventos)

    def test_nome_desconhecido_cai_para_monstro_de_nivel_1_sorteado(self):
        c_state, _, _ = combat.iniciar_combate(
            ["Dragão Ancião Inexistente"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([10, 1])
        )
        assert c_state.ativo is True
        assert len(c_state.inimigos) == 1
        assert c_state.inimigos[0].nome != "Dragão Ancião Inexistente"

    def test_inimigo_mais_rapido_ataca_de_surpresa(self):
        # Iniciativa do herói: 1+1(dex)=2. Iniciativa do goblin: 20+2(dex)=22.
        # Ataque de surpresa do goblin: d20=15 -> 15+4=19 >= CA 10 -> acerta.
        # Dano: 1d6+2 com d6=4 -> 6.
        c_state, eventos, dano_surpresa = combat.iniciar_combate(
            ["Goblin"], ATRIBUTOS_HEROI, ca_heroi=10, rng=RngFixo([1, 20, 15, 4])
        )
        assert dano_surpresa == 6
        assert any("surpresa" in e for e in eventos)

    def test_ordem_de_iniciativa_e_guardada_do_maior_pro_menor(self):
        # Herói: d20=20+1(dex)=21. Goblin(idx 0): d20=3+2(dex)=5. Lobo(idx 1): d20=10+2(dex)=12.
        # Ninguém supera o herói -> sem rolagem de ataque de surpresa, só 3 valores no rng.
        c_state, _, dano_surpresa = combat.iniciar_combate(
            ["Goblin", "Lobo"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([20, 3, 10])
        )
        assert dano_surpresa == 0
        # -1 é o herói; 1 (Lobo, iniciativa 12) vem antes de 0 (Goblin, iniciativa 5).
        assert c_state.ordem_iniciativa == [-1, 1, 0]
        assert c_state.turno_atual == 0

    def test_evento_de_surpresa_carrega_dados_estruturados(self):
        c_state, eventos, _ = combat.iniciar_combate(
            ["Goblin"], ATRIBUTOS_HEROI, ca_heroi=10, rng=RngFixo([1, 20, 15, 4])
        )
        evento_surpresa = next(e for e in eventos if "surpresa" in e)
        assert evento_surpresa.dados.tipo == "ataque"
        assert evento_surpresa.dados.quem == "Goblin"
        assert evento_surpresa.dados.sucesso is True
        assert evento_surpresa.dados.dano == 6


class TestTurnoInimigos:
    def _goblin(self) -> Inimigo:
        return Inimigo(nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra")

    def _lobo(self) -> Inimigo:
        return Inimigo(nome="Lobo", hp=11, max_hp=11, ca=13, bonus_ataque=4, dano_dado="2d4+2", nome_ataque="Mordida")

    def test_ataca_na_ordem_de_iniciativa_nao_na_ordem_de_spawn(self):
        # ordem_iniciativa manda o Lobo (índice 1) atacar antes do Goblin
        # (índice 0), mesmo com o Goblin vindo primeiro em `inimigos`.
        c_state = CombatState(
            ativo=True, inimigos=[self._goblin(), self._lobo()], ordem_iniciativa=[1, -1, 0]
        )
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([1, 1]))  # ambos erram
        assert "Lobo" in eventos[0]
        assert "Goblin" in eventos[1]

    def test_sem_ordem_calculada_cai_para_ordem_de_spawn(self):
        # CombatState montado à mão (sem passar por iniciar_combate) não tem
        # ordem_iniciativa — não pode quebrar quem já fazia isso antes da Etapa 7.
        c_state = CombatState(ativo=True, inimigos=[self._goblin(), self._lobo()])
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([1, 1]))
        assert "Goblin" in eventos[0]
        assert "Lobo" in eventos[1]

    def test_inimigo_morto_e_pulado_mesmo_na_ordem(self):
        goblin_morto = self._goblin()
        goblin_morto.hp = 0
        c_state = CombatState(ativo=True, inimigos=[goblin_morto, self._lobo()], ordem_iniciativa=[0, -1, 1])
        eventos, dano = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([1]))
        assert len(eventos) == 1
        assert "Lobo" in eventos[0]


class TestTurnoJogador:
    def _inimigo(self, hp=7, ca=15) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=ca,
            bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra",
        )

    def test_ataque_certeiro_reduz_hp_do_alvo(self):
        c_state = CombatState(ativo=True, inimigos=[self._inimigo()])
        # bônus do herói: proficiência 2 + mod força (14 -> +2) = 4. d20=15 -> 19 >= CA 15 -> acerta.
        eventos = combat.turno_jogador(
            c_state, ATRIBUTOS_HEROI, ["Cimitarra"], "Cimitarra", "Goblin", rng=RngFixo([15, 4])
        )
        assert c_state.inimigos[0].hp == 1  # 7 - (1d6+2 com d6=4 -> 6)
        assert "ACERTO" in eventos[0]

    def test_inimigo_morto_gera_evento_proprio(self):
        c_state = CombatState(ativo=True, inimigos=[self._inimigo(hp=1)])
        eventos = combat.turno_jogador(
            c_state, ATRIBUTOS_HEROI, ["Cimitarra"], "Cimitarra", "Goblin", rng=RngFixo([15, 4])
        )
        assert c_state.inimigos[0].hp == 0
        assert any("cai morto" in e for e in eventos)

    def test_alvo_inexistente_cai_para_primeiro_inimigo_vivo(self):
        c_state = CombatState(ativo=True, inimigos=[self._inimigo()])
        eventos = combat.turno_jogador(
            c_state, ATRIBUTOS_HEROI, ["Cimitarra"], "Cimitarra", "Alvo Que Não Existe", rng=RngFixo([15, 4])
        )
        assert "Goblin" in eventos[0]

    def test_ataque_errado_nao_muda_hp(self):
        c_state = CombatState(ativo=True, inimigos=[self._inimigo()])
        eventos = combat.turno_jogador(
            c_state, ATRIBUTOS_HEROI, ["Cimitarra"], "Cimitarra", "Goblin", rng=RngFixo([1])
        )
        assert c_state.inimigos[0].hp == 7
        assert "ERROU" in eventos[0]


class TestResolverTurno:
    def test_vitoria_quando_todos_os_inimigos_morrem(self):
        inimigo = Inimigo(
            nome="Goblin", hp=1, max_hp=7, ca=5,
            bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra",
        )
        c_state = CombatState(ativo=True, inimigos=[inimigo])
        hp_novo, eventos = combat.resolver_turno(
            c_state, hp_atual=10, ca_heroi=15, atributos_heroi=ATRIBUTOS_HEROI,
            inventario=["Cimitarra"], comando={"tipo": "atacar", "arma": "Cimitarra", "alvo": "Goblin"},
            rng=RngFixo([15, 4]),
        )
        assert c_state.ativo is False
        assert c_state.resultado == "vitoria"
        assert hp_novo == 10  # inimigo morto não ataca de volta
        assert any("vencido" in e for e in eventos)

    def test_derrota_apos_tres_falhas_de_morte(self):
        c_state = CombatState(ativo=True, inimigos=[], sucessos_morte=0, falhas_morte=2)
        hp_novo, eventos = combat.resolver_turno(
            c_state, hp_atual=0, ca_heroi=15, atributos_heroi=ATRIBUTOS_HEROI,
            inventario=[], comando={}, rng=RngFixo([5]),  # 5 -> falha
        )
        assert c_state.ativo is False
        assert c_state.resultado == "morte"
        assert hp_novo == 0
        assert any("fim da jornada" in e for e in eventos)

    def test_comando_sem_atacar_pula_o_turno_do_jogador(self):
        inimigo = Inimigo(
            nome="Goblin", hp=7, max_hp=7, ca=15,
            bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra",
        )
        c_state = CombatState(ativo=True, inimigos=[inimigo])
        hp_novo, eventos = combat.resolver_turno(
            c_state, hp_atual=10, ca_heroi=15, atributos_heroi=ATRIBUTOS_HEROI,
            inventario=[], comando={"tipo": "fugir"}, rng=RngFixo([1]),  # goblin erra o contra-ataque
        )
        assert c_state.inimigos[0].hp == 7  # ninguém atacou o goblin
        assert "hesita" in eventos[0]
