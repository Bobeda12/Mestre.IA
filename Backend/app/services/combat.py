"""Orquestra o combate ligando o bestiário real (infra/data_manager.py) à
resolução determinística do juiz (services/rules_engine.py).

O narrador (services/narrator.py) PROPÕE — quais monstros encaixam na cena,
qual arma e alvo o jogador quis usar; este módulo DECIDE — acerto, dano,
iniciativa, morte. Zero LLM aqui, mesmo padrão de fronteira de confiança do
ADR-0002 (Etapa 1), agora aplicado ao combate em vez do point-buy.

Ver ADR-0006 para a decisão de arquitetura por trás desta separação."""

import random

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import rules_engine as motor

NOME_ARMA_DESARMADA = "Ataque Desarmado"
_ARMA_DESARMADA = {"dano": "1d1", "propriedades": []}


def _mod_para_arma(atributos: dict, propriedades: list[str]) -> tuple[int, str]:
    """Força é o padrão; armas "Sutil" (finesse) usam o melhor entre Força e
    Destreza, e armas de "Munição" (à distância) usam Destreza — regras reais
    do PHB, não simplificação. Devolve também QUAL atributo venceu, para o
    card de rolagem poder mostrar "Destreza +2" em vez de um bônus sem
    origem (Etapa 11, B-8)."""
    mod_forca = motor.calcular_modificador(atributos.get("forca", 10))
    mod_destreza = motor.calcular_modificador(atributos.get("destreza", 10))
    if "Sutil" in propriedades:
        return (mod_forca, "forca") if mod_forca >= mod_destreza else (mod_destreza, "destreza")
    if "Munição" in propriedades:
        return mod_destreza, "destreza"
    return mod_forca, "forca"


def escolher_arma(inventario: list[str], proposta: str | None) -> tuple[str, dict]:
    """O narrador propõe a arma que o jogador quis usar; aqui o servidor
    confirma que ela existe no arsenal E está na mochila do herói. Se a
    proposta falhar, cai para a primeira arma reconhecida no inventário, e
    por fim para ataque desarmado — nunca para uma arma inventada."""
    if proposta:
        dados = regras.get_weapon(proposta)
        if dados and proposta in inventario:
            return proposta, dados
    for item in inventario:
        dados = regras.get_weapon(item)
        if dados:
            return item, dados
    return NOME_ARMA_DESARMADA, dict(_ARMA_DESARMADA)


def _criar_inimigo(nome: str) -> Inimigo | None:
    dados = regras.get_monster(nome)
    if not dados:
        return None
    nome_ataque, bonus, dano_dado = motor.parse_ataque_monstro(dados["ataque"])
    return Inimigo(
        nome=nome,
        hp=dados["hp"],
        max_hp=dados["hp"],
        ca=dados["ac"],
        bonus_ataque=bonus,
        dano_dado=dano_dado,
        nome_ataque=nome_ataque,
    )


def iniciar_combate(
    nomes_propostos: list[str],
    atributos_heroi: dict,
    ca_heroi: int,
    rng: random.Random | None = None,
) -> tuple[CombatState, list[str], int]:
    """Cria o combate a partir do bestiário real. Nomes propostos que não
    existem em data/monsters.json são descartados; se nada sobrar, um
    monstro de Nível 1 é sorteado — nunca mais o `{"nome": "Inimigo", "hp":
    10}` genérico de antes da Etapa 3.

    Devolve (estado, eventos narráveis, dano recebido de surpresa) — um
    inimigo mais rápido que o herói na iniciativa ataca antes que ele possa
    reagir."""
    dado = rng or random
    inimigos = [i for i in (_criar_inimigo(n) for n in nomes_propostos) if i is not None]
    if not inimigos:
        candidatos = regras.get_monstros_nivel_1()
        if candidatos:
            escolhido = _criar_inimigo(dado.choice(candidatos))
            if escolhido:
                inimigos = [escolhido]

    c_state = CombatState(ativo=True, inimigos=inimigos)
    if not inimigos:
        return c_state, ["A cena não tinha um monstro reconhecível no bestiário — combate não iniciado."], 0

    eventos: list[str] = [f"⚔️ Surge{'m' if len(inimigos) > 1 else ''}: {', '.join(i.nome for i in inimigos)}!"]

    mod_destreza_heroi = motor.calcular_modificador(atributos_heroi.get("destreza", 10))
    iniciativa_heroi = motor.rolar_iniciativa(mod_destreza_heroi, rng)

    # -1 representa o herói na ordem — ver domain/state.py:CombatState.
    ordem: list[tuple[int, int]] = [(-1, iniciativa_heroi)]  # (índice, iniciativa)
    dano_surpresa = 0
    for idx, inimigo in enumerate(inimigos):
        dados_monstro = regras.get_monster(inimigo.nome) or {}
        mod_destreza_inimigo = motor.calcular_modificador(dados_monstro.get("destreza", 10))
        iniciativa_inimigo = motor.rolar_iniciativa(mod_destreza_inimigo, rng)
        ordem.append((idx, iniciativa_inimigo))
        if iniciativa_inimigo <= iniciativa_heroi:
            continue
        resultado = motor.resolver_ataque(inimigo.bonus_ataque, ca_heroi, rng)
        linha = (
            f"🎲 {inimigo.nome} é mais rápido e ataca de surpresa: "
            f"d20({resultado.rolagem})+{resultado.bonus}={resultado.total} vs CA {ca_heroi} → "
        )
        dados = DadosRolagem(
            tipo="ataque", quem=inimigo.nome, alvo="heroi", d20=resultado.rolagem, bonus=resultado.bonus,
            total=resultado.total, ca=ca_heroi, sucesso=resultado.acerto, critico=resultado.critico,
            falha_critica=resultado.falha_critica,
        )
        if resultado.acerto:
            dano = motor.calcular_dano(inimigo.dano_dado, resultado.critico, rng)
            dano_surpresa += dano
            dados.dano = dano
            texto = linha + f"ACERTO{' CRÍTICO' if resultado.critico else ''}! {dano} de dano."
            eventos.append(EventoRolagem(texto, dados))
        else:
            eventos.append(EventoRolagem(linha + "ERROU.", dados))

    # Ordem final: maior iniciativa primeiro; empate favorece o herói (-1
    # antes de qualquer índice ≥0), critério arbitrário mas determinístico.
    ordem.sort(key=lambda par: (-par[1], par[0]))
    c_state.ordem_iniciativa = [idx for idx, _ in ordem]
    c_state.turno_atual = 0

    return c_state, eventos, dano_surpresa


def turno_jogador(
    c_state: CombatState,
    atributos_heroi: dict,
    inventario: list[str],
    arma_proposta: str | None,
    alvo_proposto: str | None,
    rng: random.Random | None = None,
    nivel: int = 1,
) -> list[str]:
    """Resolve o ataque do jogador contra um inimigo vivo, mutando
    `c_state.inimigos` in place (mesmo padrão de reatribuição de coluna JSON
    do resto do projeto — quem chama ainda precisa reatribuir `combat_state`
    inteiro para o SQLAlchemy detectar a mudança, ver Lição 03)."""
    vivos = [i for i in c_state.inimigos if i.hp > 0]
    if not vivos:
        return []

    alvo = next((i for i in vivos if i.nome == alvo_proposto), vivos[0])
    nome_arma, dados_arma = escolher_arma(inventario, arma_proposta)
    mod_atributo, attr_usado = _mod_para_arma(atributos_heroi, dados_arma.get("propriedades", []))
    prof = motor.bonus_proficiencia(nivel)
    bonus_ataque = prof + mod_atributo

    resultado = motor.resolver_ataque(bonus_ataque, alvo.ca, rng)
    linha = (
        f"🎲 Você ataca {alvo.nome} com {nome_arma}: "
        f"d20({resultado.rolagem})+{bonus_ataque}={resultado.total} vs CA {alvo.ca} → "
    )
    dados = DadosRolagem(
        tipo="ataque", quem="heroi", alvo=alvo.nome, d20=resultado.rolagem, bonus=bonus_ataque,
        total=resultado.total, ca=alvo.ca, sucesso=resultado.acerto, critico=resultado.critico,
        falha_critica=resultado.falha_critica, atributo=attr_usado, arma=nome_arma,
        partes_bonus=[
            {"rotulo": motor.ATRIBUTO_LABEL[attr_usado], "valor": mod_atributo},
            {"rotulo": "Proficiência", "valor": prof},
        ],
    )
    if not resultado.acerto:
        return [EventoRolagem(linha + "ERROU.", dados)]

    # weapons.json só tem o dado base ("1d6"); o modificador de atributo —
    # o mesmo usado no bônus de ataque — entra aqui, fora do crítico (que
    # dobra dados, não modificador). O ataque de monstro já vem com o mod
    # embutido no texto de data/monsters.json (parse_ataque_monstro), por
    # isso turno_inimigos() não repete essa soma.
    dano = motor.calcular_dano(dados_arma["dano"], resultado.critico, rng) + mod_atributo
    alvo.hp = max(0, alvo.hp - dano)
    critico_txt = " CRÍTICO" if resultado.critico else ""
    linha += f"ACERTO{critico_txt}! {dano} de dano. {alvo.nome}: {alvo.hp}/{alvo.max_hp} PV."
    dados.dano = dano
    eventos: list[str] = [EventoRolagem(linha, dados)]
    if alvo.hp == 0:
        eventos.append(EventoRolagem(f"💀 {alvo.nome} cai morto.", EventoStatus(tipo="morte_inimigo", quem=alvo.nome)))
    return eventos


def turno_inimigos(c_state: CombatState, ca_heroi: int, rng: random.Random | None = None) -> tuple[list[str], int]:
    """Cada inimigo vivo ataca o herói, na ordem de `c_state.ordem_iniciativa`
    (Etapa 7) — antes disso, todo mundo atacava de uma vez, na ordem de
    spawn. Um herói contra N (decisão de escopo §9.3 do PLANO_MESTRE.md,
    sem abstração de mesa multi-jogador); combates sem ordem calculada (ex:
    `CombatState` montado à mão em teste, sem passar por `iniciar_combate`)
    caem de volta pra ordem de `inimigos`, pra não quebrar chamadas antigas."""
    eventos: list[str] = []
    dano_total = 0
    ordem = [idx for idx in c_state.ordem_iniciativa if idx >= 0] or list(range(len(c_state.inimigos)))
    for turno_idx, idx in enumerate(ordem):
        if idx >= len(c_state.inimigos):
            continue
        inimigo = c_state.inimigos[idx]
        if inimigo.hp <= 0:
            continue
        c_state.turno_atual = turno_idx
        resultado = motor.resolver_ataque(inimigo.bonus_ataque, ca_heroi, rng)
        linha = (
            f"🎲 {inimigo.nome} ataca com {inimigo.nome_ataque}: "
            f"d20({resultado.rolagem})+{resultado.bonus}={resultado.total} vs CA {ca_heroi} → "
        )
        dados = DadosRolagem(
            tipo="ataque", quem=inimigo.nome, alvo="heroi", d20=resultado.rolagem, bonus=resultado.bonus,
            total=resultado.total, ca=ca_heroi, sucesso=resultado.acerto, critico=resultado.critico,
            falha_critica=resultado.falha_critica,
        )
        if resultado.acerto:
            dano = motor.calcular_dano(inimigo.dano_dado, resultado.critico, rng)
            dano_total += dano
            dados.dano = dano
            texto = linha + f"ACERTO{' CRÍTICO' if resultado.critico else ''}! {dano} de dano."
            eventos.append(EventoRolagem(texto, dados))
        else:
            eventos.append(EventoRolagem(linha + "ERROU.", dados))
    c_state.turno_atual = 0  # a rodada de inimigos acabou; a próxima começa no herói de novo
    return eventos, dano_total


def turno_morte(c_state: CombatState, rng: random.Random | None = None) -> tuple[list[str], int]:
    """O herói está a 0 PV: um teste de morte por turno, em vez de agir.
    Devolve (eventos, novo hp) — hp volta a 1 se ele se estabiliza ou
    recupera a consciência; continua 0 enquanto o resultado está em aberto."""
    resultado = motor.rolar_teste_morte(rng)
    evento_base = f"🎲 Teste de morte: d20({resultado.rolagem}) → {resultado.resultado}."
    dados = DadosRolagem(
        tipo="morte", quem="heroi", d20=resultado.rolagem,
        sucesso=resultado.resultado in ("sucesso", "estabilizado_critico"),
        critico=resultado.resultado == "estabilizado_critico",
        falha_critica=resultado.resultado == "falha_critica",
    )

    if resultado.resultado == "estabilizado_critico":
        c_state.sucessos_morte = 0
        c_state.falhas_morte = 0
        return [EventoRolagem(evento_base + " Recupera a consciência com 1 PV!", dados)], 1

    if resultado.resultado == "falha_critica":
        c_state.falhas_morte += 2
    elif resultado.resultado == "falha":
        c_state.falhas_morte += 1
    else:
        c_state.sucessos_morte += 1

    texto = evento_base + f" ({c_state.sucessos_morte} sucessos, {c_state.falhas_morte} falhas)"
    eventos: list[str] = [EventoRolagem(texto, dados)]

    if c_state.falhas_morte >= 3:
        c_state.ativo = False
        c_state.resultado = "morte"
        eventos.append("💀 Três falhas. O fim da jornada.")
        return eventos, 0

    if c_state.sucessos_morte >= 3:
        c_state.ativo = False
        c_state.resultado = "estabilizado"
        c_state.sucessos_morte = 0
        c_state.falhas_morte = 0
        eventos.append("🩸 Estabilizado. Você sobrevive, ferido.")
        return eventos, 1

    return eventos, 0


def resolver_turno(
    c_state: CombatState,
    hp_atual: int,
    ca_heroi: int,
    atributos_heroi: dict,
    inventario: list[str],
    comando: dict,
    rng: random.Random | None = None,
    nivel: int = 1,
) -> tuple[int, list[str]]:
    """O ponto de entrada usado por routers/game.py durante um combate já
    ativo. Muta `c_state` in place; devolve (novo hp do herói, eventos)."""
    if hp_atual <= 0:
        eventos_morte, hp_morte = turno_morte(c_state, rng)
        return hp_morte, eventos_morte

    eventos: list[str] = []
    if comando.get("tipo") == "atacar":
        eventos += turno_jogador(
            c_state, atributos_heroi, inventario, comando.get("arma"), comando.get("alvo"), rng, nivel
        )
    else:
        eventos.append("Você hesita e não ataca desta vez.")

    if all(i.hp <= 0 for i in c_state.inimigos):
        c_state.ativo = False
        c_state.resultado = "vitoria"
        eventos.append("🏆 Combate vencido!")
        return hp_atual, eventos

    eventos_inimigos, dano = turno_inimigos(c_state, ca_heroi, rng)
    eventos += eventos_inimigos
    hp_novo = max(0, hp_atual - dano)
    if hp_novo == 0 and hp_atual > 0:
        eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")

    return hp_novo, eventos
