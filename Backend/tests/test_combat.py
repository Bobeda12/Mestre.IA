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


class TestComportamentoInimigo:
    """Fase 1 da revisão de gameplay — leitura por palavra-chave de
    `Inimigo.comportamento`, não IA de verdade (ver combat._comportamento_inimigo)."""

    def _kobold_solitario(self, hp=5) -> Inimigo:
        return Inimigo(
            nome="Kobold", hp=hp, max_hp=5, ca=12, bonus_ataque=4, dano_dado="1d4+2", nome_ataque="Adaga",
            comportamento="Ataca em grupo. Foge se estiver sozinho.",
        )

    def _lobo_matilha(self, hp=11) -> Inimigo:
        return Inimigo(
            nome="Lobo", hp=hp, max_hp=11, ca=13, bonus_ataque=4, dano_dado="2d4+2", nome_ataque="Mordida",
            comportamento="Alcatéia. Ganha vantagem se tiver aliado perto.",
        )

    def _aranha_ferida(self, hp=5) -> Inimigo:
        return Inimigo(
            nome="Aranha Gigante", hp=hp, max_hp=18, ca=14, bonus_ataque=5, dano_dado="2d6+3", nome_ataque="Mordida",
            comportamento="Emboscada. Ataca de surpresa a partir de uma teia; recua se ferida.",
        )

    def test_foge_se_sozinho_pula_o_ataque(self):
        c_state = CombatState(ativo=True, inimigos=[self._kobold_solitario()])
        eventos, dano = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([]))
        assert dano == 0
        assert "recua" in eventos[0]

    def test_nao_foge_se_tem_aliado_vivo(self):
        # "Ataca em grupo" também é gatilho de vantagem (em_matilha) — dois
        # d20 por kobold, os dois natural 1 pra garantir erro sem precisar
        # rolar dano.
        c_state = CombatState(ativo=True, inimigos=[self._kobold_solitario(), self._kobold_solitario()])
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([1, 1, 1, 1]))
        assert all("recua" not in e for e in eventos)

    def test_matilha_ataca_com_vantagem_quando_tem_aliado(self):
        # (7,9) -> vantagem fica com 9; total 9+4=13 < CA 15, erra sem
        # precisar rolar dano (mantém o teste focado no d20, não no dano).
        c_state = CombatState(ativo=True, inimigos=[self._lobo_matilha(), self._lobo_matilha()])
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([7, 9, 1, 1]))
        assert eventos[0].dados.vantagem is True
        assert eventos[0].dados.d20 == 9

    def test_recua_quando_ferida_abaixo_de_30_por_cento(self):
        c_state = CombatState(ativo=True, inimigos=[self._aranha_ferida(hp=5)])  # 5/18 = 27%
        eventos, dano = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([]))
        assert dano == 0
        assert "recua" in eventos[0]

    def test_nao_recua_acima_de_30_por_cento(self):
        c_state = CombatState(ativo=True, inimigos=[self._aranha_ferida(hp=10)])  # 10/18 = 55%
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([1]))
        assert "recua" not in eventos[0]

    def test_vantagem_da_matilha_cancela_com_desvantagem_do_heroi(self):
        # Regra do 5e: vantagem e desvantagem de fontes diferentes se
        # cancelam — o Lobo tem vantagem por matilha, mas o herói se
        # esquivou (desvantagem pros inimigos); o resultado é um d20 normal.
        c_state = CombatState(ativo=True, inimigos=[self._lobo_matilha(), self._lobo_matilha()])
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=RngFixo([9, 9]), vantagem=False)
        assert eventos[0].dados.vantagem is None
        assert eventos[0].dados.d20 == 9


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


class TestTurnoInimigosComAliados:
    """Fase 2 da revisão de gameplay — refactor pra múltiplos alvos amigos.
    Ver ADR-0027 (revisão da decisão de escopo §9.3)."""

    def _goblin(self) -> Inimigo:
        return Inimigo(nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra")

    def _aliado(self, hp=10) -> Aliado:
        return Aliado(nome="Bob", hp=hp, max_hp=10, ca=13, bonus_ataque=3, dano_dado="1d6", nome_ataque="Adaga")

    def test_ataque_contra_aliado_nao_conta_como_dano_ao_heroi(self):
        aliado = self._aliado()
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[aliado])
        # d20=15+4=19 >= CA 13 do aliado -> acerta. dano 1d6+2 com d6=4 -> 6.
        rng = _RngAlvo([15, 4], ("aliado", 0))
        eventos, dano_heroi = combat.turno_inimigos(c_state, ca_heroi=15, rng=rng)
        assert dano_heroi == 0
        assert aliado.hp == 4
        assert "Bob" in eventos[0]

    def test_aliado_reduzido_a_zero_gera_evento_de_morte(self):
        aliado = self._aliado(hp=1)
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[aliado])
        rng = _RngAlvo([15, 4], ("aliado", 0))
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=rng)
        assert aliado.hp == 0
        evento_morte = next(e for e in eventos if "cai" in e)
        assert evento_morte.dados.tipo == "morte_aliado"
        assert evento_morte.dados.quem == "Bob"

    def test_tatica_do_heroi_nao_protege_o_aliado(self):
        # esquivar do herói (vantagem=False, desvantagem PROS INIMIGOS que
        # o atacam) não tem efeito num ataque mirado no aliado — só a
        # tática do próprio inimigo (comportamento, Fase 1) contaria aqui,
        # e o Goblin não tem nenhuma. d20 único (sem vantagem/desvantagem).
        aliado = self._aliado()
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[aliado])
        rng = _RngAlvo([5], ("aliado", 0))  # 5+4=9 < CA 13 -> erra, sem precisar rolar dano
        eventos, _ = combat.turno_inimigos(c_state, ca_heroi=15, rng=rng, vantagem=False)
        assert eventos[0].dados.vantagem is None
        assert eventos[0].dados.d20 == 5


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
