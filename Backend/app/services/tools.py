"""As ferramentas que o modelo pode chamar (Etapa 4, ADR-0007) — o
substituto do `comando_combate`/`inimigos_sugeridos`/`spawn_battle` em JSON
solto da Etapa 3. O modelo continua só PROPONDO (ADR-0006); quem decide
número é sempre `rules_engine.py`/`combat.py`, chamados daqui.

`TOOLS_SCHEMA` é o `tools=[...]` mandado pro SDK da Groq. `ToolExecutor` liga
cada nome de ferramenta ao estado real de um turno (`heroi`, `c_state`,
`w_state`) e devolve, para cada chamada, um par (resultado para o modelo,
sucesso) — nunca deixa uma ferramenta malformada derrubar o turno inteiro."""

import json
import logging
import random
import re
from collections.abc import Callable

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo, LocalDescoberto, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.services import class_abilities as classes
from app.services import combat, talents, turnos
from app.services import items as itens
from app.services import rules_engine as motor
from app.services.class_abilities import limite_foco, perfil_classe
from app.services.loot import gerar_loot
from app.services.world_tools import WORLD_DISPATCH, WORLD_TOOLS

logger = logging.getLogger(__name__)


def alcance_do_ataque(heroi: Personagem, arma: str | None = None) -> str:
    """"corpo", "distancia" ou "ambos" para o ataque básico do herói com a
    arma pedida (ou a equipada). Conjurador sem arma na mão ataca de longe."""
    if arma is None and heroi.classe in combat.CONJURADORES:
        return "distancia"  # o pulso mágico/sagrado atravessa a cena
    if arma is None and heroi.classe == "Monge":
        return "corpo"
    _, dados = combat.escolher_arma(heroi.inventario or [], arma, (heroi.equipamento or {}).get("arma"))
    return turnos.alcance_da_arma(dados.get("propriedades", []))


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
        self.turno_passou = False  # combate v2: a fila andou neste request
        # Toda luta é do motor de turnos: um estado antigo (save anterior ao
        # combate v2) é convertido aqui, antes de qualquer ferramenta.
        turnos.migrar_combate(c_state)
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
        alvo, vantagem, erro = self._mirar(alvo, arma)
        if erro:
            return {"erro": erro}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel(),
            vantagem=vantagem,
            classe=self.heroi.classe,
            arma_equipada=(self.heroi.equipamento or {}).get("arma"),
            dano_extra=self._dano_de_classe(alvo, vantagem),
        )
        self.eventos.extend(eventos)

        if all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            return self._fechar_vitoria()

        return {}

    def _recuperar_foco(self, quantidade: int) -> None:
        self.c_state.foco_max = limite_foco(self._nivel(), self.heroi.classe)
        antes = self.c_state.foco
        self.c_state.foco = min(self.c_state.foco_max, antes + quantidade)
        if self.c_state.foco > antes:
            self.eventos.append(f"🔹 Recupera {self.c_state.foco - antes} Foco.")

    def _fechar_vitoria(self, mensagem: str = "🏆 Combate vencido!") -> dict:
        """Ponto único de vitória por inimigos derrotados. Antes, `atacar`,
        `investir`, `atacar_com_aliado` e o terreno fechavam a luta cada um
        por conta própria e só `_verificar_vitoria` avisava o arco — um chefe
        morto por ataque básico nunca contava como enfrentado."""
        from app.services.living_world import marcar_chefe_enfrentado

        self.c_state.ativo = False
        self.c_state.resultado = "vitoria"
        self.eventos.append(mensagem)
        if self.c_state.chefe_do_arco:
            marcar_chefe_enfrentado(self.w_state)
        return {"resultado": "vitoria", **self._conceder_xp(self.c_state.inimigos)}

    def _verificar_vitoria(self) -> dict:
        if self.c_state.ativo and all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            return self._fechar_vitoria()
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
            return {"erro": "Foco insuficiente: defender recupera 1; descansar recupera mais"}
        vivos = [i for i in self.c_state.inimigos if i.hp > 0 and not i.afastado]
        if tecnica["alvo"] == "inimigo":
            escolhido = next((i for i in vivos if i.nome == alvo), None)
            if escolhido is None:
                return {"erro": "escolha um inimigo vivo pelo nome exato"}
            if tecnica.get("alcance") == "corpo":
                erro = self._alcancar(escolhido)
                if erro:
                    return {"erro": erro}
            alvos = [escolhido]
        else:
            alvos = vivos if tecnica["alvo"] == "todos" else []
        self.c_state.foco -= tecnica["custo"]
        self.eventos.append(f"✦ {tecnica['nome']}! Custa {tecnica['custo']} Foco.")
        # O efeito no herói perde um turno no fim do turno em que foi
        # lançado; +1 para durar o que a ficha da técnica promete.
        extra = 1
        for efeito in ("furia", "protecao", "guarda", "esquiva", "precisao"):
            if tecnica.get(efeito):
                self.c_state.efeitos_heroi[efeito] = tecnica[efeito] + extra
        atributo = perfil["atributo"]
        mod = max(0, motor.calcular_modificador(self.heroi.atributos.get(atributo, 10)))
        dano_total = 0
        for inimigo in alvos:
            rolado = motor.calcular_dano(tecnica["dano"], rng=self.rng)
            if self.heroi.classe == "Feiticeiro":
                rolado = max(rolado, motor.calcular_dano(tecnica["dano"], rng=self.rng))  # magia potencializada
            dano = rolado + mod + self._nivel() // 2 + self.c_state.bonus_especializacao
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
                if tecnica.get(efeito) and inimigo.hp > 0 and self._efeito_pega(inimigo, efeito, tecnica["nome"], mod):
                    inimigo.efeitos[efeito] = tecnica[efeito]
            if inimigo.hp == 0:
                self.eventos.append(EventoRolagem(
                    f"💀 {inimigo.nome} cai.", EventoStatus(tipo="morte_inimigo", quem=inimigo.nome)
                ))
        cura = tecnica.get("cura_fixa", 0)
        if tecnica.get("cura"):
            cura += motor.calcular_dano(tecnica["cura"], rng=self.rng) + mod
            cura += self._nivel()  # a cura acompanha o nível, como o dano dos monstros
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
                **vitoria}

    def interagir(self, interacao: str) -> dict:
        from app.services.encounters import interagir_cenario

        return interagir_cenario(self, interacao)

    # Fase 1 da revisão de gameplay (Etapa 12/13) — CD das ações táticas
    # que envolvem teste (esconder_se, fugir). Valor de primeira passada:
    # ajustar com `evals/simulador.py`, não chutar de novo.
    CD_ACAO_TATICA = 12

    @property
    def _cd_acao_tatica(self) -> int:
        return motor.ajustar_cd_por_dificuldade(self.CD_ACAO_TATICA, self.heroi.dificuldade)

    def esquivar(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de esquivar"}
        self.c_state.heroi_vantagem_inimiga = False
        self.eventos.append("Você se esquiva, atento a qualquer ataque.")
        return {"acao": "esquivar"}

    def defender(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de defender"}
        self.c_state.heroi_bonus_ca = 2
        # O Foco não enche sozinho; defender é o jeito de recuperar um
        # pouco no meio da luta, trocando a ação por fôlego.
        self._recuperar_foco(1)
        self.eventos.append("Você assume postura defensiva (+2 na CA).")
        return {"acao": "defender"}

    def investir(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de investir"}
        alvo, vantagem, erro = self._mirar(alvo, arma)
        if erro:
            return {"erro": erro}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel(),
            vantagem=vantagem,
            investida=True,
            classe=self.heroi.classe,
            arma_equipada=(self.heroi.equipamento or {}).get("arma"),
        )
        self.eventos.extend(eventos)
        if all(i.hp <= 0 or i.afastado for i in self.c_state.inimigos):
            return self._fechar_vitoria()
        # A abertura de uma investida custa caro: os inimigos atacam de
        # volta com vantagem até a próxima rodada.
        self.c_state.heroi_vantagem_inimiga = True
        return {"acao": "investir"}

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
        return {"acao": "esconder_se", "escondido": resultado.sucesso}

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
        return {"acao": "fugir", "fugiu": False}

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
        # Só quem caiu rende XP: inimigo que recuou (`afastado`, ainda com PV)
        # encerra a ameaça, mas não é um abate — mesmo critério da contagem
        # do bestiário logo abaixo.
        xp_ganho = sum(
            i.xp or (regras.get_monster(i.arquetipo or i.nome) or {}).get("xp", 0)
            for i in inimigos_derrotados if i.hp <= 0
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
        """Núcleo comum das fontes de XP: vitória em combate (`_conceder_xp`),
        passo cumprido da trilha (`capitulo.conferir_passo`), conflito
        resolvido e fim de capítulo. Todas sobem de nível pela mesma lógica."""
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
        self.c_state.foco_max = limite_foco(self._nivel(), self.heroi.classe)
        return {"xp_ganho": xp_ganho, "xp_total": self.heroi.xp, "nivel": self.heroi.nivel}

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
        return resultado

    # Fase 6 da revisão de gameplay (Etapa 12/13) — janela mínima entre
    # dois descansos longos, em turnos de jogo (não existe relógio de
    # calendário no sistema; "turnos desde o último" é a aproximação de
    # "um dia narrativo" — primeira passada, como o resto dos números
    # novos desta revisão).
    LIMITE_TURNOS_DESCANSO_LONGO = 8

    # Combate v2 (ADR-0042): dois descansos curtos entre um longo e outro.
    MAX_DESCANSOS_CURTOS = 2

    def _local_seguro(self) -> bool:
        """Catálogo seguro ou abrigo conquistado, inaugurado e ainda acessível."""
        from app.services.instalacoes import disponivel

        if any(i.tipo == "abrigo" and disponivel(self.w_state, i) for i in self.w_state.mundo.instalacoes.values()):
            return True
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
            if self.w_state.descansos_curtos >= self.MAX_DESCANSOS_CURTOS:
                return {"erro": "Você já descansou o que dava; só um descanso longo recupera mais."}
            self.w_state.descansos_curtos += 1
            maximo = limite_foco(self._nivel(), self.heroi.classe)
            ganho = maximo if self.heroi.classe == "Bruxo" else (maximo + 1) // 2
            self.c_state.foco_max = maximo
            self.c_state.foco = min(maximo, self.c_state.foco + ganho)
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
            self.eventos.append(f"🔹 Foco: {self.c_state.foco}/{maximo}.")
            return {"tipo": "curto", "cura": cura, "hp_atual": self.heroi.hp_atual, "foco": self.c_state.foco}

        # tipo == "longo"
        if not self._local_seguro():
            return {"erro": f"'{self.w_state.local}' não é seguro o bastante para um descanso longo"}
        turnos_desde_ultimo = self.w_state.turno - self.w_state.ultimo_descanso_longo
        if turnos_desde_ultimo < self.LIMITE_TURNOS_DESCANSO_LONGO:
            return {"erro": "o grupo descansou recentemente — ainda não é hora de outro descanso longo"}

        cura = self.heroi.hp_max - self.heroi.hp_atual
        self.heroi.hp_atual = self.heroi.hp_max
        self.w_state.ultimo_descanso_longo = self.w_state.turno
        self.w_state.descansos_curtos = 0
        self.c_state.foco_max = limite_foco(self._nivel(), self.heroi.classe)
        self.c_state.foco = self.c_state.foco_max
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
            self.eventos.append(f"{resultado['equipado']} equipado. Defesa: {self.heroi.defesa}.")
        return resultado

    def desequipar(self, slot: str) -> dict:
        resultado = itens.desequipar(self.heroi, slot, self.mods.ca)
        if "erro" not in resultado:
            self.eventos.append(f"{resultado['desequipado']} guardado. Defesa: {self.heroi.defesa}.")
        return resultado

    def comerciar(self, npc: str, operacao: str, item: str | None = None) -> dict:
        """Preços são do servidor (`items.preco_compra/venda`), nunca do
        narrador; o NPC precisa estar presente e ter `mercadoria`."""
        from app.services import economia

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
        vitrine = economia.vitrine(pessoa, self.w_state.itens_inventados, self.mods.desconto)
        if operacao == "listar":
            return {"vitrine": vitrine, "ouro": self.heroi.ouro}
        if not item:
            return {"erro": "diga qual item"}
        if operacao == "comprar":
            oferta = next((v for v in vitrine if v["item"].lower() == item.lower()), None)
            if oferta is None:
                return {"erro": f"{pessoa.nome} não vende '{item}'", "vitrine": vitrine}
            if oferta["quantidade"] <= 0:
                return {"erro": f"{oferta['item']} está esgotado; procure outro fornecedor ou uma entrega."}
            if self.heroi.ouro < oferta["preco"]:
                return {"erro": f"ouro insuficiente: {oferta['item']} custa {oferta['preco']}, tem {self.heroi.ouro}"}
            estoque = economia.estoque_atual(pessoa)
            estoque[oferta["item"]] -= 1
            economia.fixar_estoque(pessoa, estoque)
            self.heroi.ouro -= oferta["preco"]
            self.heroi.inventario = [*self.heroi.inventario, oferta["item"]]
            self.eventos.append(f"💰 Compra {oferta['item']} de {pessoa.nome} por {oferta['preco']} de ouro.")
            self.eventos.append(f"🎁 {self.heroi.nome} recebe: {oferta['item']}.")
            return {"comprado": oferta["item"], "preco": oferta["preco"], "ouro_restante": self.heroi.ouro}
        if operacao == "vender":
            real = itens.resolver_nome(item, self.heroi.inventario)
            if real is None:
                return {"erro": f"'{item}' não está no inventário"}
            estoque = economia.estoque_atual(pessoa)
            if real not in estoque and len(estoque) >= economia.LIMITE_ITENS:
                return {"erro": "O comerciante não tem espaço para mais tipos de mercadoria."}
            valor = itens.preco_venda((itens.ficha(real, self.w_state.itens_inventados) or {}).get("preco", 0))
            inventario = list(self.heroi.inventario)
            inventario.remove(real)
            self.heroi.inventario = inventario
            eq = itens.equipamento_de(self.heroi)
            for slot in ("arma", "armadura", "escudo"):
                if getattr(eq, slot) == real and real not in inventario:
                    itens.desequipar(self.heroi, slot)
            estoque[real] = estoque.get(real, 0) + 1
            economia.fixar_estoque(pessoa, estoque)
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

    def iniciar_combate(self, inimigos: list[str], cenario: str | None = None, chefe: bool = False) -> dict:
        if self.c_state.ativo:
            return {"erro": "já há um combate ativo"}
        from app.services.living_world import arco_ativo

        arco = arco_ativo(self.w_state.mundo)
        reservado = arco.chefe if (chefe and arco is not None and arco.chefe and not arco.chefe_enfrentado) else None
        novo, eventos, dano_surpresa = combat.iniciar_combate(
            inimigos, self.heroi.atributos, self.heroi.defesa, self.rng, nivel_heroi=self._nivel(),
            chefe_reservado=reservado,
        )
        novo.chefe_do_arco = reservado is not None
        from app.services.encounters import preparar_encontro

        preparar_encontro(novo, self.w_state, cenario)
        # Combate v2 (ADR-0042): o Foco é um recurso da jornada, não da luta.
        # O que sobrou da luta anterior é o que há agora; só descanso repõe.
        novo.foco_max = limite_foco(self._nivel(), self.heroi.classe)
        # Antes da primeira luta no motor novo (herói recém-criado ou save
        # antigo) não há "o que sobrou": começa cheio.
        ja_lutou = self.c_state.versao >= 2
        novo.foco = min(novo.foco_max, max(0, self.c_state.foco)) if ja_lutou else novo.foco_max
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
        if not self.c_state.ativo:
            return {"inimigos": [], "dano_surpresa": 0}
        # Combate v2: todos rolam iniciativa e quem é mais rápido que o
        # herói age antes do primeiro turno dele. Em emboscada já começam colados.
        alvo = self._alvo()
        self.eventos.extend(
            turnos.abrir(self.c_state, alvo, self.rng, perto=self.c_state.cenario_id == "emboscada")
        )
        dano_surpresa = self.heroi.hp_atual - alvo.hp
        self.heroi.hp_atual = alvo.hp
        return {"inimigos": [i.nome for i in self.c_state.inimigos], "dano_surpresa": dano_surpresa,
                **self._verificar_vitoria()}

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
        return self._comandar(aliado_obj, alvo)

    # -- combate v2: economia do turno, distância e fila ------------------

    def _alvo(self) -> "turnos.Alvo":
        classe = self.heroi.classe
        return turnos.Alvo(
            hp=self.heroi.hp_atual, ca=self.heroi.defesa + classes.defesa_de_classe(classe, self._nivel()),
            atributos=self.heroi.atributos or {}, nivel=self._nivel(),
            bonus_resistencia=classes.BONUS_RESISTENCIA.get(classe, 0),
        )

    def _alcancar(self, inimigo: Inimigo) -> str | None:
        """Chega ao corpo a corpo, gastando o movimento se ele está livre.
        Devolve a mensagem de erro quando não dá."""
        c = self.c_state
        if inimigo.distancia == "perto":
            return None
        preso = self._preso()
        if c.movimento_usado or preso or c.efeitos_heroi.get("amedrontado", 0):
            return preso or f"{inimigo.nome} está longe: aproxime-se antes, ou use um ataque à distância."
        c.movimento_usado = True
        self.eventos.extend(turnos.aproximar(c, inimigo))
        return None

    def _dano_de_classe(self, alvo: str, vantagem: bool | None) -> str | None:
        """Ataque furtivo do Ladino: com vantagem, ou contra quem já está
        sob algum efeito."""
        if self.heroi.classe != "Ladino":
            return None
        inimigo = self._inimigo_vivo(alvo)
        com_vantagem = vantagem is True or bool(self.c_state.efeitos_heroi.get("precisao", 0))
        return "1d6" if inimigo is not None and (com_vantagem or inimigo.efeitos) else None

    def _efeito_pega(self, inimigo: Inimigo, efeito: str, tecnica: str, mod: int) -> bool:
        """Efeito de controle de uma técnica só entra se o alvo falhar na
        resistência (CD 8 + proficiência + atributo da classe). Marcar não
        pede teste. No motor antigo, tudo entrava sempre."""
        tipo = classes.RESISTENCIA_DO_EFEITO.get(efeito)
        if tipo is None:
            return True
        cd = 8 + motor.bonus_proficiencia(self._nivel()) + mod + classes.BONUS_CD.get(self.heroi.classe, 0)
        r = turnos.resistir_inimigo(inimigo, tipo, cd, self.rng)
        self.eventos.append(EventoRolagem(
            f"🎲 {inimigo.nome} resiste a {tecnica}? d20({r.rolagem})+{r.bonus}={r.total} vs CD {cd} → "
            f"{'RESISTIU' if r.sucesso else 'NÃO RESISTIU'}.",
            DadosRolagem(tipo="resistencia", quem=inimigo.nome, ator="heroi", alvo=inimigo.nome, alvo_id=inimigo.id,
                         d20=r.rolagem, bonus=r.bonus, total=r.total, cd=cd, sucesso=r.sucesso, motivo=tecnica),
        ))
        return not r.sucesso

    def _inimigo_vivo(self, alvo: str | None) -> Inimigo | None:
        """Por id ("i2") ou pelo nome exibido."""
        return next((i for i in turnos.vivos(self.c_state) if alvo and alvo in (i.id, i.nome)), None)

    def _preso(self) -> str | None:
        """Condição que impede o herói de se deslocar agora."""
        efeitos = self.c_state.efeitos_heroi
        if efeitos.get("caido", 0):
            return "Você está caído: levante-se primeiro."
        if efeitos.get("contido", 0):
            return "Você está contido e não consegue se deslocar."
        return None

    def _alcance_do_ataque(self, arma: str | None) -> str:
        return alcance_do_ataque(self.heroi, arma)

    def _mirar(self, alvo: str, arma: str | None) -> tuple[str, bool | None, str | None]:
        """Combate v2: confere o alcance (avançando sozinho se o movimento
        ainda está livre) e soma as desvantagens do herói. Devolve
        (nome do alvo, vantagem, erro). No motor antigo não muda nada."""
        c = self.c_state
        inimigo = self._inimigo_vivo(alvo)
        if inimigo is None:
            return alvo, None, "escolha um inimigo vivo como alvo"
        alcance = self._alcance_do_ataque(arma)
        if alcance == "corpo":
            erro = self._alcancar(inimigo)
            if erro:
                return alvo, None, erro
        vantagem: bool | None = None
        colado = any(i.distancia == "perto" for i in turnos.vivos(c))
        if alcance != "corpo" and inimigo.distancia == "longe" and inimigo.efeitos.get("marcado", 0) \
                and self.heroi.classe == "Patrulheiro":
            vantagem = True  # Caçador: o alvo marcado não escapa da mira
        if alcance == "distancia" and colado:
            vantagem = combat._combinar_vantagem(vantagem, False)  # atirar com um inimigo colado atrapalha
        if any(c.efeitos_heroi.get(e, 0) for e in ("envenenado", "caido", "amedrontado")):
            vantagem = combat._combinar_vantagem(vantagem, False)
        return inimigo.nome, vantagem, None

    def aproximar(self, alvo: str) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo"}
        inimigo = self._inimigo_vivo(alvo)
        if inimigo is None:
            return {"erro": "escolha um inimigo vivo para se aproximar"}
        if inimigo.distancia == "perto":
            return {"erro": f"{inimigo.nome} já está perto."}
        preso = self._preso()
        if preso:
            return {"erro": preso}
        if self.c_state.efeitos_heroi.get("amedrontado", 0):
            return {"erro": "Você está amedrontado e não consegue avançar."}
        self.eventos.extend(turnos.aproximar(self.c_state, inimigo))
        return {"acao": "aproximar", "alvo": inimigo.nome}

    def recuar(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo"}
        if not any(i.distancia == "perto" for i in turnos.vivos(self.c_state)):
            return {"erro": "Nenhum inimigo está perto de você."}
        preso = self._preso()
        if preso:
            return {"erro": preso}
        alvo = self._alvo()
        livre = self.heroi.classe in classes.RECUA_SEM_OPORTUNIDADE
        self.eventos.extend(turnos.recuar(self.c_state, alvo, self.rng, sem_oportunidade=livre))
        dano = self.heroi.hp_atual - alvo.hp
        self.heroi.hp_atual = alvo.hp
        return {"acao": "recuar", "dano_recebido": dano, "hp_atual": self.heroi.hp_atual}

    def levantar(self) -> dict:
        if not self.c_state.efeitos_heroi.get("caido", 0):
            return {"erro": "Você não está caído."}
        self.c_state.efeitos_heroi = {k: v for k, v in self.c_state.efeitos_heroi.items() if k != "caido"}
        self.eventos.append("Você se levanta.")
        return {"acao": "levantar"}

    def encerrar_turno(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo"}
        return {"acao": "encerrar_turno"}

    def _comandar(self, aliado: Aliado, alvo: str | None) -> dict:
        """Ação bônus: aponta um alvo para o aliado. Ele bate na vez dele,
        com vantagem no primeiro golpe."""
        de_pe = turnos.vivos(self.c_state)
        inimigo = self._inimigo_vivo(alvo) or min(de_pe, key=lambda i: (i.hp, i.id), default=None)
        if inimigo is None:
            return {"erro": "não há inimigo de pé para marcar"}
        self.c_state.alvo_marcado, self.c_state.comando = inimigo.id, True
        self.eventos.append(f"📣 Você manda {aliado.nome} mirar em {inimigo.nome}.")
        return {"aliado": aliado.nome, "alvo": inimigo.nome}

    # Improvisar (ADR-0041): a IA escolheu atributo, dificuldade e efeito
    # numa lista fechada; os números e as travas são daqui.
    CD_IMPROVISO = {"facil": 10, "media": 13, "dificil": 16}
    EFEITOS_COM_ALVO = {"dano_leve", "derrubar", "desequilibrar", "empurrar", "intimidar"}

    def improvisar(self, atributo: str, dificuldade: str, efeito: str, alvo: str = "", descricao: str = "") -> dict:
        c = self.c_state
        if not c.ativo:
            return {"erro": "improvisar é uma ação de combate"}
        if atributo not in motor.ATRIBUTOS_VALIDOS or dificuldade not in self.CD_IMPROVISO:
            return {"erro": "julgamento inválido para o improviso"}
        inimigo = self._inimigo_vivo(alvo)
        if efeito in self.EFEITOS_COM_ALVO and inimigo is None:
            inimigo = min(turnos.vivos(c), key=lambda i: (i.distancia != "perto", i.id), default=None)
            if inimigo is None:
                return {"erro": "não há inimigo de pé"}
        # Chefe não cai nem se abala com um truque: o efeito vira abrir a guarda.
        if inimigo is not None and efeito in {"derrubar", "intimidar"} and turnos.e_chefe(inimigo):
            efeito = "desequilibrar"
        if efeito == "empurrar" and inimigo is not None and inimigo.distancia == "longe":
            efeito = "desequilibrar"
        if efeito == "dano_area_leve" and "improviso_area" in c.interacoes_usadas:
            efeito = "dano_leve"  # a área vale uma vez por luta
            inimigo = inimigo or min(turnos.vivos(c), key=lambda i: i.id, default=None)
        # Os dois efeitos mais fortes nunca saem baratos, julgue a IA o que julgar.
        if efeito in {"derrubar", "dano_area_leve"} and dificuldade == "facil":
            dificuldade = "media"
        repetido = efeito != "nada" and efeito == c.improviso_anterior
        cd = motor.ajustar_cd_por_dificuldade(
            self.CD_IMPROVISO[dificuldade] + (3 if repetido else 0), self.heroi.dificuldade
        )
        mod = motor.calcular_modificador(self.heroi.atributos.get(atributo, 10))
        prof = motor.bonus_proficiencia(self._nivel())
        r = motor.resolver_teste_atributo(mod + prof, cd, self.rng)
        self.eventos.append(EventoRolagem(
            f"🎲 Improviso ({atributo}): d20({r.rolagem})+{mod + prof}={r.total} vs CD {cd}"
            f"{' (truque repetido)' if repetido else ''} → {'SUCESSO' if r.sucesso else 'FALHA'}.",
            DadosRolagem(tipo="teste", quem="heroi", ator="heroi", d20=r.rolagem, bonus=mod + prof, total=r.total,
                         cd=cd, sucesso=r.sucesso, atributo=atributo, motivo=descricao.strip()[:120] or "improvisar",
                         partes_bonus=[{"rotulo": motor.ATRIBUTO_LABEL[atributo], "valor": mod},
                                       {"rotulo": "Proficiência", "valor": prof}]),
        ))
        if not r.sucesso:
            c.improviso_anterior = ""
            self.eventos.append("A ideia não funciona; a brecha se fecha.")
            return {"sucesso": False, "efeito": efeito}
        c.improviso_anterior = efeito
        nivel = self._nivel()

        def ferir(quem: Inimigo, dado: str, bonus: int) -> None:
            dano = motor.calcular_dano(dado, rng=self.rng) + bonus
            quem.hp = max(0, quem.hp - dano)
            self.eventos.append(EventoRolagem(
                f"O improviso causa {dano} de dano em {quem.nome}.",
                DadosRolagem(tipo="dano", quem="heroi", ator="heroi", alvo=quem.nome, alvo_id=quem.id, dano=dano),
            ))
            if quem.hp == 0:
                self.eventos.append(EventoRolagem(
                    f"💀 {quem.nome} cai.", EventoStatus(tipo="morte_inimigo", quem=quem.nome)
                ))

        if efeito == "dano_leve" and inimigo is not None:
            ferir(inimigo, "1d6", nivel)
        elif efeito == "dano_area_leve":
            c.interacoes_usadas = [*c.interacoes_usadas, "improviso_area"]
            for quem in turnos.vivos(c):
                ferir(quem, "1d4", nivel // 2)
        elif efeito == "derrubar" and inimigo is not None:
            inimigo.efeitos = {**inimigo.efeitos, "atordoado": 1}
            self.eventos.append(f"{inimigo.nome} perde o equilíbrio e a próxima vez.")
        elif efeito == "desequilibrar" and inimigo is not None:
            inimigo.efeitos = {**inimigo.efeitos, "vulneravel": 2}
            self.eventos.append(f"{inimigo.nome} fica com a guarda aberta.")
        elif efeito == "intimidar" and inimigo is not None:
            inimigo.efeitos = {**inimigo.efeitos, "enfraquecido": 2}
            self.eventos.append(f"{inimigo.nome} hesita e bate mais fraco.")
        elif efeito == "empurrar" and inimigo is not None:
            inimigo.distancia = "longe"
            self.eventos.append(f"{inimigo.nome} é afastado de você.")
        elif efeito == "distrair":
            c.heroi_vantagem_inimiga = False
            self.eventos.append("Os inimigos perdem a mira até o seu próximo turno.")
        elif efeito == "cobertura":
            c.heroi_bonus_ca = 3
            self.eventos.append("Você se protege: mais difícil de acertar até o seu próximo turno.")
        elif efeito == "vantagem":
            c.efeitos_heroi = {**c.efeitos_heroi, "precisao": 2}
            self.eventos.append("Você cria a abertura: seu próximo ataque sai com vantagem.")
        else:
            self.eventos.append("A manobra impressiona, mas não muda a luta.")
        return {"sucesso": True, "efeito": efeito, **self._verificar_vitoria()}

    def _custo_de(self, nome: str, args: dict) -> str | None:
        """O que a ferramenta gasta do turno do herói: "acao", "bonus",
        "movimento", "livre" (encerrar) ou None (não mexe no turno)."""
        if nome in {"aproximar", "recuar", "levantar"}:
            return "movimento"
        if nome == "encerrar_turno":
            return "livre"
        if nome == "atacar_com_aliado":
            return "bonus"
        if nome == "usar_item":
            real = itens.resolver_nome(str(args.get("item", "")), self.heroi.inventario)
            ficha = regras.get_item(real) if real else None
            return "bonus" if ficha and ficha.get("tipo") == "consumivel" else "acao"
        if nome == "usar_habilidade":
            pedido = args.get("habilidade")
            tecnica = next((h for h in perfil_classe(self.heroi.classe)["habilidades"]
                            if pedido in (h["id"], h["nome"])), None)
            return (tecnica or {}).get("acao", "acao")
        if nome == "aplicar_dano":
            nomes_heroi = {"heroi", "herói", "você", "voce", (self.heroi.nome or "").lower()}
            return None if str(args.get("alvo", "")).lower() in nomes_heroi else "acao"
        if nome == "agir_no_mundo":
            return None if args.get("acao") == "examinar" else "acao"
        if nome in {"atacar", "investir", "esquivar", "defender", "esconder_se", "fugir", "interagir", "equipar",
                    "resolver_intencao", "intervir_conflito", "improvisar"}:
            return "acao"
        return None

    def _ha_bonus_util(self) -> bool:
        """Sobrou algo que valha manter o turno aberto pela ação bônus?"""
        c = self.c_state
        ferido = self.heroi.hp_atual < self.heroi.hp_max
        for item in self.heroi.inventario or []:
            ficha = regras.get_item(item) or {}
            if ficha.get("tipo") != "consumivel":
                continue
            efeito = ficha.get("efeito") or {}
            so_cura = set(efeito) <= {"cura"}
            if not so_cura or ferido:
                return True
        marcado = next((i for i in turnos.vivos(c) if i.id == c.alvo_marcado), None)
        if marcado is None and any(a.hp > 0 for a in c.aliados):
            return True
        return any(
            h.get("acao") == "bonus" and h["nivel"] <= self._nivel() and h["custo"] <= c.foco
            for h in perfil_classe(self.heroi.classe)["habilidades"]
        )

    def _ha_movimento_util(self) -> bool:
        """Depois de agir, mover só vale para quem luta de longe (abrir
        distância) ou para quem está no chão (levantar)."""
        c = self.c_state
        if c.efeitos_heroi.get("caido", 0):
            return True
        if self._preso():
            return False
        colado = any(i.distancia == "perto" for i in turnos.vivos(c))
        return colado and self._alcance_do_ataque(None) != "corpo"

    def _turno_acabou(self) -> bool:
        """O turno fecha sozinho quando não sobra nada útil. Antes da ação,
        nunca: o jogador pode querer se mover ou usar o bônus primeiro."""
        c = self.c_state
        if not c.acao_usada:
            return False
        if not c.bonus_usada and self._ha_bonus_util():
            return False
        return c.movimento_usado or not self._ha_movimento_util()

    def _passar_a_vez(self) -> dict:
        """Fecha o turno do herói e anda a fila até ele agir de novo. Se
        ele volta atordoado, a vez passa outra vez."""
        c = self.c_state
        vitoria: dict = {}
        for _ in range(3):
            turnos.encerrar_vez_heroi(c)
            alvo = self._alvo()
            self.eventos.extend(turnos.avancar_fila(c, alvo, self.rng))
            vitoria = self._verificar_vitoria()
            if vitoria or not c.ativo:
                self.heroi.hp_atual = alvo.hp
                break
            self.eventos.extend(turnos.iniciar_vez_heroi(c, alvo))
            if self.heroi.classe == "Bárbaro" and 0 < alvo.hp < self.heroi.hp_atual:
                self._recuperar_foco(1)  # Sangue quente: apanhar alimenta a fúria
            self.heroi.hp_atual = alvo.hp
            perdeu_a_vez = c.acao_usada and c.bonus_usada and c.movimento_usado
            if self.heroi.hp_atual <= 0 or not perdeu_a_vez:
                break
        self.turno_passou = True
        return {"fim_de_turno": True, "hp_atual": self.heroi.hp_atual, **vitoria}

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
                 "mover", "descansar", "resolver_intencao"}
        em_combate = self.c_state.ativo
        consome = nome in acoes and not (nome == "agir_no_mundo" and args.get("acao") == "examinar")
        # Combate v2: o que limita o turno é ação / bônus / movimento, não
        # "uma ferramenta por request".
        custo = self._custo_de(nome, args) if em_combate else None
        if custo is not None:
            if self.heroi.hp_atual <= 0:
                return {"erro": "herói inconsciente: aguarde o teste de morte"}, False
            gasto = _CAMPO_DO_CUSTO.get(custo)
            if gasto and getattr(self.c_state, gasto):
                return {"erro": f"Você já usou {_NOME_DO_CUSTO[custo]} neste turno."}, False
        if nome == "usar_instalacao":
            consome = args.get("operacao") == "preparar"
        if nome == "equipar":
            consome = em_combate  # trocar de arma no meio da luta custa a ação
        if nome == "aplicar_dano" and em_combate:
            # dano ambiental num inimigo é uma ação de combate como outra qualquer
            nomes_heroi = {"heroi", "herói", "você", "voce", self.heroi.nome.lower()}
            consome = str(args.get("alvo", "")).lower() not in nomes_heroi
        if consome and not em_combate:
            if self._acao_gasta:
                return {"erro": "a ação deste turno já foi resolvida; narre o resultado e aguarde o jogador"}, False
            if self.heroi.hp_atual <= 0:
                return {"erro": "herói inconsciente: aguarde o teste de morte"}, False
        if nome == "encerrar_arco":
            # Fase 4 — uma tentativa por turno: o modelo não fica insistindo.
            if getattr(self, "_arco_tentado", False):
                return {"erro": "já tentou encerrar o arco neste turno; narre e aguarde"}, False
            self._arco_tentado = True
        try:
            resultado = metodo(self, **args)
        except TypeError as e:
            return {"erro": f"argumentos inválidos para '{nome}': {e}"}, False
        except Exception:  # ferramenta com bug não pode derrubar o turno
            # Achado da auditoria pré-lançamento: o texto cru da exceção
            # Python voltava pro contexto do modelo (e podia ser
            # parafraseado na narrativa do jogador). Log fica só no
            # servidor; o modelo recebe uma mensagem genérica.
            logger.exception("Ferramenta '%s' falhou ao executar", nome)
            return {"erro": f"'{nome}' falhou ao executar; tente de outro jeito"}, False
        if "erro" not in resultado:
            if consome:
                from app.services.emergencia import registrar_acontecimento

                resultado["acontecimento_id"] = registrar_acontecimento(self, nome, resultado)
                from app.services.imersao import registrar_ritmo

                registrar_ritmo(self, nome, resultado, em_combate)
                self._acao_gasta = True
                self.c_state.acao_resolvida = True
                from app.services.living_world import avancar_tempo

                minutos = 1 if em_combate else 10
                if nome == "mover" or (nome == "agir_no_mundo" and args.get("acao") == "atravessar"):
                    minutos = 120
                elif nome == "descansar":
                    minutos = 480 if args.get("tipo") == "longo" else 60
                elif nome == "usar_instalacao":
                    minutos = 60
                avancar_tempo(self, minutos, atualizar_hora=nome not in {"mover", "descansar"})
            if custo is not None:
                gasto = _CAMPO_DO_CUSTO.get(custo)
                if gasto:
                    setattr(self.c_state, gasto, True)
                if self.c_state.ativo and (nome == "encerrar_turno" or self._turno_acabou()):
                    resultado.update(self._passar_a_vez())
            from app.services.capitulo import conferir_passo

            conferir_passo(self)
        return resultado, "erro" not in resultado


_CAMPO_DO_CUSTO = {"acao": "acao_usada", "bonus": "bonus_usada", "movimento": "movimento_usado"}
_NOME_DO_CUSTO = {"acao": "sua ação", "bonus": "sua ação bônus", "movimento": "seu movimento"}

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
    "aproximar": ToolExecutor.aproximar,
    "recuar": ToolExecutor.recuar,
    "levantar": ToolExecutor.levantar,
    "encerrar_turno": ToolExecutor.encerrar_turno,
    "improvisar": ToolExecutor.improvisar,
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


def _consultar_contexto(executor, **args):
    from app.services.contexto_ia import consultar_contexto

    return consultar_contexto(executor, **args)


ToolExecutor._DESPACHO["consultar_contexto"] = _consultar_contexto


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
    {"type": "function", "function": {
        "name": "consultar_contexto",
        "description": "Consulta privada, sem gastar ação: mundo busca fatos/pessoas/locais; registro lê ref exata; "
        "memoria busca todo histórico; regras busca regras completas. pagina continua trechos. "
        "assunto=ferramentas carrega grupo em consulta: criacao, consequencias, comercio, viagem, "
        "progressao, combate, recompensas, imersao. Consulte antes de inventar um fato ausente.",
        "parameters": {"type": "object", "properties": {
            "assunto": {"type": "string", "enum": ["mundo", "registro", "memoria", "regras", "ferramentas"]},
            "consulta": {"type": "string"}, "pagina": {"type": "integer"},
        }, "required": ["assunto", "consulta"]},
    }},
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
                    "chefe": {
                        "type": "boolean",
                        "description": (
                            "true SÓ no confronto com o chefe do arco ([ARCO ATUAL]); o servidor usa a ficha reservada."
                        ),
                    },
                },
                "required": ["inimigos"],
            },
        },
    },
]

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
# Ações do herói em combate. Desde o combate por turnos (ADR-0040/0041) o
# narrador não as recebe: em luta, quem resolve é `/game/action`, e o chat
# fica fechado. Continuam no `_DESPACHO`, que é o que o clique usa.
ACOES_DE_COMBATE = {
    "atacar", "investir", "esquivar", "defender", "esconder_se", "fugir",
    "usar_habilidade", "interagir", "atacar_com_aliado",
}
_SO_FORA_DE_COMBATE = {
    "comerciar", "desequipar", "abrir_arco", "encerrar_arco",
    "mover", "descansar", "iniciar_combate", "recrutar_aliado",
    "registrar_cena", "registrar_pessoa", "registrar_conflito",
    "intervir_conflito", "definir_objetivo", "registrar_vinculo", "gastar_ouro",
    "consultar_regra", "ajustar_reputacao_npc",
    "registrar_particularidade", "desenvolver_consequencia", "propor_aprendizado",
    "registrar_momento", "registrar_marca",
    # Fase 1 (Mundo Vivo) — mesma regra: nenhuma ferramenta que muda o save
    # fica disponível para o narrador durante combate.
    "despachar_remessa", "propor_instalacao", "registrar_organizacao",
    "mobilizar_organizacao", "planejar_projeto", "registrar_avanco_projeto",
    "propor_acordo_projeto", "cumprir_acordo_projeto", "apresentar_oportunidades",
}
# Decisões do JOGADOR nunca são ferramenta do narrador (o painel e
# `/game/action` são o único caminho) — mesma regra que a Fase 3 aplica ao
# level-up.
_NUNCA_PARA_O_NARRADOR = {
    "escolher_especializacao", "escolher_nivel", "escolher_aprendizado", "gerir_projeto", "decidir_acordo_projeto",
    "usar_instalacao",
}


GRUPOS_FERRAMENTAS = {
    "economia": {"despachar_remessa", "comerciar"},
    "instalacoes": {"propor_instalacao"},
    "organizacoes": {"registrar_organizacao", "mobilizar_organizacao", "intervir_conflito"},
    "projetos": {"planejar_projeto", "registrar_avanco_projeto"},
    "acordos": {"propor_acordo_projeto", "cumprir_acordo_projeto"},
    "criacao": {"registrar_cena", "registrar_pessoa", "registrar_particularidade"},
    "consequencias": {"registrar_conflito", "desenvolver_consequencia", "intervir_conflito", "registrar_vinculo"},
    "comercio": {"comerciar", "equipar", "desequipar", "usar_item"},
    "viagem": {"mover", "descansar", "definir_objetivo", "iniciar_combate"},
    "progressao": {"propor_aprendizado", "definir_objetivo"},
    "combate": {"iniciar_combate", "aplicar_dano"},
    "recompensas": {"dar_item", "gastar_ouro", "ajustar_reputacao_npc", "recrutar_aliado"},
    "regras": {"consultar_regra"},
    "imersao": {"registrar_momento", "registrar_marca", "apresentar_oportunidades", "registrar_particularidade"},
}


def tools_para(c_state: CombatState, acao: str | None = None, w_state: WorldState | None = None) -> list[dict]:
    """Subconjunto de `TOOLS_SCHEMA` que o narrador recebe neste turno."""
    ocultas = _NUNCA_PARA_O_NARRADOR | ACOES_DE_COMBATE | (_SO_FORA_DE_COMBATE if c_state.ativo else set())
    disponiveis = [t for t in TOOLS_SCHEMA if t["function"]["name"] not in ocultas]
    if acao is None:
        return disponiveis
    from app.services.contexto_ia import termos

    ativas = {"consultar_contexto", "rolar_teste", "agir_no_mundo", "resolver_intencao"}
    palavras = termos(acao)
    if re.search(r"\b(?:vou|vamos|ir|indo|sigo)\s+(?:para|a|ao|à)\b", acao.casefold()):
        ativas |= GRUPOS_FERRAMENTAS["viagem"]
    gatilhos = {
        "economia": {"remessa", "estoque", "entrega", "abastec", "fornecedor"},
        "instalacoes": {"abrigo", "oficina", "instalac", "inaugur", "conquista"},
        "organizacoes": {"organizac", "facc", "guilda", "conselho", "sindicato", "companhia"},
        "acordos": {"acordo", "contrapartida", "patrocin", "exclusiv"},
        "projetos": {"projeto", "ambicao", "constru", "reconstru", "fundar", "restaur"},
        "comercio": {"compr", "vend", "mercad", "loja", "equip", "pocao", "beber", "usar"},
        # "ir"/"vou" saíram daqui (achado da auditoria): "ir" como raiz de 2
        # letras casava com qualquer palavra começando por "ir" (ex. "irmã",
        # "irritado"), carregando ferramentas de viagem à toa; "vou" nunca
        # bateria mesmo — é removido como stopword em `termos()`. A intenção
        # de viagem "vou/vamos/ir/indo/sigo para/a/ao/à" já é pega pelo
        # regex de frase acima.
        "viagem": {"viaj", "partir", "sair", "descans", "dorm", "caminh", "seguir"},
        "consequencias": {"promet", "conflit", "intervir", "consequenc", "iniciativa"},
        "progressao": {"aprend", "capitulo", "missao", "objetivo", "arco"},
        "recompensas": {"recrut", "aliado", "receb", "recompensa"},
        "criacao": {"novo", "nova", "desconhecid"},
        "combate": {"atac", "lutar", "combate", "agredir"},
        "imersao": {"convers", "lembr", "pista", "apelido", "celebr", "conviv", "investig"},
    }
    for grupo, raizes in gatilhos.items():
        if any(p.startswith(raiz) for p in palavras for raiz in raizes):
            ativas |= GRUPOS_FERRAMENTAS[grupo]
    if w_state is not None and not c_state.ativo:
        if w_state.local not in w_state.mundo.cenas:
            ativas |= GRUPOS_FERRAMENTAS["criacao"]
        # Abrir e fechar capítulo dependem do estado, não de o jogador ter
        # escrito "arco" ou "missão": a ferramenta aparece quando cabe.
        from app.services.living_world import arco_ativo, condicoes_arco

        if arco_ativo(w_state.mundo) is None:
            if any(c.estado == "ativo" for c in w_state.mundo.conflitos.values()):
                ativas.add("abrir_arco")
        elif condicoes_arco(w_state)["pode_encerrar"]:
            ativas.add("encerrar_arco")
    return [t for t in disponiveis if t["function"]["name"] in ativas]
