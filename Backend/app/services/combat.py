"""Orquestra o combate ligando o bestiário real (infra/data_manager.py) à
resolução determinística do juiz (services/rules_engine.py).

O narrador (services/narrator.py) PROPÕE — quais monstros encaixam na cena,
qual arma e alvo o jogador quis usar; este módulo DECIDE — acerto, dano,
iniciativa, morte. Zero LLM aqui, mesmo padrão de fronteira de confiança do
ADR-0002 (Etapa 1), agora aplicado ao combate em vez do point-buy.

Ver ADR-0006 para a decisão de arquitetura por trás desta separação."""

import random

from app.domain.state import CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import rules_engine as motor

NOME_ARMA_DESARMADA = "Ataque Desarmado"
_ARMA_DESARMADA = {"dano": "1d1", "propriedades": []}


def _mod_para_arma(atributos: dict, propriedades: list[str]) -> int:
    """Força é o padrão; armas "Sutil" (finesse) usam o melhor entre Força e
    Destreza, e armas de "Munição" (à distância) usam Destreza — regras reais
    do PHB, não simplificação."""
    mod_forca = motor.calcular_modificador(atributos.get("forca", 10))
    mod_destreza = motor.calcular_modificador(atributos.get("destreza", 10))
    if "Sutil" in propriedades:
        return max(mod_forca, mod_destreza)
    if "Munição" in propriedades:
        return mod_destreza
    return mod_forca


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

    eventos = [f"⚔️ Surge{'m' if len(inimigos) > 1 else ''}: {', '.join(i.nome for i in inimigos)}!"]

    mod_destreza_heroi = motor.calcular_modificador(atributos_heroi.get("destreza", 10))
    iniciativa_heroi = motor.rolar_iniciativa(mod_destreza_heroi, rng)

    dano_surpresa = 0
    for inimigo in inimigos:
        dados_monstro = regras.get_monster(inimigo.nome) or {}
        mod_destreza_inimigo = motor.calcular_modificador(dados_monstro.get("destreza", 10))
        iniciativa_inimigo = motor.rolar_iniciativa(mod_destreza_inimigo, rng)
        if iniciativa_inimigo <= iniciativa_heroi:
            continue
        resultado = motor.resolver_ataque(inimigo.bonus_ataque, ca_heroi, rng)
        linha = (
            f"🎲 {inimigo.nome} é mais rápido e ataca de surpresa: "
            f"d20({resultado.rolagem})+{resultado.bonus}={resultado.total} vs CA {ca_heroi} → "
        )
        if resultado.acerto:
            dano = motor.calcular_dano(inimigo.dano_dado, resultado.critico, rng)
            dano_surpresa += dano
            eventos.append(linha + f"ACERTO{' CRÍTICO' if resultado.critico else ''}! {dano} de dano.")
        else:
            eventos.append(linha + "ERROU.")

    return c_state, eventos, dano_surpresa


def turno_jogador(
    c_state: CombatState,
    atributos_heroi: dict,
    inventario: list[str],
    arma_proposta: str | None,
    alvo_proposto: str | None,
    rng: random.Random | None = None,
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
    mod_atributo = _mod_para_arma(atributos_heroi, dados_arma.get("propriedades", []))
    bonus_ataque = motor.BONUS_PROFICIENCIA + mod_atributo

    resultado = motor.resolver_ataque(bonus_ataque, alvo.ca, rng)
    linha = (
        f"🎲 Você ataca {alvo.nome} com {nome_arma}: "
        f"d20({resultado.rolagem})+{bonus_ataque}={resultado.total} vs CA {alvo.ca} → "
    )
    if not resultado.acerto:
        return [linha + "ERROU."]

    # weapons.json só tem o dado base ("1d6"); o modificador de atributo —
    # o mesmo usado no bônus de ataque — entra aqui, fora do crítico (que
    # dobra dados, não modificador). O ataque de monstro já vem com o mod
    # embutido no texto de data/monsters.json (parse_ataque_monstro), por
    # isso turno_inimigos() não repete essa soma.
    dano = motor.calcular_dano(dados_arma["dano"], resultado.critico, rng) + mod_atributo
    alvo.hp = max(0, alvo.hp - dano)
    critico_txt = " CRÍTICO" if resultado.critico else ""
    linha += f"ACERTO{critico_txt}! {dano} de dano. {alvo.nome}: {alvo.hp}/{alvo.max_hp} PV."
    eventos = [linha]
    if alvo.hp == 0:
        eventos.append(f"💀 {alvo.nome} cai morto.")
    return eventos


def turno_inimigos(c_state: CombatState, ca_heroi: int, rng: random.Random | None = None) -> tuple[list[str], int]:
    """Todo inimigo vivo ataca o herói (um herói contra N — decisão de
    escopo §9.3 do PLANO_MESTRE.md, sem abstração de mesa multi-jogador)."""
    eventos: list[str] = []
    dano_total = 0
    for inimigo in c_state.inimigos:
        if inimigo.hp <= 0:
            continue
        resultado = motor.resolver_ataque(inimigo.bonus_ataque, ca_heroi, rng)
        linha = (
            f"🎲 {inimigo.nome} ataca com {inimigo.nome_ataque}: "
            f"d20({resultado.rolagem})+{resultado.bonus}={resultado.total} vs CA {ca_heroi} → "
        )
        if resultado.acerto:
            dano = motor.calcular_dano(inimigo.dano_dado, resultado.critico, rng)
            dano_total += dano
            eventos.append(linha + f"ACERTO{' CRÍTICO' if resultado.critico else ''}! {dano} de dano.")
        else:
            eventos.append(linha + "ERROU.")
    return eventos, dano_total


def turno_morte(c_state: CombatState, rng: random.Random | None = None) -> tuple[list[str], int]:
    """O herói está a 0 PV: um teste de morte por turno, em vez de agir.
    Devolve (eventos, novo hp) — hp volta a 1 se ele se estabiliza ou
    recupera a consciência; continua 0 enquanto o resultado está em aberto."""
    resultado = motor.rolar_teste_morte(rng)
    evento_base = f"🎲 Teste de morte: d20({resultado.rolagem}) → {resultado.resultado}."

    if resultado.resultado == "estabilizado_critico":
        c_state.sucessos_morte = 0
        c_state.falhas_morte = 0
        return [evento_base + " Recupera a consciência com 1 PV!"], 1

    if resultado.resultado == "falha_critica":
        c_state.falhas_morte += 2
    elif resultado.resultado == "falha":
        c_state.falhas_morte += 1
    else:
        c_state.sucessos_morte += 1

    eventos = [evento_base + f" ({c_state.sucessos_morte} sucessos, {c_state.falhas_morte} falhas)"]

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
) -> tuple[int, list[str]]:
    """O ponto de entrada usado por routers/game.py durante um combate já
    ativo. Muta `c_state` in place; devolve (novo hp do herói, eventos)."""
    if hp_atual <= 0:
        eventos_morte, hp_morte = turno_morte(c_state, rng)
        return hp_morte, eventos_morte

    eventos: list[str] = []
    if comando.get("tipo") == "atacar":
        eventos += turno_jogador(c_state, atributos_heroi, inventario, comando.get("arma"), comando.get("alvo"), rng)
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
