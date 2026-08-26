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

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo, LocalDescoberto, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.services import combat
from app.services import rules_engine as motor


def _efeito_pocao_cura(executor: "ToolExecutor") -> dict:
    cura = motor.calcular_dano("2d4+2", rng=executor.rng)
    executor.heroi.hp_atual = min(executor.heroi.hp_max, executor.heroi.hp_atual + cura)
    executor.eventos.append(
        EventoRolagem(
            f"🧪 Poção de Cura: recupera {cura} PV. HP: {executor.heroi.hp_atual}/{executor.heroi.hp_max}.",
            EventoStatus(tipo="cura", quem="heroi", valor=cura),
        )
    )
    return {"cura": cura, "hp_atual": executor.heroi.hp_atual}


# Itens com efeito mecânico conhecido. Um item fora deste mapa ainda pode ser
# "usado" (validação de posse continua valendo), só não move nenhum número —
# não existe um sistema de itens completo ainda, é escopo aberto para depois.
_EFEITOS_ITENS: dict[str, Callable[["ToolExecutor"], dict]] = {
    "Poção de Cura": _efeito_pocao_cura,
}

# Fase 6 da revisão de gameplay (Etapa 12/13) — relógio de facção único
# (urgência do Ato atual). Chave de dict, não uma coluna própria — cabe
# mais de um relógio no futuro sem mudar `WorldState.relogios`.
RELOGIO_URGENCIA = "urgencia_ato"
RELOGIO_MAXIMO = 4


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

    def rolar_teste(self, atributo: str, cd: int, item_usado: str | None = None) -> dict:
        if atributo not in motor.ATRIBUTOS_VALIDOS:
            return {"erro": f"'{atributo}' não é um atributo válido: {sorted(motor.ATRIBUTOS_VALIDOS)}"}
        mod = motor.calcular_modificador(self.heroi.atributos.get(atributo, 10))
        partes_bonus = [{"rotulo": motor.ATRIBUTO_LABEL[atributo], "valor": mod}]
        mod_total = mod
        tags = regras.get_tags(item_usado) if item_usado and item_usado in self.heroi.inventario else []
        if tags:
            mod_total += self.BONUS_ITEM_COM_TAG
            partes_bonus.append({"rotulo": f"{item_usado} ({tags[0]})", "valor": self.BONUS_ITEM_COM_TAG})
        resultado = motor.resolver_teste_atributo(mod_total, cd, self.rng)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_total, total=resultado.total,
            cd=cd, sucesso=resultado.sucesso, atributo=atributo,
            partes_bonus=partes_bonus,
        )
        self.eventos.append(
            EventoRolagem(
                f"🎲 Teste de {atributo}: d20({resultado.rolagem})+{mod_total}={resultado.total} vs CD {cd} → "
                f"{'SUCESSO' if resultado.sucesso else 'FALHA'}.",
                dados,
            )
        )
        return {"sucesso": resultado.sucesso, "total": resultado.total}

    def atacar(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de atacar"}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel()
        )
        self.eventos.extend(eventos)

        if all(i.hp <= 0 for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            resultado_xp = self._conceder_xp(self.c_state.inimigos)
            return {"resultado": "vitoria", **resultado_xp}

        eventos_inimigos, dano = combat.turno_inimigos(self.c_state, self.heroi.defesa, self.rng)
        self.eventos.extend(eventos_inimigos)
        self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
        if self.heroi.hp_atual == 0 and dano > 0:
            self.eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
        return {"dano_recebido": dano, "hp_atual": self.heroi.hp_atual}

    # Fase 1 da revisão de gameplay (Etapa 12/13) — CD das ações táticas
    # que envolvem teste (esconder_se, fugir). Valor de primeira passada,
    # igual ao XP_OBJETIVO_NAO_COMBATE acima: ajustar depois com
    # `evals/simulador.py`, não chutar de novo.
    CD_ACAO_TATICA = 12

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
        if not self.c_state.ativo or all(i.hp <= 0 for i in self.c_state.inimigos):
            return {}
        ca_efetiva = self.heroi.defesa + self.c_state.heroi_bonus_ca
        if self.c_state.heroi_escondido:
            self.eventos.append("👤 Os inimigos vasculham o local, sem te encontrar.")
            dano = 0
        else:
            eventos_inimigos, dano = combat.turno_inimigos(
                self.c_state, ca_efetiva, self.rng, vantagem=self.c_state.heroi_vantagem_inimiga
            )
            self.eventos.extend(eventos_inimigos)
        self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
        if self.heroi.hp_atual == 0 and dano > 0:
            self.eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
        self.c_state.heroi_vantagem_inimiga = None
        self.c_state.heroi_bonus_ca = 0
        self.c_state.heroi_escondido = False
        return {"dano_recebido": dano, "hp_atual": self.heroi.hp_atual}

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
        self.eventos.append("🛡️ Você assume postura defensiva (+2 na CA).")
        return {"acao": "defender", **self._resolver_reacao_inimiga()}

    def investir(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de investir"}
        eventos = combat.turno_jogador(
            self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng, self._nivel(),
            investida=True,
        )
        self.eventos.extend(eventos)
        if all(i.hp <= 0 for i in self.c_state.inimigos):
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
        mod_destreza = motor.calcular_modificador(self.heroi.atributos.get("destreza", 10))
        resultado = motor.resolver_teste_atributo(mod_destreza, self.CD_ACAO_TATICA, self.rng)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_destreza, total=resultado.total,
            cd=self.CD_ACAO_TATICA, sucesso=resultado.sucesso, atributo="destreza",
            partes_bonus=[{"rotulo": "Destreza", "valor": mod_destreza}],
        )
        if resultado.sucesso:
            self.c_state.heroi_escondido = True
            texto = (
                f"🎲 Você se esconde: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {self.CD_ACAO_TATICA} → SUCESSO. Eles perdem seu rastro."
            )
        else:
            texto = (
                f"🎲 Você tenta se esconder: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {self.CD_ACAO_TATICA} → FALHA."
            )
        self.eventos.append(EventoRolagem(texto, dados))
        return {"acao": "esconder_se", "escondido": resultado.sucesso, **self._resolver_reacao_inimiga()}

    def fugir(self) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de fugir"}
        mod_destreza = motor.calcular_modificador(self.heroi.atributos.get("destreza", 10))
        resultado = motor.resolver_teste_atributo(mod_destreza, self.CD_ACAO_TATICA, self.rng)
        dados = DadosRolagem(
            tipo="teste", quem="heroi", d20=resultado.rolagem, bonus=mod_destreza, total=resultado.total,
            cd=self.CD_ACAO_TATICA, sucesso=resultado.sucesso, atributo="destreza",
            partes_bonus=[{"rotulo": "Destreza", "valor": mod_destreza}],
        )
        if resultado.sucesso:
            self.c_state.ativo = False
            texto = (
                f"🎲 Você foge: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
                f"vs CD {self.CD_ACAO_TATICA} → SUCESSO. Você escapa do combate."
            )
            self.eventos.append(EventoRolagem(texto, dados))
            return {"acao": "fugir", "fugiu": True}
        texto = (
            f"🎲 Você tenta fugir: d20({resultado.rolagem})+{mod_destreza}={resultado.total} "
            f"vs CD {self.CD_ACAO_TATICA} → FALHA. Eles reagem antes que você escape."
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
        xp_ganho = sum((regras.get_monster(i.nome) or {}).get("xp", 0) for i in inimigos_derrotados)
        if xp_ganho <= 0:
            return {}
        return self._aplicar_xp(xp_ganho)

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
            self.heroi.hp_max += resultado.hp_ganho
            self.heroi.hp_atual += resultado.hp_ganho
            self.eventos.append(
                f"🎉 Subiu para o nível {resultado.nivel_novo}! (+{resultado.hp_ganho} PV máximo)"
            )
        return {"xp_ganho": xp_ganho, "xp_total": self.heroi.xp, "nivel": self.heroi.nivel}

    # Fase 0 da revisão de gameplay (Etapa 12/13) — XP não-combate: sem isso
    # o jogador que resolve tudo conversando nunca sobe de nível (P-1 do
    # backlog antigo, metade resolvida). Valor fixo, não proposto pelo
    # modelo — mesmo princípio de `_conceder_xp` (ADR-0006: o LLM não decide
    # números), só o "quando" é dele, o "quanto" é do servidor. Equivale a
    # um monstro de Nível 1 ; ajustar depois com `evals/simulador.py`.
    XP_OBJETIVO_NAO_COMBATE = 50

    def concluir_objetivo(self, objetivo: str) -> dict:
        resultado = self._aplicar_xp(self.XP_OBJETIVO_NAO_COMBATE)
        return {"objetivo": objetivo, **resultado}

    def aplicar_dano(self, alvo: str, dado_dano: str, motivo: str = "") -> dict:
        dano = motor.calcular_dano(dado_dano, rng=self.rng)
        nomes_heroi = {"heroi", "herói", "você", "voce", self.heroi.nome.lower()}
        if alvo.lower() in nomes_heroi:
            self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
            self.eventos.append(
                f"🎲 {motivo or 'Dano recebido'}: {dado_dano} → {dano} de dano. "
                f"HP: {self.heroi.hp_atual}/{self.heroi.hp_max}."
            )
            return {"dano": dano, "hp_atual": self.heroi.hp_atual}

        alvo_obj = next((i for i in self.c_state.inimigos if i.nome == alvo and i.hp > 0), None)
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
        return {"dano": dano, "hp_atual": alvo_obj.hp}

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
        if item not in self.heroi.inventario:
            return {"erro": f"'{item}' não está no inventário"}
        efeito = _EFEITOS_ITENS.get(item)
        if efeito is None:
            # Sem efeito mecânico conhecido: não é consumível, não sai do
            # inventário (só itens com `_EFEITOS_ITENS` são consumidos).
            resultado = {"usado": True, "efeito": "sem efeito mecânico definido — narre livremente o uso"}
        else:
            resultado = efeito(self)
            self.heroi.inventario = [i for i in self.heroi.inventario if i != item]
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
        self.eventos.append(
            EventoRolagem(
                f"🏕️ Descanso longo: recupera totalmente os PV. HP: {self.heroi.hp_atual}/{self.heroi.hp_max}.",
                EventoStatus(tipo="cura", quem="heroi", valor=cura),
            )
        )
        # Fase 6 — relógio de urgência: descansar demais custa tempo, e o
        # tempo custa caro pro Ato atual (ver montar_contexto/[EVENTO GLOBAL]).
        self.w_state.relogios[RELOGIO_URGENCIA] = self.w_state.relogios.get(RELOGIO_URGENCIA, 0) + 1
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

    def dar_item(self, item: str) -> dict:
        self.heroi.inventario = [*self.heroi.inventario, item]
        self.eventos.append(f"🎁 {self.heroi.nome} recebe: {item}.")
        return {"inventario": self.heroi.inventario}

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

    def iniciar_combate(self, inimigos: list[str]) -> dict:
        if self.c_state.ativo:
            return {"erro": "já há um combate ativo"}
        novo, eventos, dano_surpresa = combat.iniciar_combate(
            inimigos, self.heroi.atributos, self.heroi.defesa, self.rng
        )
        self.c_state.ativo = novo.ativo
        self.c_state.inimigos = novo.inimigos
        self.c_state.sucessos_morte = novo.sucessos_morte
        self.c_state.falhas_morte = novo.falhas_morte
        self.c_state.resultado = novo.resultado
        self.c_state.ordem_iniciativa = novo.ordem_iniciativa
        self.c_state.turno_atual = novo.turno_atual
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

    def atualizar_missao(self, nome: str, objetivo: str, avancar_ato: bool = False) -> dict:
        self.q_state.nome_missao = nome
        self.q_state.objetivo_missao = objetivo
        self.eventos.append(f"📜 Missão atualizada: {nome} - {objetivo}")
        resultado: dict[str, object] = {"missao": nome, "objetivo": objetivo}
        # Fase 4 da revisão de gameplay — o modelo sinaliza que o Ato
        # inteiro (não só a missão miúda) terminou; o servidor decide se
        # há um próximo Ato pra avançar (nunca deixa o índice estourar —
        # o último Ato fica como "fim de campanha" até a Fase 7 dar um
        # fechamento de verdade a isso).
        if avancar_ato and self.q_state.atos and self.q_state.ato_atual < len(self.q_state.atos) - 1:
            self.q_state.ato_atual += 1
            novo_ato = self.q_state.atos[self.q_state.ato_atual]
            self.eventos.append(f"📖 Novo Ato: {novo_ato.titulo}")
            resultado["ato_atual"] = self.q_state.ato_atual
            resultado["ato_titulo"] = novo_ato.titulo
            # Fase 6 — o relógio de urgência é do Ato que está terminando;
            # o novo Ato começa com o dele próprio zerado.
            self.w_state.relogios[RELOGIO_URGENCIA] = 0
        return resultado

    # Fase 3 da revisão de gameplay (Etapa 12/13, ADR-0027) — estatísticas
    # de combate de um aliado recrutado são fixas, não propostas pelo
    # modelo (mesmo princípio de `_conceder_xp`: o LLM decide O QUÊ, nunca
    # O QUANTO). Primeira passada; ajustar depois com `evals/simulador.py`.
    CA_ALIADO_PADRAO = 12
    BONUS_ATAQUE_ALIADO_PADRAO = 2
    DANO_ALIADO_PADRAO = "1d6"
    HP_ALIADO_MIN = 4
    HP_ALIADO_MAX = 20

    def recrutar_aliado(self, nome: str, classe: str, hp: int) -> dict:
        aliados = self.heroi.aliados or []
        if any(a["nome"] == nome for a in aliados):
            return {"erro": f"'{nome}' já é um aliado"}
        hp_clampado = max(self.HP_ALIADO_MIN, min(self.HP_ALIADO_MAX, hp))
        registro = {
            "nome": nome, "classe": classe, "hp": hp_clampado, "hp_max": hp_clampado,
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
        if all(i.hp <= 0 for i in self.c_state.inimigos):
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
        try:
            resultado = metodo(self, **args)
        except TypeError as e:
            return {"erro": f"argumentos inválidos para '{nome}': {e}"}, False
        except Exception as e:  # ferramenta com bug não pode derrubar o turno
            return {"erro": f"'{nome}' falhou ao executar: {e}"}, False
        return resultado, "erro" not in resultado


ToolExecutor._DESPACHO = {
    "rolar_teste": ToolExecutor.rolar_teste,
    "atacar": ToolExecutor.atacar,
    "aplicar_dano": ToolExecutor.aplicar_dano,
    "mover": ToolExecutor.mover,
    "consultar_regra": ToolExecutor.consultar_regra,
    "usar_item": ToolExecutor.usar_item,
    "dar_item": ToolExecutor.dar_item,
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


TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "rolar_teste",
            "description": (
                "Testa um atributo do herói contra uma dificuldade — para qualquer ação arriscada e "
                "incerta que NÃO seja atacar em combate (escalar, se esconder, persuadir, resistir a "
                "veneno, notar uma armadilha, equilibrar-se). Sempre que o jogador tenta algo que pode "
                "dar errado, chame esta ferramenta em vez de decidir sozinho se ele conseguiu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "atributo": {
                        "type": "string",
                        "enum": ["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"],
                        "description": "O atributo mais relevante para a ação (força para escalar/arrombar, "
                        "destreza para se esconder/equilibrar, carisma para persuadir/enganar, etc.).",
                    },
                    "cd": {
                        "type": "integer",
                        "description": "Classe de Dificuldade: 5=trivial, 10=fácil, 15=médio, "
                        "20=difícil, 25=muito difícil.",
                    },
                    "item_usado": {
                        "type": "string",
                        "description": (
                            "Nome exato de um item/arma do inventário do herói, SE ele usar algo de "
                            "forma criativa pra ajudar no teste (ex: usar um machado pesado pra arrombar "
                            "uma porta). Omita se nenhum item se aplica."
                        ),
                    },
                },
                "required": ["atributo", "cd"],
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
                        "description": "Nome exato de uma arma do inventário do herói. Omita para usar a "
                        "primeira arma reconhecida do inventário, ou ataque desarmado se não houver nenhuma.",
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
                "Ataque arriscado (Investida): menos precisão, mais dano — o botão de risco do combate. "
                "Use quando o jogador quiser atacar com tudo, apostando força por cautela. Deixa o herói "
                "mais exposto até a próxima rodada."
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
                        "description": "Nome exato de uma arma do inventário do herói. Omita para usar a "
                        "primeira arma reconhecida do inventário, ou ataque desarmado se não houver nenhuma.",
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
                "O herói foca em não ser atingido em vez de atacar — ataques inimigos contra ele vêm com "
                "desvantagem até a próxima rodada. Use quando o jogador declarar que está se esquivando, "
                "se protegendo ou evitando golpes em vez de agir."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "defender",
            "description": (
                "O herói assume postura defensiva (+2 na Classe de Armadura até a próxima rodada) em vez "
                "de atacar. Use quando o jogador declarar que está se defendendo, se protegendo com o "
                "escudo/arma, ou segurando a posição."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "esconder_se",
            "description": (
                "O herói tenta sumir de vista (teste de Destreza) em vez de agir. Se bem-sucedido, os "
                "inimigos não conseguem alvejá-lo na próxima rodada. Use quando o jogador declarar que "
                "está se escondendo, se camuflando ou recuando para as sombras."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recrutar_aliado",
            "description": (
                "Recruta um NPC como companheiro do herói — ele passa a acompanhar a jornada e a lutar ao "
                "lado dele. Use quando a cena resultar num NPC se juntando de verdade ao grupo (não para "
                "NPCs que só ajudam de passagem ou aparecem numa cena só)."
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
                "Resolve o ataque de um aliado recrutado contra um inimigo vivo do combate atual. Use "
                "quando o jogador dirigir a ação do aliado ('Bob ataca o goblin') ou quando a cena pedir "
                "que ele entre na luta. Não substitui a ação do herói — chame também a ferramenta da ação "
                "dele (atacar, esquivar...) para fechar a rodada."
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
                "O herói tenta escapar do combate por completo (teste de Destreza). Se bem-sucedido, o "
                "combate termina sem vitória nem derrota. Se falhar, os inimigos têm uma rodada de ataque "
                "livre. Use quando o jogador declarar que está fugindo, recuando de vez ou correndo."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aplicar_dano",
            "description": (
                "Aplica dano que NÃO vem de um ataque com arma — queda, armadilha, fogo, veneno, magia "
                "ambiental. Não use para ataques normais em combate (isso é a ferramenta 'atacar'). Você "
                "propõe a notação de dado apropriada à fonte do dano (ex: uma queda de 3 metros é '1d6', "
                "uma fogueira é '2d6'); o servidor rola o dado de verdade."
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
                "Move o herói para outro local do mundo. Use quando o jogador declarar que está indo "
                "para um lugar específico e a cena não estiver em combate. O destino precisa ser um dos "
                "locais conhecidos do mundo — se não tiver certeza do nome exato, chame mesmo assim: o "
                "servidor devolve a lista de locais válidos se o nome não bater. Se a cena descobre um "
                "local NOVO (sem equivalente na lista), passe 'descricao_proposta' — o servidor registra "
                "esse local antes de mover pra lá, e ele passa a existir de verdade no mundo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destino": {"type": "string", "description": "Nome do local de destino."},
                    "descricao_proposta": {
                        "type": "string",
                        "description": (
                            "Só quando 'destino' é um lugar NOVO, fora dos locais conhecidos: uma "
                            "descrição curta do que o local é, pra registrá-lo no mundo."
                        ),
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
                "Busca uma regra na bíblia do mestre. Chame SEMPRE que o jogador fizer uma pergunta sobre "
                "como uma mecânica do jogo funciona — mesmo fora do personagem, mesmo em tom de dúvida "
                "('como funciona X?', 'o que acontece se eu Y?') — em vez de responder de memória."
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
                "O herói descansa para recuperar PV. 'curto' recupera parcial e pode acontecer em "
                "quase qualquer lugar seguro o bastante pra uma pausa. 'longo' recupera tudo, mas só "
                "funciona num local seguro (uma cidade, uma pousada) e não pode se repetir rápido "
                "demais. Nunca use em combate."
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
                "properties": {"item": {"type": "string", "description": "Nome do item a entregar."}},
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
                "Registra que o herói foi notavelmente rude, ameaçador, generoso ou gentil com um NPC "
                "nomeado — não em toda interação trivial, só quando o tom da cena claramente muda a "
                "relação. O NPC vai lembrar disso em cenas futuras (preço, disposição a ajudar, tom)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "npc": {"type": "string", "description": "Nome exato do NPC."},
                    "delta": {
                        "type": "integer",
                        "description": "Positivo para melhorar a relação, negativo para piorar. "
                        "Use algo entre -10 e 10 proporcional à gravidade (insulto leve: -2, "
                        "ameaça grave: -8, presente generoso: +5).",
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
                "Cria um combate quando a cena tem um confronto físico iminente com um ou mais monstros "
                "do bestiário do mundo. Use assim que a ameaça se torna hostil — não espere o jogador "
                "declarar 'eu ataco' primeiro, isso quem resolve é a ferramenta 'atacar' depois."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "inimigos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nomes de monstros do bestiário que encaixam na cena (ex: ['Goblin']).",
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
                    "avancar_ato": {
                        "type": "boolean",
                        "description": (
                            "true SÓ quando o objetivo do ATO ATUAL inteiro (não a missão miúda) "
                            "acabou de ser cumprido de verdade — avança a campanha pro próximo Ato."
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
                "Concede XP por um objetivo narrativo cumprido sem combate — resolver um enigma, "
                "convencer um NPC, completar uma missão por diplomacia ou investigação. Use uma vez "
                "por objetivo concluído, nunca repetidamente pelo mesmo feito."
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
