"""Testa app/services/combat.py — o orquestrador que liga o bestiário real
(data/monsters.json) à resolução determinística do juiz. Estes testes usam
o `random.Random` com semente/sequência fixa: o mesmo padrão de
test_rules_engine.py, para que "um goblin te mata" seja reproduzível."""

from app.domain.state import Aliado, CombatState, Inimigo
from app.services import combat
from tests.helpers import RngFixo

ATRIBUTOS_HEROI = {
    "forca": 14, "destreza": 12, "constituicao": 13,
    "inteligencia": 10, "sabedoria": 10, "carisma": 8,
}


class _RngAlvo(RngFixo):
    """Fase 2 da revisão de gameplay — `RngFixo.choice()` sempre devolve o
    primeiro item da lista (bom pro fallback de monstro aleatório, ruim
    pra testar `combat._escolher_alvo`, que PRECISA poder escolher o
    aliado, não só o herói que vem primeiro em `candidatos`)."""

    def __init__(self, valores: list[int], escolha) -> None:
        super().__init__(valores)
        self._escolha = escolha

    def choice(self, seq):
        return self._escolha


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

    def test_comportamento_do_bestiario_e_copiado_pro_inimigo(self):
        # Fase 0 da revisão de gameplay (Etapa 12/13) — antes este campo era
        # lido de data/monsters.json e descartado; a IA de inimigo (Fase 1)
        # depende dele existir em `Inimigo` pra recuar/ganhar vantagem.
        c_state, _, _ = combat.iniciar_combate(["Goblin"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([10, 1]))
        assert c_state.inimigos[0].comportamento == "Covarde. Ataca e foge (Ação Ardilosa)."

    def test_nome_fora_do_bestiario_vira_pele_de_um_arquetipo_da_banda(self):
        # Rodada de conserto (Parte 2, item J) — "chega de goblins": um nome
        # que não bate no catálogo não é mais descartado. Vira o NOME
        # exibido, com a ficha de um arquétipo sorteado da banda de nível
        # do herói (nível 1 por padrão aqui) — `RngFixo.choice` sempre
        # devolve o primeiro candidato, que é "Goblin" (data/monsters.json
        # preserva a ordem de inserção).
        c_state, eventos, _ = combat.iniciar_combate(
            ["Batedor Rasgacouro"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([10, 1])
        )
        assert c_state.ativo is True
        assert len(c_state.inimigos) == 1
        inimigo = c_state.inimigos[0]
        assert inimigo.nome == "Batedor Rasgacouro"  # a pele: nome narrativo
        assert inimigo.hp == 7 and inimigo.ca == 15 and inimigo.bonus_ataque == 4  # a ficha: Goblin de verdade
        assert any("Batedor Rasgacouro" in e for e in eventos)

    def test_bestiario_vazio_nao_quebra_o_combate(self, monkeypatch):
        # O fallback original (monstro de Nível 1 sorteado quando nada
        # sobra) só sobrevive pra quando NENHUMA banda tem candidato —
        # cenário que só acontece com o catálogo vazio de propósito.
        from app.infra.data_manager import regras

        monkeypatch.setattr(regras, "get_monstros_por_banda", lambda banda: [])
        monkeypatch.setattr(regras, "get_monstros_nivel_1", lambda: [])
        c_state, eventos, _ = combat.iniciar_combate(
            ["Qualquer Coisa"], ATRIBUTOS_HEROI, ca_heroi=15, rng=RngFixo([])
        )
        assert c_state.inimigos == []
        assert "não iniciado" in eventos[0]

    # Ataque de surpresa e ordem de iniciativa saíram daqui: quem age antes
    # do herói é decidido pela fila de `services/turnos.py` (test_combate_v2).


class TestEscolherAlvo:
    def _goblin(self) -> Inimigo:
        return Inimigo(nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra")

    def _aliado(self, hp=10) -> Aliado:
        return Aliado(nome="Bob", hp=hp, max_hp=10, ca=13, bonus_ataque=3, dano_dado="1d6", nome_ataque="Adaga")

    def test_sem_aliados_alvo_e_sempre_o_heroi_sem_consumir_rng(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        # lista de rng vazia: qualquer randint()/choice() de verdade quebraria o teste.
        tipo, idx = combat._escolher_alvo(c_state, rng=RngFixo([]))
        assert (tipo, idx) == ("heroi", None)

    def test_aliado_morto_nao_e_candidato(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[self._aliado(hp=0)])
        tipo, idx = combat._escolher_alvo(c_state, rng=RngFixo([]))
        assert (tipo, idx) == ("heroi", None)

    def test_pode_escolher_o_aliado_vivo(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[self._aliado()])
        tipo, idx = combat._escolher_alvo(c_state, rng=_RngAlvo([], ("aliado", 0)))
        assert (tipo, idx) == ("aliado", 0)


class TestTurnoAliado:
    """Fase 3 da revisão de gameplay (ADR-0027) — o ataque de um aliado
    recrutado contra um inimigo, resolvido pelo motor generalizado."""

    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def _aliado(self) -> Aliado:
        return Aliado(nome="Bob", hp=10, max_hp=10, ca=12, bonus_ataque=2, dano_dado="1d6", nome_ataque="Adaga")

    def test_ataque_certeiro_reduz_hp_do_inimigo(self):
        # d20=15+2=17 >= CA 15 -> acerta. dano 1d6 com d6=4 -> 4.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        eventos = combat.turno_aliado(c_state, self._aliado(), "Goblin", rng=RngFixo([15, 4]))
        assert c_state.inimigos[0].hp == 3
        assert "Bob" in eventos[0]
        assert "ACERTO" in eventos[0]

    def test_inimigo_morto_gera_evento_proprio(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)])
        eventos = combat.turno_aliado(c_state, self._aliado(), "Goblin", rng=RngFixo([15, 4]))
        assert c_state.inimigos[0].hp == 0
        evento_morte = next(e for e in eventos if "cai morto" in e)
        assert evento_morte.dados.tipo == "morte_inimigo"

    def test_ataque_errado_nao_muda_hp(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        eventos = combat.turno_aliado(c_state, self._aliado(), "Goblin", rng=RngFixo([1]))
        assert c_state.inimigos[0].hp == 7
        assert "ERROU" in eventos[0]

    def test_sem_inimigos_vivos_nao_faz_nada(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=0)])
        eventos = combat.turno_aliado(c_state, self._aliado(), "Goblin", rng=RngFixo([]))
        assert eventos == []


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
        # Etapa 10 (A-7): esse evento carrega dado estruturado, não é só texto.
        evento_morte = next(e for e in eventos if "cai morto" in e)
        assert evento_morte.dados.tipo == "morte_inimigo"
        assert evento_morte.dados.quem == "Goblin"

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

    def test_vantagem_repassada_ao_motor_e_ao_card(self):
        # Fase 0 da revisão de gameplay — a plumbing de vantagem/desvantagem;
        # ainda não há ferramenta que a acione (isso é a Fase 1), mas o
        # parâmetro já precisa chegar até o `DadosRolagem` do card.
        c_state = CombatState(ativo=True, inimigos=[self._inimigo()])
        eventos = combat.turno_jogador(
            c_state, ATRIBUTOS_HEROI, ["Cimitarra"], "Cimitarra", "Goblin",
            rng=RngFixo([9, 15, 4]), vantagem=True,
        )
        assert eventos[0].dados.vantagem is True
        assert eventos[0].dados.d20_extra == 9
        assert eventos[0].dados.d20 == 15

