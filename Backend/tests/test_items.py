"""Fase 1 do plano "jogo completo" (ADR-0033) — catálogo com números, itens
inventados só com tags, slots equipados, saque por banda e mercador. Tudo
servidor: o narrador nunca escreve cura, CA ou preço."""

import random

import pytest

from app.domain.items import Equipamento, ItemCatalogo
from app.domain.living_world import PessoaMundo
from app.domain.state import CombatState, Inimigo, WorldState
from app.infra.data_manager import regras
from app.services import items as itens
from app.services import rules_engine as motor
from app.services.loot import gerar_loot, recompensa_arco
from app.services.progression import migrar_equipamento
from tests.helpers import RngFixo
from tests.test_tools import _executor, _heroi

ATRIB = {"forca": 14, "destreza": 14, "constituicao": 12, "inteligencia": 10, "sabedoria": 10, "carisma": 10}


class TestCatalogo:
    def test_todo_item_do_catalogo_valida(self):
        for nome, dados in regras.items.items():
            ItemCatalogo.model_validate(dados), nome

    def test_toda_arma_tem_preco(self):
        for grupo in regras.weapons.values():
            for nome, dados in grupo.items():
                assert dados.get("preco", 0) >= 0, nome

    def test_nome_canonico_ignora_acento_e_caixa(self):
        assert regras.nome_canonico("pocao de cura") == "Poção de Cura"
        assert regras.nome_canonico("ESPADA LONGA") == "Espada Longa"
        assert regras.nome_canonico("Amuleto de Osso") is None

    def test_loot_so_cita_itens_do_catalogo(self):
        for banda, regra in regras.loot.items():
            if banda.startswith("_"):
                continue
            itens_lista = regra.get("itens", []) if banda != "arco" else [i for f in regra.values() for i in f["itens"]]
            for nome in itens_lista:
                assert itens.ficha(nome), (banda, nome)


class TestDefesa:
    def test_sem_armadura_e_dez_mais_destreza(self):
        assert motor.calcular_defesa(ATRIB, None, None) == 12

    def test_leve_soma_destreza_media_limita_pesada_ignora(self):
        assert motor.calcular_defesa(ATRIB, regras.get_item("Armadura de Couro"), None) == 13
        assert motor.calcular_defesa({**ATRIB, "destreza": 18}, regras.get_item("Armadura de Escamas"), None) == 16
        assert motor.calcular_defesa({**ATRIB, "destreza": 18}, regras.get_item("Cota de Malha"), None) == 16

    def test_escudo_soma_dois(self):
        assert motor.calcular_defesa(ATRIB, regras.get_item("Cota de Malha"), regras.get_item("Escudo")) == 18


class TestEquipar:
    def test_equipar_decide_o_slot_e_recalcula_defesa(self):
        heroi = _heroi(inventario=["Cota de Malha", "Espada Longa", "Escudo"], defesa=12)
        heroi.equipamento = {}
        assert itens.equipar(heroi, "cota de malha")["slot"] == "armadura"
        assert heroi.defesa == 16
        itens.equipar(heroi, "Escudo")
        assert heroi.defesa == 18
        assert itens.equipar(heroi, "Espada Longa")["slot"] == "arma"
        assert heroi.equipamento == {"arma": "Espada Longa", "armadura": "Cota de Malha", "escudo": "Escudo"}

    def test_forca_minima_e_duas_maos_sao_respeitadas(self):
        heroi = _heroi(inventario=["Armadura de Placas", "Machado Grande", "Escudo"])
        heroi.atributos = {**ATRIB, "forca": 12}
        heroi.equipamento = {}
        assert "erro" in itens.equipar(heroi, "Armadura de Placas")
        assert "erro" not in itens.equipar(heroi, "Escudo")
        assert "erro" in itens.equipar(heroi, "Machado Grande")  # escudo × duas mãos
        itens.desequipar(heroi, "escudo")
        assert "erro" not in itens.equipar(heroi, "Machado Grande")
        assert "erro" in itens.equipar(heroi, "Escudo")

    def test_item_fora_do_inventario_ou_sem_slot(self):
        heroi = _heroi(inventario=["Tocha"])
        heroi.equipamento = {}
        assert "erro" in itens.equipar(heroi, "Espada Longa")
        assert "erro" in itens.equipar(heroi, "Tocha")

    def test_backfill_equipa_o_que_ja_estava_na_mochila(self):
        heroi = _heroi(inventario=["Espada Curta", "Armadura de Couro"], defesa=12)
        heroi.equipamento = {}
        assert migrar_equipamento(heroi) is True
        assert heroi.equipamento["arma"] == "Espada Curta" and heroi.equipamento["armadura"] == "Armadura de Couro"
        assert heroi.defesa == 12  # couro 11 + DES 12 (+1)
        assert migrar_equipamento(heroi) is False  # idempotente

    def test_arma_equipada_e_a_preferida_no_ataque(self):
        from app.services.combat import escolher_arma

        nome, _ = escolher_arma(["Adaga", "Espada Longa"], None, equipada="Espada Longa")
        assert nome == "Espada Longa"
        nome, _ = escolher_arma(["Adaga", "Espada Longa"], "Adaga", equipada="Espada Longa")
        assert nome == "Adaga"  # a proposta explícita do jogador vence


class TestDarItem:
    def test_item_do_catalogo_entra_com_nome_canonico(self):
        heroi = _heroi(inventario=[])
        ex = _executor(heroi=heroi)
        assert "erro" not in ex.dar_item("pocao de cura")
        assert heroi.inventario == ["Poção de Cura"]

    def test_item_inventado_exige_descricao_e_tags_validas(self):
        heroi = _heroi(inventario=[])
        w = WorldState(local="Vila de Phandalin")
        ex = _executor(heroi=heroi, w_state=w)
        assert "erro" in ex.dar_item("Amuleto de Osso")
        assert "erro" in ex.dar_item("Amuleto de Osso", descricao="Osso polido", tags=["Mágico"])
        assert "erro" not in ex.dar_item("Amuleto de Osso", descricao="Osso polido num cordão", tags=["Sagrado"])
        assert "Amuleto de Osso" in w.itens_inventados and heroi.inventario == ["Amuleto de Osso"]
        # e a tag vale em rolar_teste
        ex2 = _executor(heroi=heroi, w_state=w, rng=RngFixo([10]))
        ex2.rolar_teste("sabedoria", 12, item_usado="amuleto de osso", motivo="rezar")
        partes = ex2.eventos[-1].dados.partes_bonus
        assert any(parte["rotulo"].startswith("Amuleto de Osso") for parte in partes)


class TestUsarItem:
    def test_pocao_de_foco_e_antidoto(self):
        heroi = _heroi(inventario=["Poção de Foco", "Antídoto"])
        c = CombatState(ativo=True, foco=0, foco_max=3, efeitos_heroi={"envenenado": 2},
                        inimigos=[Inimigo(nome="Goblin", hp=7, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2")])
        ex = _executor(heroi=heroi, c_state=c, rng=RngFixo([3, 3, 3, 3]))
        assert ex.usar_item("Poção de Foco")["foco"] == 2
        assert "Poção de Foco" not in heroi.inventario
        assert ex.usar_item("antidoto")["removidos"] == ["envenenado"]

    def test_frasco_de_oleo_atinge_todos_e_pode_vencer(self):
        heroi = _heroi(inventario=["Frasco de Óleo"], xp=0, nivel=1, classe="Guerreiro")
        c = CombatState(ativo=True, inimigos=[
            Inimigo(nome="Goblin", hp=3, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", xp=50),
            Inimigo(nome="Kobold", hp=3, max_hp=5, ca=12, bonus_ataque=4, dano_dado="1d4+2", xp=25),
        ])
        ex = _executor(heroi=heroi, c_state=c, rng=RngFixo([3, 3, 3, 3]))
        r = ex.usar_item("Frasco de Óleo")
        assert r["dano_total"] == 12 and r["resultado"] == "vitoria" and c.ativo is False

    def test_oleo_de_lamina_soma_dois_no_ataque(self):
        heroi = _heroi(inventario=["Óleo de Lâmina", "Espada Longa"], classe="Guerreiro")
        heroi.equipamento = {"arma": "Espada Longa"}
        goblin = Inimigo(nome="Goblin", hp=20, max_hp=20, ca=10, bonus_ataque=4, dano_dado="1d6+2")
        c = CombatState(ativo=True, inimigos=[goblin])
        ex = _executor(heroi=heroi, c_state=c, rng=RngFixo([15, 4, 5]))
        ex.usar_item("Óleo de Lâmina")
        assert c.efeitos_heroi.get("lamina") == 2  # 3 rodadas, uma já passou (reação inimiga)
        ex2 = _executor(heroi=heroi, c_state=c, rng=RngFixo([15, 4, 5, 5]))
        ex2.atacar("Goblin")
        # d8=4 + FOR(+2) + lâmina 2 = 8 de dano
        assert c.inimigos[0].hp == 12


class TestLoot:
    def _goblin(self):
        return Inimigo(
            nome="Goblin", arquetipo="Goblin", hp=0, max_hp=7, ca=15, bonus_ataque=4, dano_dado="1d6+2", xp=50
        )

    def test_saque_e_deterministico_por_rng(self):
        a = gerar_loot([self._goblin()], random.Random(7))
        b = gerar_loot([self._goblin()], random.Random(7))
        assert (a.ouro, a.itens) == (b.ouro, b.itens)
        assert a.ouro >= 1

    def test_inimigo_afastado_nao_deixa_saque(self):
        vivo = self._goblin()
        vivo.hp = 5
        vivo.afastado = True
        assert gerar_loot([vivo], random.Random(1)).ouro == 0

    def test_vitoria_entrega_ouro_no_heroi(self):
        heroi = _heroi(ouro=10, inventario=["Espada Longa"], classe="Guerreiro")
        c = CombatState(ativo=True, inimigos=[Inimigo(nome="Goblin", arquetipo="Goblin", hp=1, max_hp=7, ca=5,
                                                      bonus_ataque=4, dano_dado="1d6+2", xp=50)])
        w = WorldState(local="Vila de Phandalin", semente_aventura=42, turno=3)
        ex = _executor(heroi=heroi, c_state=c, w_state=w, rng=RngFixo([15, 4, 7]))
        r = ex.atacar("Goblin")
        assert r["resultado"] == "vitoria" and r.get("ouro_saque", 0) >= 1
        assert heroi.ouro == 10 + r["ouro_saque"]

    def test_recompensa_de_arco_por_faixa(self):
        assert recompensa_arco(1, random.Random(1)).itens == ["Poção de Cura", "Poção de Foco"]
        assert "Cota de Malha" in recompensa_arco(6, random.Random(1)).itens


class TestComerciar:
    def _mundo(self, executor, confianca=0, mercadoria=("Poção de Cura", "Espada Curta")):
        m = executor.w_state.mundo
        m.pessoas["mercador"] = PessoaMundo(
            id="mercador", nome="Bela", local=executor.w_state.local, objetivo="vender",
            confianca=confianca, mercadoria=list(mercadoria),
        )

    def test_vitrine_com_preco_do_servidor_e_desconto_por_confianca(self):
        ex = _executor(heroi=_heroi(ouro=100), w_state=WorldState(local="Vila de Phandalin"))
        self._mundo(ex, confianca=100)
        vitrine = ex.comerciar("Bela", "listar")["vitrine"]
        assert {"item": "Poção de Cura", "preco": 19} in vitrine  # 25 * 0.75 = 18.75 -> 19

    def test_comprar_debita_e_entrega(self):
        heroi = _heroi(ouro=30, inventario=[])
        ex = _executor(heroi=heroi, w_state=WorldState(local="Vila de Phandalin"))
        self._mundo(ex)
        r = ex.comerciar("mercador", "comprar", "Poção de Cura")
        assert r["preco"] == 25 and heroi.ouro == 5 and heroi.inventario == ["Poção de Cura"]
        assert "erro" in ex.comerciar("mercador", "comprar", "Espada Curta")  # sem ouro

    def test_vender_item_equipado_desequipa(self):
        heroi = _heroi(ouro=0, inventario=["Espada Longa"])
        heroi.equipamento = {"arma": "Espada Longa"}
        ex = _executor(heroi=heroi, w_state=WorldState(local="Vila de Phandalin"))
        self._mundo(ex)
        r = ex.comerciar("Bela", "vender", "Espada Longa")
        assert r["preco"] == 7 and heroi.ouro == 7 and heroi.inventario == []
        assert heroi.equipamento["arma"] is None

    def test_sem_mercador_ou_em_combate_recusa(self):
        ex = _executor(heroi=_heroi(ouro=100), w_state=WorldState(local="Vila de Phandalin"))
        assert "erro" in ex.comerciar("ninguem", "listar")
        self._mundo(ex)
        ex.c_state.ativo = True
        assert "erro" in ex.comerciar("Bela", "listar")

    def test_registrar_pessoa_filtra_mercadoria_fora_do_catalogo(self):
        from tests.test_living_world import agir  # helper de ferramenta

        ex = _executor(heroi=_heroi(), w_state=WorldState(local="Vila de Phandalin"))
        ex.w_state.mundo.cenas  # noqa: B018 — garante mundo carregado
        _, ok = agir(ex, "registrar_pessoa", pessoa={
            "id": "quitandeira", "nome": "Nara", "local": "Vila de Phandalin", "objetivo": "vender",
            "mercadoria": ["pocao de cura", "Elmo do Sol", "Escudo"],
        })
        assert ok
        assert ex.w_state.mundo.pessoas["quitandeira"].mercadoria == ["Poção de Cura", "Escudo"]


class TestToolsPorEstadoFase1:
    def test_comerciar_e_desequipar_so_fora_de_combate_equipar_sempre(self):
        from app.services.tools import tools_para

        fora = {t["function"]["name"] for t in tools_para(CombatState(ativo=False))}
        dentro = {t["function"]["name"] for t in tools_para(CombatState(ativo=True))}
        assert {"comerciar", "desequipar", "equipar"} <= fora
        assert "equipar" in dentro and not {"comerciar", "desequipar"} & dentro


@pytest.mark.parametrize("nome", ["Equipamento"])
def test_equipamento_modelo_vazio(nome):
    assert Equipamento().model_dump() == {"arma": None, "armadura": None, "escudo": None}

    def test_recadastro_de_pessoa_conhecida_so_atualiza_a_mercadoria(self):
        from tests.test_living_world import agir

        ex = _executor(heroi=_heroi(), w_state=WorldState(local="Vila de Phandalin"))
        self._mundo(ex, confianca=40, mercadoria=())
        ex.w_state.mundo.pessoas["mercador"].lembrancas = ["ajudou na ponte"]
        r, ok = agir(ex, "registrar_pessoa", pessoa={
            "id": "outro", "nome": "bela", "local": "Vila de Phandalin", "objetivo": "x", "mercadoria": ["Antídoto"],
        })
        assert ok and r["existente"] and r["mercadoria"] == ["Antídoto"]
        pessoa = ex.w_state.mundo.pessoas["mercador"]
        assert pessoa.mercadoria == ["Antídoto"] and pessoa.confianca == 40 and pessoa.lembrancas == ["ajudou na ponte"]
        assert "outro" not in ex.w_state.mundo.pessoas
