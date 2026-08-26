"""Testa app/services/tools.py — cada ferramenta que o modelo pode chamar
(Etapa 4, ADR-0007), isolada do loop de agente e da API da Groq. Mesmo
padrão de `random.Random` com sequência fixa de test_combat.py/
test_rules_engine.py."""

from app.domain.state import Aliado, Ato, CombatState, Inimigo, LocalDescoberto, QuestLog, WorldState
from app.infra.db import Personagem
from app.services.tools import RELOGIO_URGENCIA, ToolExecutor, sincronizar_aliados
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


def _registro_aliado(nome: str, hp: int = 10, hp_max: int = 10, classe: str = "Batedor") -> dict:
    """Mesma forma de `Personagem.aliados` (Fase 3) — só pra não repetir o
    dict inteiro em cada teste."""
    return {"nome": nome, "classe": classe, "hp": hp, "hp_max": hp_max, "lealdade": 50, "inventario": []}


def _executor(heroi=None, c_state=None, w_state=None, q_state=None, rng=None) -> ToolExecutor:
    return ToolExecutor(
        heroi or _heroi(),
        c_state or CombatState(),
        w_state or WorldState(local="Vila de Phandalin", clima="Ensolarado"),
        q_state or QuestLog(),
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

    def test_item_com_tag_no_inventario_concede_bonus(self):
        # Fase 6 (revisão de gameplay) — Tocha tem tag [Fogo] em
        # data/items.json. destreza mod +1; sem o item d20=13 -> total 14
        # < CD 15 (falha); com o bônus +2 vira 16 >= 15 (sucesso).
        heroi = _heroi(inventario=["Cimitarra", "Tocha"])
        executor = _executor(heroi=heroi, rng=RngFixo([13]))
        resultado = executor.rolar_teste("destreza", 15, item_usado="Tocha")
        assert resultado["sucesso"] is True
        assert resultado["total"] == 16
        [evento] = executor.eventos
        assert {"rotulo": "Tocha (Fogo)", "valor": 2} in evento.dados.partes_bonus

    def test_item_fora_do_inventario_nao_concede_bonus(self):
        heroi = _heroi(inventario=["Cimitarra"])  # sem a Tocha
        resultado = _executor(heroi=heroi, rng=RngFixo([13])).rolar_teste("destreza", 15, item_usado="Tocha")
        assert resultado["total"] == 14  # sem bônus de item

    def test_item_sem_tag_nao_concede_bonus(self):
        heroi = _heroi(inventario=["Cimitarra", "Mochila"])  # Mochila não está em data/items.json
        resultado = _executor(heroi=heroi, rng=RngFixo([13])).rolar_teste("destreza", 15, item_usado="Mochila")
        assert resultado["total"] == 14

    def test_arma_reaproveita_propriedades_como_tag(self):
        # Machado Grande tem propriedade "Pesada" em data/weapons.json —
        # Fase 6 trata propriedade de arma como tag também. mod força +2
        # (atributos padrão de _heroi) + bônus de item +2 = 4; d20=13 -> 17.
        heroi = _heroi(inventario=["Cimitarra", "Machado Grande"])
        resultado = _executor(heroi=heroi, rng=RngFixo([13])).rolar_teste("forca", 15, item_usado="Machado Grande")
        assert resultado["total"] == 17


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


class TestEsquivar:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).esquivar()
        assert "erro" in resultado

    def test_impoe_desvantagem_ao_ataque_inimigo_e_reseta_depois(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        # desvantagem: dois d20 (9,3) -> fica com o menor, 3; total 3+4=7 < CA 15 -> erra.
        executor = _executor(c_state=c_state, rng=RngFixo([9, 3]))
        resultado = executor.esquivar()
        assert any("esquiva" in e for e in executor.eventos)
        evento_ataque = next(e for e in executor.eventos if getattr(e, "dados", None) and e.dados.tipo == "ataque")
        assert evento_ataque.dados.vantagem is False
        assert evento_ataque.dados.d20 == 3
        assert c_state.heroi_vantagem_inimiga is None  # o efeito não sobrevive além desta rodada
        assert resultado["hp_atual"] == 10


class TestDefender:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).defender()
        assert "erro" in resultado

    def test_bonus_de_ca_evita_o_acerto_e_reseta_depois(self):
        # Sem o bônus, d20=11+4=15 acertaria a CA 15 do herói. Com +2 (CA
        # efetiva 17), o mesmo ataque erra.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([11]))
        resultado = executor.defender()
        assert any("defensiva" in e for e in executor.eventos)
        assert c_state.heroi_bonus_ca == 0
        assert resultado["hp_atual"] == 10


class TestInvestir:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).investir("Goblin")
        assert "erro" in resultado

    def test_penalidade_no_acerto_e_bonus_no_dano(self):
        # bônus efetivo: proficiência 2 + força 2 - 2 (investida) = 2.
        # d20=15 -> total 17 >= CA 15 -> acerta. dano 1d6(=4)+força(2)=6,
        # x1.5 (investida) = 9 -> mata o Goblin (hp 1).
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4]))
        resultado = executor.investir("Goblin", "Cimitarra")
        assert resultado["resultado"] == "vitoria"
        evento_ataque = next(e for e in executor.eventos if getattr(e, "dados", None) and e.dados.tipo == "ataque")
        assert {"rotulo": "Investida", "valor": -2} in evento_ataque.dados.partes_bonus

    def test_nao_letal_expoe_o_heroi_a_vantagem_no_contra_ataque(self):
        # dano: 1d6(=1)+força(2)=3, x1.5=4 -> Goblin sobrevive (7-4=3).
        # Contra-ataque com vantagem: d20(2,9) -> fica com 9; 9+4=13 < CA
        # 15 do herói -> erra.
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=7)])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 1, 2, 9]))
        executor.investir("Goblin", "Cimitarra")
        evento_contra = executor.eventos[-1]
        assert evento_contra.dados.vantagem is True
        assert c_state.heroi_vantagem_inimiga is None


class TestEsconderSe:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).esconder_se()
        assert "erro" in resultado

    def test_sucesso_esconde_o_heroi_e_inimigo_nao_ataca(self):
        # teste de Destreza (mod +1): d20=15 -> total 16 >= CD 12 -> sucesso.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([15]))
        resultado = executor.esconder_se()
        assert resultado["escondido"] is True
        assert resultado["dano_recebido"] == 0
        assert c_state.heroi_escondido is False  # consumido na mesma rodada

    def test_falha_ao_esconder_inimigo_ataca_normalmente(self):
        # teste: d20=5+1=6 < CD 12 -> falha. Contra-ataque normal: d20=1 -> erra.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([5, 1]))
        resultado = executor.esconder_se()
        assert resultado["escondido"] is False
        assert resultado["dano_recebido"] == 0


class TestFugir:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).fugir()
        assert "erro" in resultado

    def test_sucesso_encerra_o_combate_sem_resultado(self):
        # d20=15+1=16 >= CD 12 -> sucesso.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([15]))
        resultado = executor.fugir()
        assert resultado["fugiu"] is True
        assert c_state.ativo is False
        assert c_state.resultado is None  # não é vitória nem morte, só termina

    def test_falha_gera_uma_rodada_de_ataque_livre(self):
        # d20=5+1=6 < CD 12 -> falha. Ataque livre do Goblin: d20=1 -> erra.
        c_state = CombatState(ativo=True, inimigos=[self._goblin()])
        executor = _executor(c_state=c_state, rng=RngFixo([5, 1]))
        resultado = executor.fugir()
        assert resultado["fugiu"] is False
        assert c_state.ativo is True


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

    def test_destino_desconhecido_sem_descricao_continua_rejeitado(self):
        # Fase 5 — sem `descricao_proposta`, o comportamento de antes desta
        # fase não muda: nada de local inventado sem passar pelo registro.
        resultado = _executor().mover("Torre Caída")
        assert "erro" in resultado
        assert "Torre Caída" not in resultado["locais_validos"]

    def test_destino_novo_com_descricao_e_registrado_e_move(self):
        # rng fixo em 10 (nem 1 nem 20) pra não disparar o encontro
        # aleatório da Fase 6 e deixar o teste flaky.
        w_state = WorldState(local="Vila de Phandalin", clima="Chuvoso")
        executor = _executor(w_state=w_state, rng=RngFixo([10]))
        resultado = executor.mover("Torre Caída", descricao_proposta="Uma torre de mago em ruínas.")
        assert resultado["local"] == "Torre Caída"
        assert resultado["descricao"] == "Uma torre de mago em ruínas."
        assert "encontro" not in resultado
        assert w_state.local == "Torre Caída"
        assert w_state.locais_descobertos["Torre Caída"].descricao == "Uma torre de mago em ruínas."
        assert any("registrado" in e for e in executor.eventos)

    def test_local_descoberto_herda_o_clima_da_cena_atual(self):
        w_state = WorldState(local="Vila de Phandalin", clima="Nevando")
        executor = _executor(w_state=w_state)
        executor.mover("Torre Caída", descricao_proposta="Uma torre em ruínas.")
        assert w_state.clima == "Nevando"
        assert w_state.locais_descobertos["Torre Caída"].clima == "Nevando"

    def test_local_ja_descoberto_e_reconhecido_sem_precisar_de_nova_descricao(self):
        w_state = WorldState(
            local="Vila de Phandalin", clima="Ensolarado",
            locais_descobertos={"Torre Caída": LocalDescoberto(descricao="Uma torre em ruínas.", clima="Frio")},
        )
        executor = _executor(w_state=w_state, rng=RngFixo([10]))
        resultado = executor.mover("Torre Caída")
        assert resultado["local"] == "Torre Caída"
        assert resultado["descricao"] == "Uma torre em ruínas."
        assert w_state.clima == "Frio"

    def test_local_do_catalogo_nunca_precisa_de_descricao_proposta(self):
        # Nada muda pro caminho já existente — descricao_proposta é
        # ignorada quando o destino já está no catálogo global.
        w_state = WorldState(local="Vila de Phandalin", clima="Ensolarado")
        executor = _executor(w_state=w_state, rng=RngFixo([10]))
        resultado = executor.mover("Floresta das Sombras", descricao_proposta="Isto deveria ser ignorado")
        assert resultado["descricao"] != "Isto deveria ser ignorado"
        assert "Floresta das Sombras" not in w_state.locais_descobertos

    def test_encontro_aleatorio_natural_1_e_emboscada(self):
        # Fase 6 (revisão de gameplay) — encontro aleatório de viagem.
        resultado = _executor(rng=RngFixo([1])).mover("Floresta das Sombras")
        assert resultado["encontro"] == "emboscada"

    def test_encontro_aleatorio_natural_20_e_achado(self):
        resultado = _executor(rng=RngFixo([20])).mover("Floresta das Sombras")
        assert resultado["encontro"] == "achado"

    def test_sem_natural_1_ou_20_nao_ha_encontro(self):
        resultado = _executor(rng=RngFixo([10])).mover("Floresta das Sombras")
        assert "encontro" not in resultado

    def test_falha_ao_mover_nao_rola_encontro(self):
        # A rolagem só acontece se o movimento de fato acontecer — um erro
        # não deveria consumir rng nem sugerir um encontro que não houve.
        resultado = _executor(rng=RngFixo([])).mover("Cidade Que Não Existe")
        assert "erro" in resultado
        assert "encontro" not in resultado


class TestDescansar:
    def test_durante_combate_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=True)).descansar("curto")
        assert "erro" in resultado

    def test_tipo_invalido_e_rejeitado(self):
        resultado = _executor().descansar("cochilo")
        assert "erro" in resultado

    def test_descanso_curto_cura_parcial(self):
        # dado_vida do Guerreiro = 1d10, mod constituição (13) = +1. d10=7 -> cura 8.
        heroi = _heroi(hp_atual=5, hp_max=20)
        executor = _executor(heroi=heroi, rng=RngFixo([7]))
        resultado = executor.descansar("curto")
        assert resultado == {"tipo": "curto", "cura": 8, "hp_atual": 13}
        assert heroi.hp_atual == 13

    def test_descanso_curto_nao_passa_do_hp_maximo(self):
        heroi = _heroi(hp_atual=18, hp_max=20)
        executor = _executor(heroi=heroi, rng=RngFixo([10]))  # cura 10+1=11, estouraria 20
        resultado = executor.descansar("curto")
        assert heroi.hp_atual == 20
        assert resultado["hp_atual"] == 20

    def test_descanso_longo_em_local_inseguro_e_rejeitado(self):
        w_state = WorldState(local="Floresta das Sombras")  # seguro: false
        heroi = _heroi(hp_atual=5, hp_max=20)
        resultado = _executor(heroi=heroi, w_state=w_state).descansar("longo")
        assert "erro" in resultado
        assert heroi.hp_atual == 5  # nada mudou

    def test_descanso_longo_em_local_seguro_cura_tudo(self):
        w_state = WorldState(local="Vila de Phandalin", turno=20)  # seguro: true
        heroi = _heroi(hp_atual=5, hp_max=20)
        resultado = _executor(heroi=heroi, w_state=w_state).descansar("longo")
        assert resultado["tipo"] == "longo"
        assert resultado["cura"] == 15
        assert heroi.hp_atual == 20
        assert w_state.ultimo_descanso_longo == 20

    def test_descanso_longo_registra_o_turno_e_bloqueia_o_proximo_cedo_demais(self):
        w_state = WorldState(local="Vila de Phandalin", turno=5, ultimo_descanso_longo=2)  # só 3 turnos atrás
        resultado = _executor(w_state=w_state).descansar("longo")
        assert "erro" in resultado

    def test_descanso_longo_incrementa_o_relogio_de_urgencia(self):
        w_state = WorldState(local="Vila de Phandalin", turno=20)
        _executor(w_state=w_state).descansar("longo")
        assert w_state.relogios[RELOGIO_URGENCIA] == 1

    def test_gancho_de_acampamento_so_aparece_com_aliado_vivo(self):
        w_state = WorldState(local="Vila de Phandalin", turno=20)
        heroi = _heroi(aliados=[_registro_aliado("Bob")])
        resultado = _executor(heroi=heroi, w_state=w_state).descansar("longo")
        assert "Bob" in resultado["gancho_acampamento"]

    def test_sem_aliado_vivo_nao_ha_gancho(self):
        w_state = WorldState(local="Vila de Phandalin", turno=20)
        resultado = _executor(w_state=w_state).descansar("longo")
        assert "gancho_acampamento" not in resultado


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

    def test_aliados_vivos_do_roster_entram_no_combate(self):
        # Fase 3 (revisão de gameplay) — companheiro recrutado antes desta
        # luta acompanha o herói pra dentro dela, com o HP que trouxe.
        heroi = _heroi(aliados=[
            {"nome": "Bob", "classe": "Batedor", "hp": 6, "hp_max": 10, "lealdade": 50, "inventario": []},
            {"nome": "Morto", "classe": "Guerreiro", "hp": 0, "hp_max": 10, "lealdade": 50, "inventario": []},
        ])
        c_state = CombatState()
        executor = _executor(heroi=heroi, c_state=c_state, rng=RngFixo([10, 1]))
        executor.iniciar_combate(["Goblin"])
        assert [a.nome for a in c_state.aliados] == ["Bob"]  # o aliado morto não volta
        assert c_state.aliados[0].hp == 6
        assert c_state.aliados[0].max_hp == 10


class TestRecrutarAliado:
    def test_recruta_e_grava_no_roster_persistente(self):
        heroi = _heroi()
        executor = _executor(heroi=heroi)
        resultado = executor.recrutar_aliado("Bob", "Batedor", 12)
        assert resultado == {"nome": "Bob", "classe": "Batedor", "hp": 12}
        assert heroi.aliados == [
            {"nome": "Bob", "classe": "Batedor", "hp": 12, "hp_max": 12, "lealdade": 50, "inventario": []}
        ]

    def test_hp_e_clampado_num_intervalo_razoavel(self):
        heroi = _heroi()
        executor = _executor(heroi=heroi)
        executor.recrutar_aliado("Bob", "Batedor", 999)
        assert heroi.aliados[0]["hp"] == ToolExecutor.HP_ALIADO_MAX
        executor.recrutar_aliado("Ana", "Curandeira", 0)
        assert heroi.aliados[1]["hp"] == ToolExecutor.HP_ALIADO_MIN

    def test_nome_duplicado_e_rejeitado(self):
        heroi = _heroi(aliados=[_registro_aliado("Bob")])
        resultado = _executor(heroi=heroi).recrutar_aliado("Bob", "Outra Classe", 5)
        assert "erro" in resultado
        assert len(heroi.aliados) == 1

    def test_recrutar_durante_combate_tambem_adiciona_ao_c_state(self):
        heroi = _heroi()
        c_state = CombatState(ativo=True, inimigos=[])
        executor = _executor(heroi=heroi, c_state=c_state)
        executor.recrutar_aliado("Bob", "Batedor", 12)
        assert len(c_state.aliados) == 1
        assert c_state.aliados[0].nome == "Bob"
        assert c_state.aliados[0].hp == 12

    def test_recrutar_fora_de_combate_nao_toca_c_state(self):
        heroi = _heroi()
        c_state = CombatState(ativo=False)
        executor = _executor(heroi=heroi, c_state=c_state)
        executor.recrutar_aliado("Bob", "Batedor", 12)
        assert c_state.aliados == []


class TestAtacarComAliado:
    def _goblin(self, hp=7) -> Inimigo:
        return Inimigo(
            nome="Goblin", hp=hp, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", nome_ataque="Cimitarra"
        )

    def _aliado(self, hp=10) -> Aliado:
        return Aliado(nome="Bob", hp=hp, max_hp=10, ca=12, bonus_ataque=2, dano_dado="1d6", nome_ataque="Adaga")

    def test_sem_combate_ativo_e_rejeitado(self):
        resultado = _executor(c_state=CombatState(ativo=False)).atacar_com_aliado("Bob", "Goblin")
        assert "erro" in resultado

    def test_aliado_inexistente_ou_morto_e_rejeitado(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[self._aliado(hp=0)])
        resultado = _executor(c_state=c_state).atacar_com_aliado("Bob", "Goblin")
        assert "erro" in resultado

    def test_resolve_o_ataque_pelo_motor_generalizado(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[self._aliado()])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4]))
        resultado = executor.atacar_com_aliado("Bob", "Goblin")
        assert c_state.inimigos[0].hp == 3
        assert resultado == {"aliado": "Bob", "alvo": "Goblin"}
        assert any("Bob" in e for e in executor.eventos)

    def test_nao_aciona_reacao_dos_inimigos_sozinho(self):
        # Simplificação deliberada (ADR-0027): o ataque do aliado não fecha
        # a rodada — só a ação do próprio herói faz isso. Sem uma segunda
        # rolagem de d20 no rng, uma reação dos inimigos aqui estouraria o
        # RngFixo (só há valores pro ataque do aliado).
        c_state = CombatState(ativo=True, inimigos=[self._goblin()], aliados=[self._aliado()])
        executor = _executor(c_state=c_state, rng=RngFixo([15, 4]))
        executor.atacar_com_aliado("Bob", "Goblin")  # não levanta StopIteration

    def test_vitoria_concede_xp_como_um_ataque_normal(self):
        c_state = CombatState(ativo=True, inimigos=[self._goblin(hp=1)], aliados=[self._aliado()])
        heroi = _heroi(xp=0, nivel=1, aliados=[])
        executor = _executor(heroi=heroi, c_state=c_state, rng=RngFixo([15, 4]))
        resultado = executor.atacar_com_aliado("Bob", "Goblin")
        assert resultado["resultado"] == "vitoria"
        assert resultado["xp_ganho"] == 50
        assert heroi.xp == 50


class TestSincronizarAliados:
    def test_sem_aliados_em_combate_nao_faz_nada(self):
        heroi = _heroi(aliados=[_registro_aliado("Bob")])
        sincronizar_aliados(heroi, CombatState())
        assert heroi.aliados[0]["hp"] == 10

    def test_hp_de_combate_e_copiado_pro_roster_persistente(self):
        heroi = _heroi(aliados=[_registro_aliado("Bob")])
        c_state = CombatState(aliados=[Aliado(nome="Bob", hp=4, max_hp=10, ca=12)])
        sincronizar_aliados(heroi, c_state)
        assert heroi.aliados[0]["hp"] == 4

    def test_aliado_que_nao_esta_em_combate_fica_intocado(self):
        heroi = _heroi(aliados=[_registro_aliado("Ana", hp=8, hp_max=8, classe="Curandeira")])
        c_state = CombatState(aliados=[Aliado(nome="Bob", hp=4, max_hp=10, ca=12)])
        sincronizar_aliados(heroi, c_state)
        assert heroi.aliados[0]["hp"] == 8


class TestAtualizarMissao:
    def _atos(self) -> list[Ato]:
        return [
            Ato(titulo="O Chamado", objetivo="Achar o mapa"),
            Ato(titulo="A Jornada", objetivo="Atravessar a floresta"),
        ]

    def test_atualiza_nome_e_objetivo(self):
        q_state = QuestLog()
        executor = _executor(q_state=q_state)
        resultado = executor.atualizar_missao("Resgatar o Ferreiro", "Encontrar o esconderijo")
        assert q_state.nome_missao == "Resgatar o Ferreiro"
        assert q_state.objetivo_missao == "Encontrar o esconderijo"
        assert resultado == {"missao": "Resgatar o Ferreiro", "objetivo": "Encontrar o esconderijo"}
        assert any("Missão atualizada" in e for e in executor.eventos)

    def test_avancar_ato_sem_esqueleto_nao_faz_nada(self):
        q_state = QuestLog(atos=[])
        executor = _executor(q_state=q_state)
        resultado = executor.atualizar_missao("Nome", "Objetivo", avancar_ato=True)
        assert q_state.ato_atual == 0
        assert "ato_atual" not in resultado

    def test_avancar_ato_avanca_o_indice(self):
        q_state = QuestLog(atos=self._atos(), ato_atual=0)
        executor = _executor(q_state=q_state)
        resultado = executor.atualizar_missao("Nome", "Objetivo", avancar_ato=True)
        assert q_state.ato_atual == 1
        assert resultado["ato_atual"] == 1
        assert resultado["ato_titulo"] == "A Jornada"
        assert any("Novo Ato" in e for e in executor.eventos)

    def test_avancar_ato_no_ultimo_nao_estoura_o_indice(self):
        q_state = QuestLog(atos=self._atos(), ato_atual=1)  # já no último
        executor = _executor(q_state=q_state)
        executor.atualizar_missao("Nome", "Objetivo", avancar_ato=True)
        assert q_state.ato_atual == 1  # não vira 2 (fora da lista)

    def test_sem_avancar_ato_o_indice_fica_parado(self):
        q_state = QuestLog(atos=self._atos(), ato_atual=0)
        executor = _executor(q_state=q_state)
        executor.atualizar_missao("Nome", "Objetivo")
        assert q_state.ato_atual == 0

    def test_avancar_ato_reseta_o_relogio_de_urgencia(self):
        # Fase 6 (revisão de gameplay) — o relógio é do Ato que está
        # terminando; o novo Ato começa com o dele zerado.
        q_state = QuestLog(atos=self._atos(), ato_atual=0)
        w_state = WorldState(relogios={RELOGIO_URGENCIA: 3})
        executor = _executor(q_state=q_state, w_state=w_state)
        executor.atualizar_missao("Nome", "Objetivo", avancar_ato=True)
        assert w_state.relogios[RELOGIO_URGENCIA] == 0


class TestConcluirObjetivo:
    def test_concede_xp_fixo_sem_combate(self):
        heroi = _heroi(xp=0, nivel=1)
        executor = _executor(heroi=heroi)
        resultado = executor.concluir_objetivo("Convenceu o guarda a abrir o portão")
        assert resultado["xp_ganho"] == 50
        assert heroi.xp == 50
        assert resultado["objetivo"] == "Convenceu o guarda a abrir o portão"

    def test_xp_suficiente_sobe_de_nivel(self):
        heroi = _heroi(xp=250, nivel=1, hp_max=10, hp_atual=10, classe="Guerreiro")
        executor = _executor(heroi=heroi, rng=RngFixo([7]))
        resultado = executor.concluir_objetivo("Resolveu o enigma da esfinge")
        assert resultado["xp_total"] == 300
        assert resultado["nivel"] == 2
        assert heroi.nivel == 2


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
