"""Combate v2 — fila de turnos com iniciativa real, distância e condições.

No motor antigo (`combat.turno_inimigos`) um clique era a ação do herói mais a
rodada inteira dos inimigos, sempre com o herói primeiro. Aqui cada
participante tem a sua vez, na ordem rolada: o herói, cada inimigo e cada
aliado. A distância é uma etiqueta por inimigo ("perto" ou "longe" do herói),
sem mapa. Tudo determinístico com `rng` injetado, sem LLM (ADR-0006)."""

import random
from dataclasses import dataclass

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import combat
from app.services import rules_engine as motor

HEROI = "heroi"
ATRIBUTO_RESISTENCIA = {"vigor": "constituicao", "reflexo": "destreza", "vontade": "sabedoria"}
NOME_CONDICAO = {
    "envenenado": "envenenado", "caido": "caído", "amedrontado": "amedrontado", "contido": "contido",
    "queimando": "em chamas", "enfraquecido": "enfraquecido", "atordoado": "atordoado",
}
DANO_CONDICAO = 2  # veneno e fogo, por turno do portador
REGENERACAO = 3
BONUS_GOLPE_PESADO = 3
RECARGA_INICIAL = 2  # habilidade de ação: uma vez de aviso antes do primeiro uso


@dataclass
class Alvo:
    """O que os inimigos precisam saber do herói ao agir. `hp` é mutado
    aqui; quem chama copia de volta para o personagem."""

    hp: int
    ca: int
    atributos: dict
    nivel: int = 1


# -- preparação ---------------------------------------------------------------

def _aplicar_ficha(inimigo: Inimigo) -> None:
    ficha = regras.get_monster(inimigo.arquetipo or inimigo.nome) or {}
    inimigo.alcance = ficha.get("alcance", "corpo")
    inimigo.tatica = ficha.get("tatica", "agressivo")
    inimigo.foge_abaixo = float(ficha.get("foge_abaixo", 0))
    inimigo.fortes = list(ficha.get("fortes", []))
    inimigo.habilidade = ficha.get("habilidade")


def e_chefe(inimigo: Inimigo) -> bool:
    return (inimigo.arquetipo or inimigo.nome) in regras.get_monstros_chefe()


def _proxima_intencao(inimigo: Inimigo) -> str:
    """Intenção pública: o que o inimigo fará na PRÓXIMA vez. É o aviso que
    dá sentido a Defender e Recuar."""
    if inimigo.efeitos.get("atordoado", 0):
        return "atordoado"
    hab = inimigo.habilidade
    if hab and hab.get("gatilho") == "acao" and inimigo.recarga <= 1:
        return str(hab["nome"]).lower()
    if inimigo.tatica == "bruto" and inimigo.intencao != "golpe pesado":
        return "golpe pesado"
    return "atacar"


def preparar(c_state: CombatState, atributos_heroi: dict, rng: random.Random | None = None,
             perto: bool = False) -> None:
    """Dá id estável, ficha tática, distância e iniciativa a todos, e monta
    a fila. A vez fica ANTES do primeiro: `avancar_fila` abre o combate e
    quem é mais rápido que o herói age primeiro."""
    for n, inimigo in enumerate(c_state.inimigos, start=1):
        inimigo.id = f"i{n}"
        _aplicar_ficha(inimigo)
        inimigo.distancia = "perto" if perto else "longe"
        ficha = regras.get_monster(inimigo.arquetipo or inimigo.nome) or {}
        inimigo.iniciativa = motor.rolar_iniciativa(motor.calcular_modificador(ficha.get("destreza", 10)), rng)
        if inimigo.habilidade and inimigo.habilidade.get("gatilho") == "acao":
            inimigo.recarga = RECARGA_INICIAL
        inimigo.intencao = "atacar"
    for n, aliado in enumerate(c_state.aliados, start=1):
        aliado.id = f"a{n}"
        aliado.iniciativa = motor.rolar_iniciativa(0, rng)
    iniciativa_heroi = motor.rolar_iniciativa(motor.calcular_modificador(atributos_heroi.get("destreza", 10)), rng)
    # Empate: herói, depois aliados, depois inimigos — arbitrário, mas fixo.
    ordem = [(-iniciativa_heroi, 0, HEROI)]
    ordem += [(-a.iniciativa, 1, a.id) for a in c_state.aliados]
    ordem += [(-i.iniciativa, 2, i.id) for i in c_state.inimigos]
    c_state.fila = [pid for _, _, pid in sorted(ordem)]
    c_state.vez = len(c_state.fila) - 1
    c_state.rodada = 0
    c_state.versao = 2
    _zerar_turno(c_state)


def abrir(c_state: CombatState, alvo: "Alvo", rng: random.Random | None = None, perto: bool = False) -> list[str]:
    """Começo da luta: prepara todo mundo, deixa agir quem é mais rápido
    que o herói e entrega o primeiro turno a ele."""
    preparar(c_state, alvo.atributos, rng, perto=perto)
    eventos = avancar_fila(c_state, alvo, rng)
    if vivos(c_state):
        eventos += iniciar_vez_heroi(c_state, alvo)
    return eventos


def migrar_combate(c_state: CombatState) -> bool:
    """Luta em curso de um save do motor antigo: todos já estão engajados
    ("perto"), a fila segue a iniciativa que já existia e a vez é do herói."""
    if not c_state.ativo or c_state.versao >= 2:
        return False
    for n, inimigo in enumerate(c_state.inimigos, start=1):
        inimigo.id = f"i{n}"
        _aplicar_ficha(inimigo)
        inimigo.distancia = "perto"
    for n, aliado in enumerate(c_state.aliados, start=1):
        aliado.id = f"a{n}"
    antiga = [i for i in c_state.ordem_iniciativa if 0 <= i < len(c_state.inimigos)]
    faltam = [i for i in range(len(c_state.inimigos)) if i not in antiga]
    c_state.fila = [HEROI, *[a.id for a in c_state.aliados], *[c_state.inimigos[i].id for i in antiga + faltam]]
    c_state.vez = 0
    c_state.versao = 2
    return True


# -- consultas ------------------------------------------------------------

def da_vez(c_state: CombatState) -> str:
    return c_state.fila[c_state.vez] if c_state.fila else HEROI


def inimigo_por_id(c_state: CombatState, pid: str) -> Inimigo | None:
    return next((i for i in c_state.inimigos if i.id == pid), None)


def vivos(c_state: CombatState) -> list[Inimigo]:
    return [i for i in c_state.inimigos if i.hp > 0 and not i.afastado]


def alcance_da_arma(propriedades: list[str]) -> str:
    """Sem campo novo em weapons.json: Munição atira, Arremesso faz os dois."""
    if any(p.startswith("Munição") for p in propriedades):
        return "distancia"
    if any(p.startswith("Arremesso") for p in propriedades):
        return "ambos"
    return "corpo"


def bonus_resistencia(inimigo: Inimigo, tipo: str) -> int:
    """Monstro não tem ficha de atributos completa: a resistência acompanha
    o bônus de ataque (que já sobe com a banda), +3 no que a ficha diz ser
    o forte dele."""
    return max(0, inimigo.bonus_ataque - 3) + (3 if tipo in inimigo.fortes else 0)


def resistir_inimigo(inimigo: Inimigo, tipo: str, cd: int, rng: random.Random | None = None):
    return motor.resolver_teste_atributo(bonus_resistencia(inimigo, tipo), cd, rng)


# -- condições do herói -------------------------------------------------------

def impor_condicao(c_state: CombatState, condicao: str, duracao: int) -> EventoRolagem:
    c_state.efeitos_heroi = {**c_state.efeitos_heroi,
                             condicao: max(duracao, c_state.efeitos_heroi.get(condicao, 0))}
    return EventoRolagem(
        f"⚠️ Você está {NOME_CONDICAO.get(condicao, condicao)} por {duracao} turno{'s' if duracao != 1 else ''}.",
        EventoStatus(tipo="condicao", quem=HEROI, valor=duracao, detalhe=condicao),
    )


def _resistencia_do_heroi(c_state: CombatState, alvo: Alvo, inimigo: Inimigo, hab: dict,
                          rng: random.Random | None) -> tuple[bool, DadosRolagem]:
    tipo = hab.get("resistencia", "vigor")
    atributo = ATRIBUTO_RESISTENCIA[tipo]
    mod = motor.calcular_modificador(alvo.atributos.get(atributo, 10))
    r = motor.resolver_teste_atributo(mod, int(hab.get("cd", 12)), rng)
    dados = DadosRolagem(
        tipo="resistencia", quem=HEROI, ator=inimigo.id, d20=r.rolagem, bonus=mod, total=r.total, cd=r.cd,
        sucesso=r.sucesso, atributo=atributo, motivo=str(hab.get("nome", "")),
        partes_bonus=[{"rotulo": motor.ATRIBUTO_LABEL[atributo], "valor": mod}],
    )
    return r.sucesso, dados


def _usar_habilidade(c_state: CombatState, inimigo: Inimigo, alvo: Alvo, rng: random.Random | None) -> list[str]:
    """Habilidade de ação (sopro, raio, olhar): o herói resiste ou sofre."""
    hab = inimigo.habilidade or {}
    passou, dados = _resistencia_do_heroi(c_state, alvo, inimigo, hab, rng)
    dano = motor.calcular_dano(hab["dano"], rng=rng) if hab.get("dano") else 0
    if passou:
        dano = dano // 2 if hab.get("meio") else 0
    dados.dano = dano or None
    alvo.hp = max(0, alvo.hp - dano)
    linha = (
        f"🎲 {inimigo.nome} usa {hab['nome']}! Resistência ({dados.atributo}): d20({dados.d20})+{dados.bonus}="
        f"{dados.total} vs CD {dados.cd} → {'RESISTIU' if passou else 'FALHOU'}."
        + (f" {dano} de dano." if dano else "")
    )
    eventos: list[str] = [EventoRolagem(linha, dados)]
    if not passou and hab.get("condicao"):
        eventos.append(impor_condicao(c_state, hab["condicao"], int(hab.get("duracao", 1))))
    return eventos


# -- vez de cada um ---------------------------------------------------------

def _fim_da_vez_do_inimigo(inimigo: Inimigo) -> None:
    inimigo.efeitos = combat._avancar_efeitos(inimigo.efeitos)
    inimigo.intencao = _proxima_intencao(inimigo)


def _morreu(inimigo: Inimigo) -> EventoRolagem:
    return EventoRolagem(f"💀 {inimigo.nome} cai.", EventoStatus(tipo="morte_inimigo", quem=inimigo.nome))


def _atacar(c_state: CombatState, inimigo: Inimigo, alvo: Alvo, tipo_alvo: str, idx_aliado: int | None,
            vantagem: bool | None, rng: random.Random | None, oportunidade: bool = False) -> list[str]:
    eventos: list[str] = []
    aliado = c_state.aliados[idx_aliado] if tipo_alvo == "aliado" and idx_aliado is not None else None
    if aliado is not None:
        nome_alvo, ca_alvo = aliado.nome, aliado.ca
        linha = f"🎲 {inimigo.nome} ataca {aliado.nome} com {inimigo.nome_ataque}: "
    else:
        nome_alvo = HEROI
        ca_alvo = alvo.ca + c_state.heroi_bonus_ca + (2 if c_state.efeitos_heroi.get("guarda", 0) else 0)
        verbo = "aproveita a brecha e ataca" if oportunidade else "ataca"
        linha = f"🎲 {inimigo.nome} {verbo} com {inimigo.nome_ataque}: "
    pesado = inimigo.intencao == "golpe pesado" and not oportunidade
    r = motor.resolver_ataque(inimigo.bonus_ataque, ca_alvo, rng, vantagem=vantagem)
    linha += f"d20({r.rolagem})+{r.bonus}={r.total} vs CA {ca_alvo} → "
    dados = DadosRolagem(
        tipo="ataque", quem=inimigo.nome, ator=inimigo.id, alvo=nome_alvo, alvo_id=aliado.id if aliado else HEROI,
        d20=r.rolagem, bonus=r.bonus, total=r.total, ca=ca_alvo, sucesso=r.acerto, critico=r.critico,
        falha_critica=r.falha_critica, d20_extra=r.d20_extra, vantagem=r.vantagem,
    )
    if not r.acerto:
        return [EventoRolagem(linha + "ERROU.", dados)]
    dano = motor.calcular_dano(inimigo.dano_dado, r.critico, rng) + (BONUS_GOLPE_PESADO if pesado else 0)
    if inimigo.efeitos.get("enfraquecido", 0):
        dano = max(0, dano - 3)
    if aliado is None and (c_state.efeitos_heroi.get("furia", 0) or c_state.efeitos_heroi.get("protecao", 0)):
        dano = max(0, dano - 2)
    dados.dano = dano
    eventos.append(EventoRolagem(
        linha + f"ACERTO{' CRÍTICO' if r.critico else ''}{' (golpe pesado)' if pesado else ''}! {dano} de dano.", dados
    ))
    if aliado is not None:
        aliado.hp = max(0, aliado.hp - dano)
        if aliado.hp == 0:
            eventos.append(EventoRolagem(f"💀 {aliado.nome} cai.", EventoStatus(tipo="morte_aliado", quem=aliado.nome)))
        return eventos
    antes = alvo.hp
    alvo.hp = max(0, alvo.hp - dano)
    hab = inimigo.habilidade
    if hab and hab.get("gatilho") == "no_acerto" and alvo.hp > 0 and not oportunidade:
        passou, dados_res = _resistencia_do_heroi(c_state, alvo, inimigo, hab, rng)
        eventos.append(EventoRolagem(
            f"🎲 {hab['nome']}: resistência ({dados_res.atributo}) d20({dados_res.d20})+{dados_res.bonus}="
            f"{dados_res.total} vs CD {dados_res.cd} → {'RESISTIU' if passou else 'FALHOU'}.", dados_res,
        ))
        if not passou:
            eventos.append(impor_condicao(c_state, hab["condicao"], int(hab.get("duracao", 1))))
    if antes > 0 and alvo.hp == 0:
        eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
    return eventos


def vez_inimigo(c_state: CombatState, inimigo: Inimigo, alvo: Alvo, rng: random.Random | None = None) -> list[str]:
    eventos: list[str] = []
    inimigo.reacao_usada = False
    if inimigo.efeitos.get("queimando", 0):
        inimigo.hp = max(0, inimigo.hp - DANO_CONDICAO)
        eventos.append(EventoRolagem(
            f"🔥 {inimigo.nome} sofre {DANO_CONDICAO} de queimadura.",
            DadosRolagem(tipo="dano", quem=HEROI, alvo=inimigo.nome, alvo_id=inimigo.id, dano=DANO_CONDICAO),
        ))
        if inimigo.hp == 0:
            return [*eventos, _morreu(inimigo)]
    if inimigo.tatica == "regenera" and 0 < inimigo.hp < inimigo.max_hp:
        cura = min(REGENERACAO, inimigo.max_hp - inimigo.hp)
        inimigo.hp += cura
        eventos.append(f"💚 {inimigo.nome} regenera {cura} PV.")
    if inimigo.recarga > 0:
        inimigo.recarga -= 1
    if inimigo.efeitos.get("atordoado", 0):
        eventos.append(f"💫 {inimigo.nome} está atordoado e perde a vez.")
        _fim_da_vez_do_inimigo(inimigo)
        return eventos
    ferido = inimigo.max_hp > 0 and inimigo.hp / inimigo.max_hp < inimigo.foge_abaixo
    if ferido and not e_chefe(inimigo):
        inimigo.afastado = True
        eventos.append(f"🏃 {inimigo.nome} foge do combate.")
        return eventos

    tipo_alvo, idx_aliado = combat._escolher_alvo(c_state, rng)
    aliados_de_pe = [i for i, a in enumerate(c_state.aliados) if a.hp > 0]
    if tipo_alvo == HEROI and alvo.hp <= 0:
        # Herói caído não leva golpe de misericórdia: quem decide é o teste de morte.
        if not aliados_de_pe:
            _fim_da_vez_do_inimigo(inimigo)
            return eventos
        tipo_alvo, idx_aliado = "aliado", aliados_de_pe[0]
    if tipo_alvo == HEROI and c_state.heroi_escondido:
        eventos.append(f"👤 {inimigo.nome} vasculha o local, sem te encontrar.")
        _fim_da_vez_do_inimigo(inimigo)
        return eventos

    vantagem: bool | None = None
    outros = sum(1 for i in vivos(c_state) if i is not inimigo)
    if inimigo.tatica == "matilha" and outros > 0:
        vantagem = True
    if tipo_alvo == HEROI:
        if inimigo.alcance == "corpo" and inimigo.distancia == "longe":
            inimigo.distancia = "perto"
            eventos.append(f"👣 {inimigo.nome} avança até você.")
        hab = inimigo.habilidade
        if hab and hab.get("gatilho") == "acao" and inimigo.recarga == 0:
            eventos += _usar_habilidade(c_state, inimigo, alvo, rng)
            inimigo.recarga = int(hab.get("recarga", 3))
            if alvo.hp == 0:
                eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
            _fim_da_vez_do_inimigo(inimigo)
            return eventos
        if inimigo.alcance == "distancia" and inimigo.distancia == "perto":
            vantagem = combat._combinar_vantagem(vantagem, False)  # atirar com o alvo colado atrapalha
        if inimigo.distancia == "perto" and (
            c_state.efeitos_heroi.get("caido", 0) or c_state.efeitos_heroi.get("contido", 0)
        ):
            vantagem = combat._combinar_vantagem(vantagem, True)
        vantagem = combat._combinar_vantagem(vantagem, c_state.heroi_vantagem_inimiga)
        if c_state.efeitos_heroi.get("esquiva", 0):
            vantagem = combat._combinar_vantagem(vantagem, False)
    eventos += _atacar(c_state, inimigo, alvo, tipo_alvo, idx_aliado, vantagem, rng)
    _fim_da_vez_do_inimigo(inimigo)
    return eventos


def vez_aliado(c_state: CombatState, aliado: Aliado, rng: random.Random | None = None) -> list[str]:
    """O aliado age sozinho: bate em quem o herói marcou (com vantagem, uma
    vez por comando) ou em quem está mais ferido."""
    de_pe = vivos(c_state)
    if not de_pe:
        return []
    marcado = next((i for i in de_pe if i.id == c_state.alvo_marcado), None)
    alvo = marcado or min(de_pe, key=lambda i: (i.hp, i.id))
    vantagem = True if (marcado is not None and c_state.comando) else None
    if marcado is not None:
        c_state.comando = False
    return combat.turno_aliado(c_state, aliado, alvo.nome, rng, vantagem=vantagem)


# -- o herói ---------------------------------------------------------------

def _zerar_turno(c_state: CombatState) -> None:
    c_state.acao_usada = c_state.bonus_usada = c_state.movimento_usado = c_state.reacao_usada = False


def iniciar_vez_heroi(c_state: CombatState, alvo: Alvo) -> list[str]:
    """Começo do turno do herói: o que ele armou no turno anterior (defesa,
    esquiva, esconderijo) já protegeu contra a rodada e expira agora."""
    _zerar_turno(c_state)
    c_state.heroi_bonus_ca = 0
    c_state.heroi_vantagem_inimiga = None
    c_state.heroi_escondido = False
    eventos: list[str] = []
    if alvo.hp <= 0:
        return eventos
    for condicao, emoji in (("envenenado", "☠️"), ("queimando", "🔥")):
        if c_state.efeitos_heroi.get(condicao, 0) and alvo.hp > 0:
            alvo.hp = max(0, alvo.hp - DANO_CONDICAO)
            eventos.append(EventoRolagem(
                f"{emoji} Você sofre {DANO_CONDICAO} de dano por estar {NOME_CONDICAO[condicao]}.",
                DadosRolagem(tipo="dano", quem="condicao", alvo=HEROI, alvo_id=HEROI, dano=DANO_CONDICAO),
            ))
    if alvo.hp == 0:
        eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
    elif c_state.efeitos_heroi.get("atordoado", 0):
        eventos.append("💫 Você está atordoado e perde a vez.")
        c_state.acao_usada = c_state.bonus_usada = c_state.movimento_usado = True
    return eventos


def encerrar_vez_heroi(c_state: CombatState) -> None:
    c_state.efeitos_heroi = combat._avancar_efeitos(c_state.efeitos_heroi)


def aproximar(c_state: CombatState, inimigo: Inimigo) -> list[str]:
    inimigo.distancia = "perto"
    return [f"👣 Você avança até {inimigo.nome}."]


def recuar(c_state: CombatState, alvo: Alvo, rng: random.Random | None = None,
           sem_oportunidade: bool = False) -> list[str]:
    """Sair do corpo a corpo abre a guarda: cada inimigo perto que ainda
    tem reação nesta rodada ataca uma vez. Depois todos ficam longe."""
    eventos: list[str] = ["↩️ Você recua e abre distância."]
    for inimigo in vivos(c_state):
        if inimigo.distancia != "perto":
            continue
        pode_reagir = not inimigo.reacao_usada and not inimigo.efeitos.get("atordoado", 0)
        if pode_reagir and not sem_oportunidade and alvo.hp > 0:
            inimigo.reacao_usada = True
            eventos += _atacar(c_state, inimigo, alvo, HEROI, None, None, rng, oportunidade=True)
        inimigo.distancia = "longe"
    return eventos


def avancar_fila(c_state: CombatState, alvo: Alvo, rng: random.Random | None = None) -> list[str]:
    """Anda a fila a partir de quem acabou de agir, resolvendo inimigos e
    aliados, até chegar a vez do herói ou a luta acabar."""
    eventos: list[str] = []
    for _ in range(2 * len(c_state.fila) + 2):  # trava: nunca roda sem fim
        if not vivos(c_state) or not c_state.fila:
            break
        c_state.vez = (c_state.vez + 1) % len(c_state.fila)
        if c_state.vez == 0:
            c_state.rodada += 1
        pid = c_state.fila[c_state.vez]
        if pid == HEROI:
            break
        inimigo = inimigo_por_id(c_state, pid)
        if inimigo is not None:
            if inimigo.hp > 0 and not inimigo.afastado:
                eventos += vez_inimigo(c_state, inimigo, alvo, rng)
            continue
        aliado = next((a for a in c_state.aliados if a.id == pid), None)
        if aliado is not None and aliado.hp > 0:
            eventos += vez_aliado(c_state, aliado, rng)
    return eventos
