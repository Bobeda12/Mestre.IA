"""As ferramentas que o modelo pode chamar (Etapa 4, ADR-0007) — o
substituto do `comando_combate`/`inimigos_sugeridos`/`spawn_battle` em JSON
solto da Etapa 3. O modelo continua só PROPONDO (ADR-0006); quem decide
número é sempre `rules_engine.py`/`combat.py`, chamados daqui.

`TOOLS_SCHEMA` é o `tools=[...]` mandado pro SDK da Groq. `ToolExecutor` liga
cada nome de ferramenta ao estado real de um turno (`heroi`, `c_state`,
`w_state`) e devolve, para cada chamada, um par (resultado para o modelo,
sucesso) — nunca deixa uma ferramenta malformada derrubar o turno inteiro."""

import json
import random
from collections.abc import Callable
from typing import Any

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo, LocalDescoberto, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.services import combat, talents
from app.services import items as itens
from app.services import rules_engine as motor
from app.services.class_abilities import limite_foco, perfil_classe
from app.services.loot import gerar_loot
from app.services.world_tools import WORLD_DISPATCH, WORLD_TOOLS


class ToolExecutor:
    """Um por turno. Mantém referência direta a `c_state`/`w_state` (o mesmo
    objeto que o router vai persistir depois) — ferramentas mutam em vez de
    substituir, senão a reatribuição feita pelo router perderia a mudança."""

    def __init__(
        self,
        heroi: Personagem,
        c_state: CombatState,
        w_state: WorldState,
        q_state: QuestLog,
        rng: random.Random | None = None,
    ) -> None:
        self.heroi = heroi
        self.c_state = c_state
        self.w_state = w_state
        self.q_state = q_state
        self.rng = rng
        self.eventos: list[str] = []
        self._acao_gasta = False
        # Fase 3 (ADR-0034) — talentos são números em canais que o motor já
        # tem: `bonus_especializacao` é o canal de dano; a defesa é
        # recalculada onde muda (equipar/nível); vantagem entra em rolar_teste.
        self.mods = talents.modificadores(w_state.talentos, heroi.classe)
        self.c_state.bonus_especializacao = sum(
            escolha == "combatente" for escolha in w_state.mundo.especializacoes.values()
        ) + self.mods.dano

    @property
    def eventos_estruturados(self) -> list[dict]:
        """O dado por trás de cada evento que veio de uma rolagem (Etapa 7)
        — para o card do frontend, sem fazer parsing do texto emoji. Só os
        eventos construídos como `EventoRolagem` (ver domain/eventos.py)
        entram aqui; um `self.eventos.append("string comum")` continua
        funcionando em todo lugar, só não vira card."""
        return [e.dados.to_dict() for e in self.eventos if isinstance(e, EventoRolagem) and e.dados is not None]

    # -- ferramentas ---------------------------------------------------

    # Fase 6 da revisão de gameplay (Etapa 12/13) — bônus fixo por usar um
    # item/arma com tag de forma criativa (ex: um machado [Pesado] pra
    # arrombar uma porta). Primeira passada: qualquer tag vale o mesmo
    # bônus — o servidor não tenta casar qual tag combina com qual
    # situação, isso é a narrativa do modelo justificando; ajustar com
    # `evals/simulador.py` se +2 se mostrar fraco ou forte demais.
    BONUS_ITEM_COM_TAG = 2

    def rolar_teste(self, atributo: str, cd: int, item_usado: str | None = None, motivo: str | None = None) -> dict:
        if atributo not in motor.ATRIBUTOS_VALIDOS:
            return {"erro": f"'{atributo}' não é um atributo válido: {sorted(motor.ATRIBUTOS_VALIDOS)}"}
        # Remaster da criação de personagem — o modelo propõe a CD "base"
        # (5=trivial...25=muito difícil, ver TOOLS_SCHEMA); o servidor
        # decide o número final, somando o ajuste de `dificuldade` do
        # herói. Mesmo espírito de `vantagem_por_traco` logo abaixo.
        cd = motor.ajustar_cd_por_dificuldade(cd, self.heroi.dificuldade)
        mod = motor.calcular_modificador(self.heroi.atributos.get(atributo, 10))
        partes_bonus = [{"rotulo": motor.ATRIBUTO_LABEL[atributo], "valor": mod}]
        mod_total = mod
        item_real = itens.resolver_nome(item_usado, self.heroi.inventario) if item_usado else None
        tags = itens.tags_de(item_real, self.w_state.itens_inventados) if item_real else []
        item_usado = item_real or item_usado
        if tags:
            mod_total += self.BONUS_ITEM_COM_TAG
            partes_bonus.append({"rotulo": f"{item_usado} ({tags[0]})", "valor": self.BONUS_ITEM_COM_TAG})
        # Rodada de conserto (Parte 2, item H) — o servidor decide se algum
        # traço do herói se aplica, lendo o catálogo de raças; o `motivo`
        # só descreve a ação, nunca concede nada por conta própria.
        d_raca = regras.get_race_details(self.heroi.raca) or {}
        vantagem = motor.vantagem_por_traco(
            d_raca.get("tracos", []), d_raca.get("visao") == "Escuro", motivo
        ) or None
        if atributo in self.mods.vantagens:
            vantagem = True  # talento (Fase 3): vantagem no atributo escolhido
        resultado = motor.resolver_teste_atributo(mod_total, cd, self.rng, vantagem=vantagem)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_total, total=resultado.total,
            cd=cd, sucesso=resultado.sucesso, atributo=atributo,
            partes_bonus=partes_bonus, motivo=motivo,
            d20_extra=resultado.d20_extra, vantagem=resultado.vantagem,
        )
        vantagem_txt = " (vantagem de traço racial)" if resultado.vantagem else ""
        linha = (
            f"🎲 Teste de {atributo}: d20({resultado.rolagem})+{mod_total}={resultado.total} "
            f"vs CD {cd}{vantagem_txt} → {'SUCESSO' if resultado.sucesso else 'FALHA'}."
        )
        self.eventos.append(EventoRolagem(linha, dados))
        return {"sucesso": resultado.sucesso, "total": resultado.total}

    def atacar(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de atacar"}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel(),
            classe=self.heroi.classe,
            arma_equipada=(self.heroi.equipamento or {}).get("arma"),
        )
        self.eventos.extend(eventos)
        self._recuperar_foco(1)

        if all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            resultado_xp = self._conceder_xp(self.c_state.inimigos)
            return {"resultado": "vitoria", **resultado_xp}

        return self._resolver_reacao_inimiga()

    def _recuperar_foco(self, quantidade: int) -> None:
        self.c_state.foco_max = limite_foco(self._nivel())
        antes = self.c_state.foco
        self.c_state.foco = min(self.c_state.foco_max, antes + quantidade)
        if self.c_state.foco > antes:
            self.eventos.append(f"🔹 Recupera {self.c_state.foco - antes} Foco.")

    def _verificar_vitoria(self) -> dict:
        if self.c_state.ativo and all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            from app.services.living_world import marcar_chefe_enfrentado

            if self.c_state.chefe_do_arco:
                marcar_chefe_enfrentado(self.w_state)
            return {"resultado": "vitoria", **self._conceder_xp(self.c_state.inimigos)}
        return {}

    def usar_habilidade(self, habilidade: str, alvo: str | None = None) -> dict:
        if not self.c_state.ativo or self.heroi.hp_atual <= 0:
            return {"erro": "habilidades exigem combate ativo e herói consciente"}
        perfil = perfil_classe(self.heroi.classe)
        tecnica = next((h for h in perfil["habilidades"] if habilidade in (h["id"], h["nome"])), None)
        if tecnica is None:
            return {"erro": "essa habilidade não pertence à sua classe"}
        if self._nivel() < tecnica["nivel"]:
            return {"erro": f"habilidade desbloqueada no nível {tecnica['nivel']}"}
        if self.c_state.foco < tecnica["custo"]:
            return {"erro": "Foco insuficiente: ataque básico recupera 1; defender recupera 2"}
        vivos = [i for i in self.c_state.inimigos if i.hp > 0 and not i.afastado]
        if tecnica["alvo"] == "inimigo":
            escolhido = next((i for i in vivos if i.nome == alvo), None)
            if escolhido is None:
                return {"erro": "escolha um inimigo vivo pelo nome exato"}
            alvos = [escolhido]
        else:
            alvos = vivos if tecnica["alvo"] == "todos" else []
        self.c_state.foco -= tecnica["custo"]
        self.eventos.append(f"✦ {tecnica['nome']}! Custa {tecnica['custo']} Foco.")
        for efeito in ("furia", "protecao", "guarda", "esquiva", "precisao"):
            if tecnica.get(efeito):
                self.c_state.efeitos_heroi[efeito] = tecnica[efeito]
        atributo = perfil["atributo"]
        mod = max(0, motor.calcular_modificador(self.heroi.atributos.get(atributo, 10)))
        dano_total = 0
        for inimigo in alvos:
            dano = (motor.calcular_dano(tecnica["dano"], rng=self.rng) + mod + self._nivel() // 2
                    + self.c_state.bonus_especializacao)
            if tecnica.get("oportunista") and (inimigo.hp < inimigo.max_hp or inimigo.efeitos):
                dano += motor.calcular_dano("1d6", rng=self.rng)
            if tecnica.get("executar") and inimigo.hp * 2 < inimigo.max_hp:
                dano += motor.calcular_dano("2d6", rng=self.rng)
            dano += 3 if inimigo.efeitos.get("marcado", 0) else 0
            dano += 2 if self.c_state.efeitos_heroi.get("furia", 0) else 0
            dano += 2 if self.c_state.efeitos_heroi.get("lamina", 0) else 0
            dano = max(1, dano)
            dano_real = min(inimigo.hp, dano)
            inimigo.hp = max(0, inimigo.hp - dano)
            dano_total += dano_real
            self.eventos.append(EventoRolagem(
                f"✦ {tecnica['nome']} atinge {inimigo.nome}: {dano} de dano ({inimigo.hp}/{inimigo.max_hp} PV).",
                DadosRolagem(tipo="dano", quem="heroi", alvo=inimigo.nome, dano=dano,
                             atributo=atributo, arma=tecnica["nome"], sucesso=True),
            ))
            for efeito in ("atordoado", "queimando", "enfraquecido", "vulneravel", "marcado"):
                if tecnica.get(efeito):
                    inimigo.efeitos[efeito] = tecnica[efeito]
            if inimigo.hp == 0:
                self.eventos.append(EventoRolagem(
                    f"💀 {inimigo.nome} cai.", EventoStatus(tipo="morte_inimigo", quem=inimigo.nome)
                ))
        cura = tecnica.get("cura_fixa", 0)
        if tecnica.get("cura"):
            cura += motor.calcular_dano(tecnica["cura"], rng=self.rng) + mod
        if tecnica.get("dreno"):
            cura += dano_total // 2
        if cura:
            recuperado = min(cura, self.heroi.hp_max - self.heroi.hp_atual)
            self.heroi.hp_atual += recuperado
            self.eventos.append(EventoRolagem(
                f"💚 Recupera {recuperado} PV.", EventoStatus(tipo="cura", quem="heroi", valor=recuperado)
            ))
            if tecnica.get("grupo"):
                for aliado in self.c_state.aliados:
                    if aliado.hp > 0:
                        recuperado_aliado = min(cura, aliado.max_hp - aliado.hp)
                        aliado.hp += recuperado_aliado
                        self.eventos.append(EventoRolagem(
                            f"💚 {aliado.nome} recupera {recuperado_aliado} PV.",
                            EventoStatus(tipo="cura", quem=aliado.nome, valor=recuperado_aliado),
                        ))
        if tecnica.get("sumir"):
            self.c_state.heroi_escondido = True
        vitoria = self._verificar_vitoria()
        return {"habilidade": tecnica["id"], "foco": self.c_state.foco,
                **(vitoria or self._resolver_reacao_inimiga())}

    def interagir(self, interacao: str) -> dict:
        from app.services.encounters import interagir_cenario

        return interagir_cenario(self, interacao)

    # Fase 1 da revisão de gameplay (Etapa 12/13) — CD das ações táticas
    # que envolvem teste (esconder_se, fugir). Valor de primeira passada,
    # igual ao XP_OBJETIVO_NAO_COMBATE acima: ajustar depois com
    # `evals/simulador.py`, não chutar de novo.
    CD_ACAO_TATICA = 12

    @property
    def _cd_acao_tatica(self) -> int:
        return motor.ajustar_cd_por_dificuldade(self.CD_ACAO_TATICA, self.heroi.dificuldade)

    def _resolver_reacao_inimiga(self) -> dict:
        """Depois de uma ação estruturada do herói que NÃO é `atacar`
        (esquivar/defender/investir/esconder_se) — a rodada de inimigos
        ainda acontece, porque um turno é uma troca só, nunca só a ação do
        herói sozinha. Usa os efeitos que a ação acabou de armar em
        `c_state` (Fase 1: vantagem/desvantagem do ataque inimigo, bônus de
        CA, herói escondido) e os reseta em seguida — duram exatamente uma
        rodada, "até o próximo turno do herói" nunca sobrevive além dela
        porque cada ferramenta tática consome a rodada de inimigos na
        mesma chamada em que arma o efeito."""
        if not self.c_state.ativo or all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            return {}
        ca_efetiva = self.heroi.defesa + self.c_state.heroi_bonus_ca
        if self.c_state.efeitos_heroi.get("guarda", 0):
            ca_efetiva += 2
        vantagem = self.c_state.heroi_vantagem_inimiga
        if self.c_state.efeitos_heroi.get("esquiva", 0):
            vantagem = combat._combinar_vantagem(vantagem, False)
        if self.c_state.heroi_escondido:
            self.eventos.append("👤 Os inimigos vasculham o local, sem te encontrar.")
            dano = 0
            combat.finalizar_rodada(self.c_state)
        else:
            eventos_inimigos, dano = combat.turno_inimigos(
                self.c_state, ca_efetiva, self.rng, vantagem=vantagem
            )
            self.eventos.extend(eventos_inimigos)
        self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
        if self.heroi.hp_atual == 0 and dano > 0:
            self.eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
        self.c_state.heroi_vantagem_inimiga = None
        self.c_state.heroi_bonus_ca = 0
        self.c_state.heroi_escondido = False
        return {"dano_recebido": dano, "hp_atual": self.heroi.hp_atual, **self._verificar_vitoria()}

    def esquivar(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de esquivar"}
        self.c_state.heroi_vantagem_inimiga = False
        self.eventos.append("🛡️ Você se esquiva, atento a qualquer ataque.")
        return {"acao": "esquivar", **self._resolver_reacao_inimiga()}

    def defender(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de defender"}
        self.c_state.heroi_bonus_ca = 2
        self._recuperar_foco(2)
        self.eventos.append("🛡️ Você assume postura defensiva (+2 na CA).")
        return {"acao": "defender", **self._resolver_reacao_inimiga()}

    def investir(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de investir"}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel(),
            investida=True,
            classe=self.heroi.classe,
            arma_equipada=(self.heroi.equipamento or {}).get("arma"),
        )
        self.eventos.extend(eventos)
        if all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            resultado_xp = self._conceder_xp(self.c_state.inimigos)
            return {"resultado": "vitoria", **resultado_xp}
        # A abertura de uma investida custa caro: os inimigos atacam de
        # volta com vantagem até a próxima rodada.
        self.c_state.heroi_vantagem_inimiga = True
        return {"acao": "investir", **self._resolver_reacao_inimiga()}

    def esconder_se(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de esconder_se"}
        cd = self._cd_acao_tatica
        mod_destreza = motor.calcular_modificador(self.heroi.atributos.get("destreza", 10))
        resultado = motor.resolver_teste_atributo(mod_destreza, cd, self.rng)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_destreza, total=resultado.total,
            cd=cd, sucesso=resultado.sucesso, atributo="destreza",
            partes_bonus=[{"rotulo": "Destreza", "valor": mod_destreza}],
        )
        if resultado.sucesso:
            self.c_state.heroi_escondido = True
            texto = (
                f"🎲 Você se esconde: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {cd} → SUCESSO. Eles perdem seu rastro."
            )
        else:
            texto = (
                f"🎲 Você tenta se esconder: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {cd} → FALHA."
            )
        self.eventos.append(EventoRolagem(texto, dados))
        return {"acao": "esconder_se", "escondido": resultado.sucesso, **self._resolver_reacao_inimiga()}

    def fugir(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de fugir"}
        cd = self._cd_acao_tatica
        mod_destreza = motor.calcular_modificador(self.heroi.atributos.get("destreza", 10))
        resultado = motor.resolver_teste_atributo(mod_destreza, cd, self.rng)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_destreza, total=resultado.total,
            cd=cd, sucesso=resultado.sucesso, atributo="destreza",
            partes_bonus=[{"rotulo": "Destreza", "valor": mod_destreza}],
        )
        if resultado.sucesso:
            self.c_state.ativo = False
            texto = (
                f"🎲 Você foge: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {cd} → SUCESSO. Você escapa do combate."
            )
            self.eventos.append(EventoRolagem(texto, dados))
            return {"acao": "fugir", "fugiu": True}
        texto = (
            f"🎲 Você tenta fugir: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
            f"vs CD {cd} → FALHA. Eles reagem antes que você escape."
        )
        self.eventos.append(EventoRolagem(texto, dados))
        # falha custa uma rodada de ataque livre de cada inimigo vivo —
        # mecanicamente igual a uma rodada normal de inimigos.
        return {"acao": "fugir", "fugiu": False, **self._resolver_reacao_inimiga()}

    def _nivel(self) -> int:
        """`self.heroi.nivel` pode ser `None` num `Personagem()` montado à
        mão sem passar pelo default da coluna (cenários de
        `evals/golden/*.yaml` anteriores à Etapa 7, e testes que constroem
        o objeto direto — mesmo motivo de `atributos.get(attr, 10)` já usar
        default em vez de assumir a chave presente). Nunca acontece num
        personagem real, que sempre passou pelo INSERT com o default '1'."""
        return self.heroi.nivel or 1

    def _conceder_xp(self, inimigos_derrotados: list[Inimigo]) -> dict:
        """XP é uma consequência automática da vitória, não uma ferramenta
        que o modelo chama — mesmo princípio do teste de morte em
        `routers/game.py` (ADR-0006: o LLM propõe a cena, nunca decide o
        número). Sobe nível em loop porque uma vitória grande pode cruzar
        mais de um limiar de `rules_engine.XP_POR_NIVEL` de uma vez."""
        xp_ganho = sum(
            i.xp or (regras.get_monster(i.arquetipo or i.nome) or {}).get("xp", 0)
            for i in inimigos_derrotados
        )
        # Pendência do remaster UX (PLANO_REMASTER_UX.md, item 3) —
        # bestiário persistente: `_conceder_xp` é chamado exatamente uma
        # vez por vitória, com a lista definitiva de inimigos derrotados
        # (`self.c_state.inimigos`, todos já em 0 PV) — o único lugar do
        # motor que sabe "este combate acabou e estes morreram", sem
        # precisar recontar eventos ou arriscar contar o mesmo cadáver duas
        # vezes. Chave é o nome do bestiário (`i.nome`), a mesma que o
        # frontend já usa pra buscar o sprite em `/assets/monstros/`.
        if inimigos_derrotados:
            abates = dict(self.heroi.monstros_derrotados or {})
            for inimigo in inimigos_derrotados:
                if inimigo.hp > 0:
                    continue
                chave = inimigo.arquetipo or inimigo.nome
                abates[chave] = abates.get(chave, 0) + 1
            self.heroi.monstros_derrotados = abates
        # Fase 1 (ADR-0033) — saque determinístico por banda, no único
        # ponto de vitória. Ouro entra aqui e no fim de arco (Fase 4), e só.
        # RNG próprio, derivado da semente da aventura e do turno: o saque é
        # reprodutível e não consome a sequência de dados do combate (os
        # testes com `RngFixo` continuam exatos).
        rng_saque = random.Random(f"{self.w_state.semente_aventura}:{self.w_state.turno}:saque")
        saque = gerar_loot(inimigos_derrotados, rng_saque)
        extra: dict = {}
        if saque.ouro:
            self.heroi.ouro = (self.heroi.ouro or 0) + saque.ouro
            self.eventos.append(f"💰 Saque: {saque.ouro} de ouro. Total: {self.heroi.ouro}.")
            extra["ouro_saque"] = saque.ouro
        for nome_item in saque.itens:
            self.heroi.inventario = [*self.heroi.inventario, nome_item]
            self.eventos.append(f"🎁 {self.heroi.nome} recebe: {nome_item}.")
        if saque.itens:
            extra["itens_saque"] = saque.itens
        if xp_ganho <= 0:
            return extra
        return {**extra, **self._aplicar_xp(xp_ganho)}

    def _aplicar_xp(self, xp_ganho: int) -> dict:
        """Núcleo comum de `_conceder_xp` (vitória em combate) e
        `concluir_objetivo` (Fase 0 da revisão de gameplay — XP fora de
        combate). Separado porque as duas fontes de XP compartilham a mesma
        lógica de nível, mas nenhuma delas é a outra."""
        self.heroi.xp = (self.heroi.xp or 0) + xp_ganho
        self.heroi.nivel = self._nivel()
        self.eventos.append(f"✨ Ganha {xp_ganho} de XP ({self.heroi.xp} total).")

        dado_vida = regras.get_class_details(self.heroi.classe).get("dado_vida", 8)
        mod_con = motor.calcular_modificador(self.heroi.atributos.get("constituicao", 10))
        while True:
            resultado = motor.subir_nivel(self.heroi.xp, self.heroi.nivel, dado_vida, mod_con, self.rng)
            if not resultado.subiu:
                break
            self.heroi.nivel = resultado.nivel_novo
            hp_ganho = resultado.hp_ganho + self.mods.hp_por_nivel
            self.heroi.hp_max += hp_ganho
            self.heroi.hp_atual += hp_ganho
            self.eventos.append(f"🎉 Subiu para o nível {resultado.nivel_novo}! (+{hp_ganho} PV máximo)")
            # Fase 3 (ADR-0034) — a escolha fica pendente para o jogador; o
            # narrador só lembra, nunca escolhe.
            if talents.nivel_com_escolha(resultado.nivel_novo):
                self.w_state.niveis_pendentes = [*self.w_state.niveis_pendentes, resultado.nivel_novo]
                self.eventos.append(f"⭐ Nível {resultado.nivel_novo}: uma escolha espera por você na ficha.")
            for habilidade in perfil_classe(self.heroi.classe)["habilidades"]:
                if habilidade["nivel"] == resultado.nivel_novo:
                    self.eventos.append(f"✦ Nova técnica: {habilidade['nome']} — {habilidade['descricao']}")
        self.c_state.foco_max = limite_foco(self._nivel())
        return {"xp_ganho": xp_ganho, "xp_total": self.heroi.xp, "nivel": self.heroi.nivel}

    # Fase 0 da revisão de gameplay (Etapa 12/13) — XP não-combate: sem isso
    # o jogador que resolve tudo conversando nunca sobe de nível (P-1 do
    # backlog antigo, metade resolvida). Valor fixo, não proposto pelo
    # modelo — mesmo princípio de `_conceder_xp` (ADR-0006: o LLM não decide
    # números), só o "quando" é dele, o "quanto" é do servidor. Equivale a
    # um monstro de Nível 1 ; ajustar depois com `evals/simulador.py`.
    XP_OBJETIVO_NAO_COMBATE = 50

    def concluir_objetivo(self, objetivo: str) -> dict:
        chave = " ".join(objetivo.casefold().split())
        if not chave or chave in self.w_state.objetivos_concluidos:
            return {"erro": "objetivo vazio ou já recompensado"}
        if self.c_state.ativo:
            return {"erro": "conclua o encontro antes de recompensar um objetivo narrativo"}
        self.w_state.objetivos_concluidos.append(chave)
        resultado = self._aplicar_xp(self.XP_OBJETIVO_NAO_COMBATE)
        return {"objetivo": objetivo, **resultado}

    def aplicar_dano(self, alvo: str, dado_dano: str, motivo: str = "") -> dict:
        # Fase 0 do plano "jogo completo" (08/09/2026) — o guard que proibia
        # dano ambiental em inimigo durante combate foi removido por decisão
        # do autor: empurrar o goblin no fogo tem que funcionar. Para não
        # virar ataque grátis, em combate a chamada consome a ação do turno
        # (ver `executar`) e continua limitada a 4d12+10.
        qtd, faces, modificador = motor._parse_dado(dado_dano)
        if not (1 <= qtd <= 4 and 1 <= faces <= 12 and -10 <= modificador <= 10):
            return {"erro": "dano ambiental deve usar até 4 dados de no máximo 12 faces, modificador até 10"}
        dano = max(0, motor.calcular_dano(dado_dano, rng=self.rng))
        nomes_heroi = {"heroi", "herói", "você", "voce", self.heroi.nome.lower()}
        if alvo.lower() in nomes_heroi:
            self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
            self.eventos.append(
                f"🎲 {motivo or 'Dano recebido'}: {dado_dano} → {dano} de dano. "
                f"HP: {self.heroi.hp_atual}/{self.heroi.hp_max}."
            )
            return {"dano": dano, "hp_atual": self.heroi.hp_atual}

        alvo_obj = next((i for i in self.c_state.inimigos if i.nome == alvo and i.hp > 0 and not i.afastado), None)
        if alvo_obj is None:
            return {"erro": f"'{alvo}' não é um alvo válido (nem o herói, nem um inimigo vivo no combate)"}
        alvo_obj.hp = max(0, alvo_obj.hp - dano)
        self.eventos.append(
            f"🎲 {motivo or 'Dano aplicado'} em {alvo_obj.nome}: {dado_dano} → {dano} de dano. "
            f"{alvo_obj.nome}: {alvo_obj.hp}/{alvo_obj.max_hp} PV."
        )
        if alvo_obj.hp == 0:
            self.eventos.append(
                EventoRolagem(f"💀 {alvo_obj.nome} cai morto.", EventoStatus(tipo="morte_inimigo", quem=alvo_obj.nome))
            )
        return {"dano": dano, "hp_atual": alvo_obj.hp, **self._verificar_vitoria()}

    def mover(self, destino: str, descricao_proposta: str | None = None) -> dict:
        """Fase 5 da revisão de gameplay (Etapa 12/13, ADR-0028) — destino
        fora do catálogo global (`data/locations.json`) só é aceito se
        `descricao_proposta` vier junto: o modelo PROPÕE a descrição, o
        servidor REGISTRA (mesmo padrão "propõe/decide" do ADR-0002) em
        `w_state.locais_descobertos` antes de mover pra lá — nunca move
        pra um lugar que ele mesmo não conhece. Sem descrição, o
        comportamento é o de sempre: só os locais já conhecidos (catálogo
        ou já descobertos nesta sessão)."""
        if self.c_state.ativo:
            return {"erro": "não é possível se mover durante um combate ativo"}
        cena = self.w_state.mundo.cenas.get(self.w_state.local)
        if cena:
            # Fase 0 do plano "jogo completo" (08/09/2026) — saídas registradas
            # pelo Mundo Vivo só restringem os destinos que elas NOMEIAM: uma
            # passagem trancada para X impede ir a X, mas a cena nunca prende
            # o herói para destinos sem saída registrada (a origem emergente
            # promete "você pode partir sem aceitar compromisso", e o smoke
            # test de `mover` para o catálogo depende disso).
            caminhos = [e for e in cena.entidades.values() if e.tipo == "saida" and e.destino == destino]
            if caminhos and all(
                e.estado == "bloqueado" or ("trancado" in e.propriedades and e.estado != "destruido")
                for e in caminhos
            ):
                return {"erro": "As passagens para esse destino estão bloqueadas ou trancadas."}
        ja_descoberto = self.w_state.locais_descobertos.get(destino)
        dados = {"descricao": ja_descoberto.descricao, "clima": ja_descoberto.clima} if ja_descoberto else (
            regras.get_location(destino)
        )
        if not dados and descricao_proposta:
            # Herda o clima da cena atual — descobrir um lugar novo não
            # muda o tempo sozinho; se a narrativa quiser mudar o clima,
            # o próximo `mover`/turno já reflete isso.
            self.w_state.locais_descobertos = {
                **self.w_state.locais_descobertos,
                destino: LocalDescoberto(descricao=descricao_proposta, clima=self.w_state.clima),
            }
            dados = {"descricao": descricao_proposta, "clima": self.w_state.clima}
            self.eventos.append(f"🗺️ Novo local registrado: {destino}.")
        if not dados:
            locais_validos = regras.get_locations_list() + list(self.w_state.locais_descobertos.keys())
            return {"erro": f"'{destino}' não é um local conhecido", "locais_validos": locais_validos}
        self.w_state.local = destino
        if dados.get("clima"):
            self.w_state.clima = dados["clima"]
        # Pendência do remaster UX (item 2) — viajar custa horas de
        # verdade, não um turno abstrato; 2h é uma travessia curta entre
        # locais vizinhos, consistente com a escala do resto do jogo (uma
        # campanha de sessão única, não uma viagem de dias).
        self.w_state.hora_do_dia = (self.w_state.hora_do_dia + 2) % 24
        self.eventos.append(f"🧭 Vocês seguem para {destino}.")
        resultado = {"local": destino, "descricao": dados.get("descricao", "")}
        # Fase 6 da revisão de gameplay — encontro aleatório de viagem: 1
        # em 20 é emboscada, 20 em 20 é achado. O servidor só gera o
        # evento; a IA reage a ele (narra e chama iniciar_combate/dar_item
        # como a cena pedir) — ela não decide se algo acontece.
        dado = self.rng or random
        rolagem_viagem = dado.randint(1, 20)
        if rolagem_viagem == 1:
            resultado["encontro"] = "emboscada"
            self.eventos.append("⚠️ Perigo na estrada!")
        elif rolagem_viagem == 20:
            resultado["encontro"] = "achado"
            self.eventos.append("✨ Um golpe de sorte na estrada!")
        return resultado

    def consultar_regra(self, termo: str) -> dict:
        termo_lower = termo.lower().strip()
        if not termo_lower:
            return {"encontrado": False}
        trechos = [
            linha.strip()
            for linha in regras.get_biblia().splitlines()
            if termo_lower in linha.lower() and linha.strip()
        ]
        if not trechos:
            return {"encontrado": False}
        return {"encontrado": True, "trechos": trechos[:3]}

    def usar_item(self, item: str) -> dict:
        real = itens.resolver_nome(item, self.heroi.inventario)
        if real is None:
            return {"erro": f"'{item}' não está no inventário"}
        ficha_bruta = regras.get_item(real)
        if not ficha_bruta or ficha_bruta.get("tipo") != "consumivel":
            # Ferramenta, arma, armadura ou item inventado: não some da
            # mochila e não move número — o uso é narrativo (ou `equipar`).
            resultado = {"usado": True, "item": real, "efeito": "sem efeito mecânico — narre livremente o uso"}
        else:
            from app.domain.items import ItemCatalogo

            resultado = itens.aplicar_efeito_consumivel(self, real, ItemCatalogo.model_validate(ficha_bruta))
            inventario = list(self.heroi.inventario)
            inventario.remove(real)
            self.heroi.inventario = inventario
            if resultado.get("resultado") == "vitoria":
                return resultado
        # Fase 1 da revisão de gameplay — usar um item em combate gasta a
        # ação do herói como qualquer outra: antes disso os inimigos nunca
        # reagiam a um turno "de item" (self._resolver_reacao_inimiga() é
        # um no-op fora de combate, então isto não muda nada fora dele).
        return {**resultado, **self._resolver_reacao_inimiga()}

    # Fase 6 da revisão de gameplay (Etapa 12/13) — janela mínima entre
    # dois descansos longos, em turnos de jogo (não existe relógio de
    # calendário no sistema; "turnos desde o último" é a aproximação de
    # "um dia narrativo" — primeira passada, como o resto dos números
    # novos desta revisão).
    LIMITE_TURNOS_DESCANSO_LONGO = 8

    def _local_seguro(self) -> bool:
        """Um local recém-descoberto (Fase 5) é conservadoramente inseguro
        pra descanso longo — só o catálogo curado (`data/locations.json`,
        campo `seguro`) garante isso hoje."""
        if self.w_state.local in self.w_state.locais_descobertos:
            return False
        dados = regras.get_location(self.w_state.local) or {}
        return bool(dados.get("seguro", False))

    def descansar(self, tipo: str) -> dict:
        if self.c_state.ativo:
            return {"erro": "não é possível descansar durante um combate ativo"}
        if tipo not in ("curto", "longo"):
            return {"erro": "'tipo' precisa ser 'curto' ou 'longo'"}

        if tipo == "curto":
            dado_vida = regras.get_class_details(self.heroi.classe).get("dado_vida", 8)
            mod_con = motor.calcular_modificador(self.heroi.atributos.get("constituicao", 10))
            cura = max(1, motor.rolar_dado(f"1d{dado_vida}", self.rng) + mod_con)
            self.heroi.hp_atual = min(self.heroi.hp_max, self.heroi.hp_atual + cura)
            # Pendência do remaster UX (item 2) — descanso curto é ~1h
            # narrativa (uma pausa pra recuperar o fôlego), não a noite
            # inteira do descanso longo abaixo.
            self.w_state.hora_do_dia = (self.w_state.hora_do_dia + 1) % 24
            self.eventos.append(
                EventoRolagem(
                    f"🏕️ Descanso curto: recupera {cura} PV. HP: {self.heroi.hp_atual}/{self.heroi.hp_max}.",
                    EventoStatus(tipo="cura", quem="heroi", valor=cura),
                )
            )
            return {"tipo": "curto", "cura": cura, "hp_atual": self.heroi.hp_atual}

        # tipo == "longo"
        if not self._local_seguro():
            return {"erro": f"'{self.w_state.local}' não é seguro o bastante para um descanso longo"}
        turnos_desde_ultimo = self.w_state.turno - self.w_state.ultimo_descanso_longo
        if turnos_desde_ultimo < self.LIMITE_TURNOS_DESCANSO_LONGO:
            return {"erro": "o grupo descansou recentemente — ainda não é hora de outro descanso longo"}

        cura = self.heroi.hp_max - self.heroi.hp_atual
        self.heroi.hp_atual = self.heroi.hp_max
        self.w_state.ultimo_descanso_longo = self.w_state.turno
        # Pendência do remaster UX (item 2) — "dormir leva a noite toda":
        # descanso longo pula 8h de verdade (não é "amanhecer" fixo — duas
        # noites seguidas de manhã cedo continuam avançando, é a mesma
        # aritmética de mod 24 dos outros dois avanços).
        self.w_state.hora_do_dia = (self.w_state.hora_do_dia + 8) % 24
        self.eventos.append(
            EventoRolagem(
                f"🏕️ Descanso longo: recupera totalmente os PV. HP: {self.heroi.hp_atual}/{self.heroi.hp_max}.",
                EventoStatus(tipo="cura", quem="heroi", valor=cura),
            )
        )
        # O relógio de urgência do Ato saiu com os Atos (ADR-0032); o custo
        # de "descansar demais" agora é o dos conflitos do Mundo Vivo, que
        # avançam em `executar` -> `avancar_tempo` (480 min no descanso longo).
        resultado = {"tipo": "longo", "cura": cura, "hp_atual": self.heroi.hp_atual}
        # Fase 6 — gancho de roleplay: o descanso longo é o "acampamento"
        # do gameplay_v2.md, o momento de companheiro abrir o jogo — só
        # faz sentido quando existe um aliado vivo pra ter essa fala.
        aliados_vivos = [a for a in (self.heroi.aliados or []) if a["hp"] > 0]
        if aliados_vivos:
            resultado["gancho_acampamento"] = (
                f"Enquanto o grupo descansa, {aliados_vivos[0]['nome']} parece querer conversar — "
                "puxe uma fala ou revelação dele nesta cena, antes de continuar."
            )
        return resultado

    def dar_item(self, item: str, descricao: str | None = None, tags: list[str] | None = None) -> dict:
        """Fase 1 (ADR-0033): item do catálogo entra como sempre (nome
        canônico); item fora dele só entra com descrição + tags do
        vocabulário fechado e vira `ItemInventado` — nunca tem efeito além
        do bônus de tag em `rolar_teste`."""
        from pydantic import ValidationError

        from app.domain.items import TAGS_VALIDAS, ItemInventado

        canonico = regras.nome_canonico(item)
        if canonico is not None:
            item = canonico
        elif item in self.w_state.itens_inventados:
            pass
        else:
            if not descricao or not tags:
                return {"erro": f"'{item}' não está no catálogo: passe descricao e tags ({', '.join(TAGS_VALIDAS)})"}
            try:
                inventado = ItemInventado(nome=item, descricao=descricao, tags=tags)  # type: ignore[arg-type]
            except ValidationError:
                return {"erro": f"tags inválidas; use até 3 de: {', '.join(TAGS_VALIDAS)}"}
            self.w_state.itens_inventados = {**self.w_state.itens_inventados, item: inventado}
        self.heroi.inventario = [*self.heroi.inventario, item]
        self.eventos.append(f"🎁 {self.heroi.nome} recebe: {item}.")
        return {"inventario": self.heroi.inventario}

    def escolher_nivel(self, nivel: int, tipo: str, escolha: str) -> dict:
        """Decisão do jogador (só pela rota /game/action, nunca ferramenta do
        narrador): +1 atributo, talento, ou especialização nos marcos 3/7."""
        if nivel not in self.w_state.niveis_pendentes:
            return {"erro": f"não há escolha pendente para o nível {nivel}"}
        if self.c_state.ativo:
            return {"erro": "escolha de nível só fora de combate"}
        opcoes = talents.opcoes_para(self.heroi.classe, nivel, self.w_state.talentos, self.heroi.atributos or {})
        opcao = next((o for o in opcoes if o["tipo"] == tipo and o["id"] == escolha), None)
        if opcao is None:
            return {"erro": "opção inválida para este nível", "opcoes": opcoes}
        if tipo == "atributo":
            atributos = dict(self.heroi.atributos or {})
            antes = atributos.get(escolha, 10)
            atributos[escolha] = min(talents.ATRIBUTO_MAXIMO, antes + 1)
            self.heroi.atributos = atributos
            subiu_mod = motor.calcular_modificador(atributos[escolha]) > motor.calcular_modificador(antes)
            if escolha == "constituicao" and subiu_mod:
                self.heroi.hp_max += self.heroi.nivel or 1  # retroativo: +1 por nível
                self.heroi.hp_atual += self.heroi.nivel or 1
            self.eventos.append(f"⭐ Nível {nivel}: {escolha.capitalize()} sobe para {atributos[escolha]}.")
        elif tipo == "talento":
            self.w_state.talentos = [*self.w_state.talentos, escolha]
            t = talents.talento(escolha, self.heroi.classe) or {}
            hp_por_nivel = int(t.get("efeito", {}).get("hp_por_nivel", 0))
            if hp_por_nivel:
                ganho = hp_por_nivel * (self.heroi.nivel or 1)
                self.heroi.hp_max += ganho
                self.heroi.hp_atual += ganho
            self.mods = talents.modificadores(self.w_state.talentos, self.heroi.classe)
            self.eventos.append(f"⭐ Nível {nivel}: talento {t.get('nome', escolha)} — {t.get('descricao', '')}")
        else:  # especializacao
            self.w_state.mundo.especializacoes[str(nivel)] = escolha
            self.eventos.append(f"⭐ Nível {nivel}: especialização {escolha}.")
        self.w_state.niveis_pendentes = [n for n in self.w_state.niveis_pendentes if n != nivel]
        # defesa e dano recalculados com os talentos atuais
        self.heroi.defesa = itens.calcular_defesa(
            self.heroi.atributos or {}, itens.equipamento_de(self.heroi), self.mods.ca
        )
        self.c_state.bonus_especializacao = sum(
            e == "combatente" for e in self.w_state.mundo.especializacoes.values()
        ) + self.mods.dano
        return {"nivel": nivel, "tipo": tipo, "escolha": escolha, "defesa": self.heroi.defesa,
                "pendentes": self.w_state.niveis_pendentes}

    def equipar(self, item: str) -> dict:
        resultado = itens.equipar(self.heroi, item, self.mods.ca)
        if "erro" not in resultado:
            self.eventos.append(f"🛡️ Equipa {resultado['equipado']}. Defesa: {self.heroi.defesa}.")
            if self.c_state.ativo:
                resultado.update(self._resolver_reacao_inimiga())
        return resultado

    def desequipar(self, slot: str) -> dict:
        resultado = itens.desequipar(self.heroi, slot, self.mods.ca)
        if "erro" not in resultado:
            self.eventos.append(f"🛡️ Guarda {resultado['desequipado']}. Defesa: {self.heroi.defesa}.")
        return resultado

    def comerciar(self, npc: str, operacao: str, item: str | None = None) -> dict:
        """Preços são do servidor (`items.preco_compra/venda`), nunca do
        narrador; o NPC precisa estar presente e ter `mercadoria`."""
        if self.c_state.ativo:
            return {"erro": "ninguém negocia no meio de um combate"}
        mundo = self.w_state.mundo
        pessoa = mundo.pessoas.get(npc) or next(
            (p for p in mundo.pessoas.values() if p.nome.strip().lower() == npc.strip().lower()), None
        )
        if pessoa is None or pessoa.local != self.w_state.local or pessoa.disposicao == "ausente":
            return {"erro": f"'{npc}' não está aqui"}
        if not pessoa.mercadoria:
            return {"erro": f"{pessoa.nome} não tem nada para vender nem compra nada"}
        vitrine: list[dict[str, Any]] = [
            {"item": n, "preco": itens.preco_compra(
                (itens.ficha(n) or {}).get("preco", 0), pessoa.confianca, self.mods.desconto
            )}
            for n in pessoa.mercadoria
        ]
        if operacao == "listar":
            return {"vitrine": vitrine, "ouro": self.heroi.ouro}
        if not item:
            return {"erro": "diga qual item"}
        if operacao == "comprar":
            oferta = next((v for v in vitrine if v["item"].lower() == item.lower()), None)
            if oferta is None:
                return {"erro": f"{pessoa.nome} não vende '{item}'", "vitrine": vitrine}
            if self.heroi.ouro < oferta["preco"]:
                return {"erro": f"ouro insuficiente: {oferta['item']} custa {oferta['preco']}, tem {self.heroi.ouro}"}
            self.heroi.ouro -= oferta["preco"]
            self.heroi.inventario = [*self.heroi.inventario, oferta["item"]]
            self.eventos.append(f"💰 Compra {oferta['item']} de {pessoa.nome} por {oferta['preco']} de ouro.")
            self.eventos.append(f"🎁 {self.heroi.nome} recebe: {oferta['item']}.")
            return {"comprado": oferta["item"], "preco": oferta["preco"], "ouro_restante": self.heroi.ouro}
        if operacao == "vender":
            real = itens.resolver_nome(item, self.heroi.inventario)
            if real is None:
                return {"erro": f"'{item}' não está no inventário"}
            valor = itens.preco_venda((itens.ficha(real, self.w_state.itens_inventados) or {}).get("preco", 0))
            inventario = list(self.heroi.inventario)
            inventario.remove(real)
            self.heroi.inventario = inventario
            eq = itens.equipamento_de(self.heroi)
            for slot in ("arma", "armadura", "escudo"):
                if getattr(eq, slot) == real and real not in inventario:
                    itens.desequipar(self.heroi, slot)
            self.heroi.ouro += valor
            self.eventos.append(f"💰 Vende {real} a {pessoa.nome} por {valor} de ouro.")
            return {"vendido": real, "preco": valor, "ouro_restante": self.heroi.ouro}
        return {"erro": "operacao precisa ser listar, comprar ou vender"}

    def gastar_ouro(self, qtd: int) -> dict:
        if qtd < 0:
            return {"erro": "quantidade não pode ser negativa"}
        if self.heroi.ouro < qtd:
            return {"erro": f"ouro insuficiente: tem {self.heroi.ouro}, precisa de {qtd}"}
        self.heroi.ouro -= qtd
        self.eventos.append(f"💰 Gasta {qtd} de ouro. Restam {self.heroi.ouro}.")
        return {"ouro_restante": self.heroi.ouro}

    def ajustar_reputacao_npc(self, npc: str, delta: int, motivo: str = "") -> dict:
        """Reputação por NPC (Etapa 5) — cumpre a promessa da bíblia do
        mestre ("NPCs têm memória"). `delta` é clampado por chamada e o
        valor acumulado é clampado no total: o modelo propõe a direção e a
        intensidade aproximada, o servidor decide o número final (mesmo
        espírito de `gastar_ouro`). Só alimenta a narrativa — não existe
        motor de preço de loja, é escopo explicitamente fora desta etapa."""
        delta_clampado = max(-10, min(10, delta))
        atual = self.heroi.reputacao_npcs.get(npc, 0)
        novo = max(-100, min(100, atual + delta_clampado))
        self.heroi.reputacao_npcs = {**self.heroi.reputacao_npcs, npc: novo}
        self.eventos.append(f"🤝 Reputação com {npc}: {atual:+d} → {novo:+d} ({motivo or 'sem motivo informado'}).")
        return {"npc": npc, "reputacao": novo}

    def iniciar_combate(self, inimigos: list[str], cenario: str | None = None) -> dict:
        if self.c_state.ativo:
            return {"erro": "já há um combate ativo"}
        novo, eventos, dano_surpresa = combat.iniciar_combate(
            inimigos, self.heroi.atributos, self.heroi.defesa, self.rng, nivel_heroi=self._nivel()
        )
        from app.services.encounters import preparar_encontro

        preparar_encontro(novo, self.w_state, cenario)
        for campo in type(novo).model_fields:
            setattr(self.c_state, campo, getattr(novo, campo))
        # Fase 3 da revisão de gameplay — companheiros já recrutados
        # (roster persistente, `self.heroi.aliados`) entram em toda luta
        # nova, com o HP que trouxeram da última — um que morreu (hp 0)
        # não volta. Estatísticas de combate (CA/ataque/dano) são fixas de
        # primeira passada, ver as constantes da classe.
        self.c_state.aliados = [
            Aliado(
                nome=a["nome"], hp=a["hp"], max_hp=a["hp_max"], ca=self.CA_ALIADO_PADRAO,
                bonus_ataque=self.BONUS_ATAQUE_ALIADO_PADRAO, dano_dado=self.DANO_ALIADO_PADRAO,
                nome_ataque="Ataque",
            )
            for a in (self.heroi.aliados or [])
            if a["hp"] > 0
        ]
        self.eventos.extend(eventos)
        if dano_surpresa:
            self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano_surpresa)
        return {"inimigos": [i.nome for i in self.c_state.inimigos], "dano_surpresa": dano_surpresa}

    def atualizar_missao(self, nome: str, objetivo: str) -> dict:
        self.q_state.nome_missao = nome
        self.q_state.objetivo_missao = objetivo
        self.eventos.append(f"📜 Missão atualizada: {nome} - {objetivo}")
        return {"missao": nome, "objetivo": objetivo}

    # Fase 3 da revisão de gameplay (Etapa 12/13, ADR-0027) — estatísticas
    # de combate de um aliado recrutado são fixas, não propostas pelo
    # modelo (mesmo princípio de `_conceder_xp`: o LLM decide O QUÊ, nunca
    # O QUANTO). Primeira passada; ajustar depois com `evals/simulador.py`.
    CA_ALIADO_PADRAO = 12
    BONUS_ATAQUE_ALIADO_PADRAO = 2
    DANO_ALIADO_PADRAO = "1d6"
    HP_ALIADO_MIN = 4
    HP_ALIADO_MAX = 20

    def recrutar_aliado(self, nome: str, classe: str, hp: int, raca: str = "Humano") -> dict:
        aliados = self.heroi.aliados or []
        if any(a["nome"] == nome for a in aliados):
            return {"erro": f"'{nome}' já é um aliado"}
        hp_clampado = max(self.HP_ALIADO_MIN, min(self.HP_ALIADO_MAX, hp))
        if raca not in regras.get_races_list():
            raca = "Humano"  # retrato no palco vem de /assets/races/<raca>.png (Fase 2)
        registro = {
            "nome": nome, "classe": classe, "raca": raca, "hp": hp_clampado, "hp_max": hp_clampado,
            "lealdade": 50, "inventario": [],
        }
        self.heroi.aliados = [*aliados, registro]
        self.eventos.append(f"🤝 {nome} ({classe}) se junta a você.")
        if self.c_state.ativo:
            self.c_state.aliados = [
                *self.c_state.aliados,
                Aliado(
                    nome=nome, hp=hp_clampado, max_hp=hp_clampado, ca=self.CA_ALIADO_PADRAO,
                    bonus_ataque=self.BONUS_ATAQUE_ALIADO_PADRAO, dano_dado=self.DANO_ALIADO_PADRAO,
                    nome_ataque="Ataque",
                ),
            ]
        return {"nome": nome, "classe": classe, "hp": hp_clampado}

    def atacar_com_aliado(self, aliado: str, alvo: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de atacar_com_aliado"}
        aliado_obj = next((a for a in self.c_state.aliados if a.nome == aliado and a.hp > 0), None)
        if aliado_obj is None:
            return {"erro": f"'{aliado}' não é um aliado vivo neste combate"}
        eventos = combat.turno_aliado(self.c_state, aliado_obj, alvo, self.rng)
        self.eventos.extend(eventos)
        if all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            resultado_xp = self._conceder_xp(self.c_state.inimigos)
            return {"resultado": "vitoria", **resultado_xp}
        # Simplificação deliberada (ver ADR-0027): o ataque do aliado NÃO
        # aciona a resposta dos inimigos sozinho — o herói ainda tem a
        # própria ação nesta rodada, e é ela (atacar/esquivar/...) que
        # fecha o turno. Chamar só "atacar_com_aliado" sem nenhuma ação do
        # herói deixa os inimigos sem reagir nesta rodada; documentado
        # como lacuna conhecida, não descuido.
        return {"aliado": aliado, "alvo": alvo}

    # -- despacho --------------------------------------------------------

    _DESPACHO: dict[str, Callable] = {}  # preenchido abaixo da classe

    def executar(self, nome: str, args_json: str) -> tuple[dict, bool]:
        """Nunca deixa uma ferramenta malformada (nome inexistente, JSON
        quebrado, argumento errado, ou uma exceção interna) travar o turno —
        vira uma mensagem de erro que volta pro modelo como resultado da
        ferramenta, e ele tem o próximo passo do loop para se corrigir."""
        metodo = self._DESPACHO.get(nome)
        if metodo is None:
            return {"erro": f"ferramenta '{nome}' não existe"}, False
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            return {"erro": f"argumentos de '{nome}' não são um JSON válido"}, False
        if not isinstance(args, dict):
            return {"erro": "argumentos precisam ser um objeto JSON"}, False
        acoes = {"atacar", "investir", "esquivar", "defender", "esconder_se", "fugir",
                 "usar_habilidade", "interagir", "usar_item", "agir_no_mundo", "intervir_conflito",
                 "mover", "descansar"}
        em_combate = self.c_state.ativo
        consome = nome in acoes and not (nome == "agir_no_mundo" and args.get("acao") == "examinar")
        if nome == "equipar":
            consome = em_combate  # trocar de arma no meio da luta custa a ação
        if nome == "aplicar_dano" and em_combate:
            # dano ambiental num inimigo é uma ação de combate como outra qualquer
            nomes_heroi = {"heroi", "herói", "você", "voce", self.heroi.nome.lower()}
            consome = str(args.get("alvo", "")).lower() not in nomes_heroi
        if consome:
            if self._acao_gasta:
                return {"erro": "a ação deste turno já foi resolvida; narre o resultado e aguarde o jogador"}, False
            if self.heroi.hp_atual <= 0:
                return {"erro": "herói inconsciente: aguarde o teste de morte"}, False
        if nome == "encerrar_arco":
            # Fase 4 — uma tentativa por turno: o modelo não fica insistindo.
            if getattr(self, "_arco_tentado", False):
                return {"erro": "já tentou encerrar o arco neste turno; narre e aguarde"}, False
            self._arco_tentado = True
        if nome == "atacar_com_aliado" and args.get("aliado") in self.c_state.aliados_agiram:
            return {"erro": "esse aliado já agiu nesta rodada"}, False
        try:
            resultado = metodo(self, **args)
        except TypeError as e:
            return {"erro": f"argumentos inválidos para '{nome}': {e}"}, False
        except Exception as e:  # ferramenta com bug não pode derrubar o turno
            return {"erro": f"'{nome}' falhou ao executar: {e}"}, False
        if "erro" not in resultado:
            if consome:
                self._acao_gasta = True
                self.c_state.acao_resolvida = True
                from app.services.living_world import avancar_tempo

                minutos = 1 if em_combate else 10
                if nome == "mover" or (nome == "agir_no_mundo" and args.get("acao") == "atravessar"):
                    minutos = 120
                elif nome == "descansar":
                    minutos = 480 if args.get("tipo") == "longo" else 60
                avancar_tempo(self, minutos, atualizar_hora=nome not in {"mover", "descansar"})
            if nome == "atacar_com_aliado":
                self.c_state.aliados_agiram = [*self.c_state.aliados_agiram, args.get("aliado", "")]
        return resultado, "erro" not in resultado


ToolExecutor._DESPACHO = {
    "rolar_teste": ToolExecutor.rolar_teste,
    "atacar": ToolExecutor.atacar,
    "usar_habilidade": ToolExecutor.usar_habilidade,
    "interagir": ToolExecutor.interagir,
    "aplicar_dano": ToolExecutor.aplicar_dano,
    "mover": ToolExecutor.mover,
    "consultar_regra": ToolExecutor.consultar_regra,
    "usar_item": ToolExecutor.usar_item,
    "dar_item": ToolExecutor.dar_item,
    "equipar": ToolExecutor.equipar,
    "escolher_nivel": ToolExecutor.escolher_nivel,
    "desequipar": ToolExecutor.desequipar,
    "comerciar": ToolExecutor.comerciar,
    "gastar_ouro": ToolExecutor.gastar_ouro,
    "ajustar_reputacao_npc": ToolExecutor.ajustar_reputacao_npc,
    "iniciar_combate": ToolExecutor.iniciar_combate,
    "atualizar_missao": ToolExecutor.atualizar_missao,
    "concluir_objetivo": ToolExecutor.concluir_objetivo,
    "esquivar": ToolExecutor.esquivar,
    "defender": ToolExecutor.defender,
    "investir": ToolExecutor.investir,
    "esconder_se": ToolExecutor.esconder_se,
    "fugir": ToolExecutor.fugir,
    "recrutar_aliado": ToolExecutor.recrutar_aliado,
    "atacar_com_aliado": ToolExecutor.atacar_com_aliado,
    "descansar": ToolExecutor.descansar,
}


ToolExecutor._DESPACHO.update(WORLD_DISPATCH)


def sincronizar_aliados(heroi: Personagem, c_state: CombatState) -> None:
    """Fase 3 da revisão de gameplay — o HP de um aliado muda em combate
    (`c_state.aliados`, criado a cada `iniciar_combate`/`recrutar_aliado`),
    mas quem persiste entre turnos e sessões é o roster em
    `Personagem.aliados`. Chamada uma vez por turno, depois que o combate
    já foi resolvido (routers/game.py, logo antes de `heroi.combat_state =
    c_state.model_dump()`) — sem isto, dano recebido pelo aliado "some"
    assim que o turno termina."""
    if not c_state.aliados:
        return
    hp_por_nome = {a.nome: a.hp for a in c_state.aliados}
    heroi.aliados = [
        {**registro, "hp": hp_por_nome.get(registro["nome"], registro["hp"])}
        for registro in (heroi.aliados or [])
    ]


TOOLS_SCHEMA: list[dict] = [*WORLD_TOOLS,
    {
        "type": "function",
        "function": {
            "name": "rolar_teste",
            "description": (
                "Teste de atributo contra CD para qualquer ação arriscada fora de ataque (escalar, esconder," 
                "persuadir, resistir, perceber). Se pode dar errado, chame — nunca decida sozinho."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "atributo": {
                        "type": "string",
                        "enum": ["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"],
                        "description": (
                            "O atributo mais relevante (força: escalar/arrombar; destreza: esconder/equilibrar;" 
                            "carisma: persuadir)."
                        ),
                    },
                    "cd": {
                        "type": "integer",
                        "description": "Classe de Dificuldade: 5=trivial, 10=fácil, 15=médio, "
                        "20=difícil, 25=muito difícil.",
                    },
                    "item_usado": {
                        "type": "string",
                        "description": (
                            "Item/arma do inventário usado de forma criativa no teste. Omita se nenhum se aplica."
                        ),
                    },
                    "motivo": {
                        "type": "string",
                        "description": (
                            "Poucas palavras concretas sobre O QUE está sendo testado (ex: 'resistir ao veneno da" 
                            "aranha'). O jogador vê isso; pode dar vantagem por traço do herói."
                        ),
                    },
                },
                "required": ["atributo", "cd", "motivo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "atacar",
            "description": (
                "Resolve um ataque corpo a corpo ou à distância do herói contra um inimigo vivo do "
                "combate atual. Use sempre que o jogador declarar uma ação de ataque em combate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alvo": {
                        "type": "string",
                        "description": "Nome exato de um inimigo vivo listado no combate atual.",
                    },
                    "arma": {
                        "type": "string",
                        "description": "Arma do inventário. Omita para a primeira arma reconhecida, ou desarmado.",
                    },
                },
                "required": ["alvo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "investir",
            "description": (
                "Investida: menos precisão, mais dano, herói mais exposto até a próxima rodada — o botão de" 
                "risco."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alvo": {
                        "type": "string",
                        "description": "Nome exato de um inimigo vivo listado no combate atual.",
                    },
                    "arma": {
                        "type": "string",
                        "description": "Arma do inventário. Omita para a primeira arma reconhecida, ou desarmado.",
                    },
                },
                "required": ["alvo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "esquivar",
            "description": (
                "Não ser atingido em vez de atacar: ataques inimigos contra o herói com desvantagem até a próxima" 
                "rodada."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "defender",
            "description": "Postura defensiva (+2 na CA até a próxima rodada) em vez de atacar; recupera Foco.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "esconder_se",
            "description": (
                "Sumir de vista (teste de Destreza) em vez de agir: em sucesso, os inimigos não o alvejam na" 
                "próxima rodada."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recrutar_aliado",
            "description": (
                "Um NPC se junta de verdade ao grupo e passa a acompanhar e lutar ao lado do herói. Não use para" 
                "ajuda de passagem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do NPC recrutado."},
                    "classe": {"type": "string", "description": "Papel ou classe dele (ex: 'Batedor', 'Clérigo')."},
                    "hp": {
                        "type": "integer",
                        "description": "PV inicial aproximado, condizente com a cena (ex: 8 a 15 para um NPC comum).",
                    },
                    "raca": {"type": "string", "description": "Raça do catálogo (Humano, Elfo, Anão...)."},
                },
                "required": ["nome", "classe", "hp"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "atacar_com_aliado",
            "description": (
                "Ataque de um aliado recrutado contra um inimigo vivo. Não substitui a ação do herói — chame" 
                "também a ferramenta da ação dele para fechar a rodada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "aliado": {"type": "string", "description": "Nome exato de um aliado vivo no combate atual."},
                    "alvo": {
                        "type": "string",
                        "description": "Nome exato de um inimigo vivo. Omita para o aliado escolher.",
                    },
                },
                "required": ["aliado"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fugir",
            "description": (
                "Escapar do combate (teste de Destreza): sucesso encerra sem vitória nem derrota; falha dá uma" 
                "rodada de ataque livre aos inimigos."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aplicar_dano",
            "description": (
                "Dano que NÃO é ataque com arma: queda, armadilha, fogo, veneno, magia ambiental. Você propõe o" 
                "dado (queda de 3 m '1d6', fogueira '2d6'); o servidor rola. Em combate, contra inimigo, gasta a" 
                "ação."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alvo": {
                        "type": "string",
                        "description": "'heroi', ou o nome exato de um inimigo vivo no combate atual.",
                    },
                    "dado_dano": {"type": "string", "description": "Notação de dado, ex: '1d6', '2d6+2'."},
                    "motivo": {"type": "string", "description": "Causa do dano, ex: 'queda', 'fogueira', 'veneno'."},
                },
                "required": ["alvo", "dado_dano"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mover",
            "description": (
                "Leva o herói a outro local (nunca em combate). Se o nome não bater, o servidor devolve os locais" 
                "válidos. Local NOVO: passe descricao_proposta e ele passa a existir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destino": {"type": "string", "description": "Nome do local de destino."},
                    "descricao_proposta": {
                        "type": "string",
                        "description": "Só para destino NOVO: descrição curta do lugar, para registrá-lo no mundo.",
                    },
                },
                "required": ["destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_regra",
            "description": (
                "Busca uma regra na bíblia. Chame SEMPRE que o jogador perguntar como uma mecânica funciona," 
                "mesmo fora do personagem — nunca responda de memória."
            ),
            "parameters": {
                "type": "object",
                "properties": {"termo": {"type": "string", "description": "Palavra-chave da regra buscada."}},
                "required": ["termo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "usar_item",
            "description": "Usa um item que já está no inventário do herói (poção, pergaminho, ferramenta).",
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string", "description": "Nome exato do item no inventário."}},
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "descansar",
            "description": (
                "Recupera PV. 'curto': parcial, quase em qualquer lugar. 'longo': tudo, só em local seguro e não" 
                "repetido cedo demais. Nunca em combate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["curto", "longo"], "description": "Tipo de descanso."},
                },
                "required": ["tipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dar_item",
            "description": (
                "Adiciona um item ao inventário do herói — recompensa de combate, saque encontrado, "
                "presente de um NPC. Use quando a cena claramente entrega um item novo ao jogador."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Nome do item a entregar."},
                    "descricao": {
                        "type": "string",
                        "description": "Só para item FORA do catálogo: o que ele é, em uma frase.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "enum": [
                            "Fogo", "Luz", "Sagrado", "Utilidade", "Cura", "Foco", "Veneno", "Gelo", "Leve", "Pesada",
                            "Afiado", "Arcano"
                        ]},
                        "description": "Só para item FORA do catálogo: até 3 tags; é o único poder que ele terá.",
                    },
                },
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gastar_ouro",
            "description": "Debita ouro do herói — compra, suborno, pagamento de taxa. Falha se não houver saldo.",
            "parameters": {
                "type": "object",
                "properties": {"qtd": {"type": "integer", "description": "Quantidade de ouro a gastar."}},
                "required": ["qtd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ajustar_reputacao_npc",
            "description": (
                "Registra que o herói foi notavelmente rude, ameaçador, generoso ou gentil com um NPC nomeado —" 
                "só quando o tom muda a relação de verdade. O NPC lembra em cenas futuras."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "npc": {"type": "string", "description": "Nome exato do NPC."},
                    "delta": {
                        "type": "integer",
                        "description": "-10 a 10, proporcional (insulto leve -2, ameaça grave -8, presente +5).",
                    },
                    "motivo": {"type": "string", "description": "O que o herói fez, em poucas palavras."},
                },
                "required": ["npc", "delta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "iniciar_combate",
            "description": (
                "Cria o combate assim que a ameaça fica hostil (não espere 'eu ataco'). Inimigos são nomes do" 
                "bestiário OU nomes narrativos próprios — o servidor escolhe a ficha real por trás do nome."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "inimigos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Nomes dos inimigos: exatos do bestiário ('Goblin') ou narrativos ('Lobo Alfa de Vharn')" 
                            "— a ficha vem de um arquétipo real do nível certo."
                        ),
                    },
                    "cenario": {
                        "type": "string", "enum": ["duelo", "emboscada", "ritual", "resgate", "cerco", "cacada"],
                        "description": "Tipo coerente com a cena; ritual e resgate só quando já existem na história.",
                    },
                },
                "required": ["inimigos"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_missao",
            "description": (
                "Atualiza a missão ativa no diário de missões (Quest Log) do jogador. Use quando um "
                "NPC der uma nova tarefa, ou quando o objetivo da missão atual mudar ou for completado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "O título curto e claro da missão (ex: 'Resgatar o Ferreiro').",
                    },
                    "objetivo": {
                        "type": "string",
                        "description": (
                            "O que o jogador deve fazer agora "
                            "(ex: 'Encontre o esconderijo dos goblins na floresta')."
                        ),
                    },
                },
                "required": ["nome", "objetivo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "concluir_objetivo",
            "description": (
                "XP por objetivo cumprido sem combate (enigma, NPC convencido, missão por diplomacia). Uma vez" 
                "por objetivo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "objetivo": {
                        "type": "string",
                        "description": "O que foi cumprido (ex: 'Convenceu o guarda a abrir o portão').",
                    },
                },
                "required": ["objetivo"],
            },
        },
    },
]

TOOLS_SCHEMA.extend([
    {
        "type": "function", "function": {
            "name": "usar_habilidade",
            "description": (
                "Técnica da classe (id do painel). O servidor valida nível, Foco e alvo e resolve efeitos. Uma" 
                "ação por turno; não use aplicar_dano para simular magias."
            ),
            "parameters": {"type": "object", "properties": {
                "habilidade": {"type": "string", "description": "ID exato da habilidade da classe."},
                "alvo": {"type": "string", "description": "Nome exato do inimigo; omita para área ou apoio."},
            }, "required": ["habilidade"]},
        },
    },
    {
        "type": "function", "function": {
            "name": "interagir",
            "description": "Usa uma interação do cenário listada no estado; custa a ação e causa reação inimiga.",
            "parameters": {"type": "object", "properties": {
                "interacao": {"type": "string", "description": "ID exato da interação disponível no cenário."},
            }, "required": ["interacao"]},
        },
    },
])


TOOLS_SCHEMA.extend([
    {
        "type": "function",
        "function": {
            "name": "equipar",
            "description": (
                "Equipa arma, armadura ou escudo que está no inventário; o servidor decide o slot e "
                "recalcula a Defesa. Em combate custa a ação."
            ),
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string", "description": "Nome do item no inventário."}},
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desequipar",
            "description": "Tira o que está num slot (arma, armadura ou escudo). Fora de combate.",
            "parameters": {
                "type": "object",
                "properties": {"slot": {"type": "string", "enum": ["arma", "armadura", "escudo"]}},
                "required": ["slot"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comerciar",
            "description": (
                "Compra, venda ou vitrine com um NPC presente que tenha mercadoria. Preços são do "
                "servidor — nunca narre preço antes de chamar. Nunca em combate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "npc": {"type": "string", "description": "id ou nome da pessoa registrada."},
                    "operacao": {"type": "string", "enum": ["listar", "comprar", "vender"]},
                    "item": {"type": "string", "description": "Item a comprar (da vitrine) ou vender (do inventário)."},
                },
                "required": ["npc", "operacao"],
            },
        },
    },
])


# Fase 0 do plano "jogo completo" (08/09/2026) — ferramentas por estado.
#
# Achado ao vivo: a chave do Groq no plano gratuito tem teto de 8.000
# tokens POR MINUTO no modelo principal, e uma chamada de turno com as 30
# ferramentas (~7k tokens só de schema) mais o prompt (~3-4k) não cabe em
# nenhuma. O Mundo Vivo acrescentou 8 ferramentas e um bloco de prompt, e
# foi o que empurrou o turno para além do teto: todo turno caía no Gemini,
# que estoura 429 no laço de 6 passos, e a narrativa voltava vazia.
#
# Mandar só o que faz sentido no estado atual corta ~40% em combate e
# ~25% fora dele, e ainda tira do modelo a tentação de `mover` no meio da
# luta ou `atacar` numa conversa. `_DESPACHO` continua completo — o filtro
# é só do que o NARRADOR enxerga; `/game/action` chama o que quiser.
_SO_EM_COMBATE = {
    "atacar", "investir", "esquivar", "defender", "esconder_se", "fugir",
    "usar_habilidade", "interagir", "atacar_com_aliado",
}
_SO_FORA_DE_COMBATE = {
    "comerciar", "desequipar", "abrir_arco", "encerrar_arco",
    "mover", "descansar", "iniciar_combate", "recrutar_aliado", "concluir_objetivo",
    "atualizar_missao", "registrar_cena", "registrar_pessoa", "registrar_conflito",
    "intervir_conflito", "definir_objetivo", "registrar_vinculo", "gastar_ouro",
    "consultar_regra", "ajustar_reputacao_npc",
}
# Decisões do JOGADOR nunca são ferramenta do narrador (o painel e
# `/game/action` são o único caminho) — mesma regra que a Fase 3 aplica ao
# level-up.
_NUNCA_PARA_O_NARRADOR = {"escolher_especializacao", "escolher_nivel"}


def tools_para(c_state: CombatState) -> list[dict]:
    """Subconjunto de `TOOLS_SCHEMA` que o narrador recebe neste turno."""
    ocultas = _NUNCA_PARA_O_NARRADOR | (_SO_FORA_DE_COMBATE if c_state.ativo else _SO_EM_COMBATE)
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] not in ocultas]
