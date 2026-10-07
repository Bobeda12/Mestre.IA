"""Orquestra o combate ligando o bestiário real (infra/data_manager.py) à
resolução determinística do juiz (services/rules_engine.py).

O narrador (services/narrator.py) PROPÕE — quais monstros encaixam na cena,
qual arma e alvo o jogador quis usar; este módulo DECIDE — acerto, dano,
iniciativa, morte. Zero LLM aqui, mesmo padrão de fronteira de confiança do
ADR-0002 (Etapa 1), agora aplicado ao combate em vez do point-buy.

Ver ADR-0006 para a decisão de arquitetura por trás desta separação."""

import random

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import Aliado, CombatState, Inimigo
from app.infra.data_manager import regras
from app.services import rules_engine as motor
from app.services.class_abilities import CONJURADORES, dado_do_pulso, limite_foco, perfil_classe

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


def escolher_arma(inventario: list[str], proposta: str | None, equipada: str | None = None) -> tuple[str, dict]:
    """O narrador propõe a arma que o jogador quis usar; aqui o servidor
    confirma que ela existe no arsenal E está na mochila do herói. Se a
    proposta falhar, cai para a arma EQUIPADA (Fase 1, ADR-0033), depois
    para a primeira arma reconhecida no inventário, e por fim para ataque
    desarmado — nunca para uma arma inventada."""
    if proposta:
        dados = regras.get_weapon(proposta)
        if dados and proposta in inventario:
            return proposta, dados
    if equipada and equipada in inventario:
        dados = regras.get_weapon(equipada)
        if dados:
            return equipada, dados
    for item in inventario:
        dados = regras.get_weapon(item)
        if dados:
            return item, dados
    return NOME_ARMA_DESARMADA, dict(_ARMA_DESARMADA)


def _criar_inimigo(nome: str, nome_exibicao: str | None = None) -> Inimigo | None:
    """`nome_exibicao` (Parte 2, item J da rodada de conserto) — a PELE de
    um arquétipo: `nome` continua sendo a ficha real (HP/CA/dano, sempre do
    bestiário), só o nome mostrado ao jogador muda. `None` (o caso comum,
    inclusive todo o resto deste arquivo) mostra o nome do arquétipo direto,
    como sempre foi."""
    dados = regras.get_monster(nome)
    if not dados:
        return None
    nome_ataque, bonus, dano_dado = motor.parse_ataque_monstro(dados["ataque"])
    return Inimigo(
        nome=nome_exibicao or nome,
        arquetipo=nome,
        xp=dados.get("xp", 0),
        hp=dados["hp"],
        max_hp=dados["hp"],
        ca=dados["ac"],
        bonus_ataque=bonus,
        dano_dado=dano_dado,
        nome_ataque=nome_ataque,
        comportamento=dados.get("comportamento", ""),
    )


def iniciar_combate(
    nomes_propostos: list[str],
    atributos_heroi: dict,
    ca_heroi: int,
    rng: random.Random | None = None,
    nivel_heroi: int = 1,
    chefe_reservado: str | None = None,
) -> tuple[CombatState, list[str], int]:
    """Cria o combate a partir do bestiário real.

    Nomes propostos que batem exato com o catálogo usam a ficha e o nome
    dele, como sempre. Um nome que NÃO bate (Parte 2, item J — "chega de
    goblins") não é mais descartado: vira a PELE de um arquétipo sorteado
    da banda de nível do herói (`rules_engine.desafio_sugerido`) — a ficha
    (HP/CA/dano/comportamento) é sempre a do arquétipo real, só o nome
    exibido é o que o modelo propôs. Mesmo padrão "o modelo propõe, o
    servidor decide" do ADR-0002, já usado em `mover(descricao_proposta)`
    para locais. Se nada sobrar (bestiário vazio, banda sem candidato), um
    monstro de Nível 1 é sorteado — nunca mais o `{"nome": "Inimigo", "hp":
    10}` genérico de antes da Etapa 3.

    Devolve (estado, eventos narráveis, dano recebido de surpresa) — um
    inimigo mais rápido que o herói na iniciativa ataca antes que ele possa
    reagir."""
    dado = rng or random
    # (inimigo criado, nome do ARQUÉTIPO que decide a ficha) — guardado à
    # parte porque `inimigo.nome` pode ser uma pele, e a rolagem de
    # iniciativa abaixo precisa da destreza do arquétipo de verdade, não
    # de um nome inventado que não existe em data/monsters.json.
    pares: list[tuple[Inimigo, str]] = []
    # Fase 5 (ADR-0035) — o chefe do arco: ficha reservada por `abrir_arco`,
    # fora do orçamento e das bandas do nível; o primeiro nome proposto
    # pelo narrador vira a pele dele.
    if chefe_reservado and regras.get_monster(chefe_reservado):
        pele = str(nomes_propostos[0]).strip()[:80] if nomes_propostos else None
        inimigo_chefe = _criar_inimigo(chefe_reservado, nome_exibicao=pele or None)
        if inimigo_chefe:
            pares.append((inimigo_chefe, chefe_reservado))
            nomes_propostos = list(nomes_propostos)[1:]
    bandas = motor.desafio_sugerido(nivel_heroi)
    candidatos = [c for banda in bandas for c in regras.get_monstros_por_banda(banda)]
    # Encontros solo curtos: orçamento impede tropas inteiras ou chefes
    # fora da faixa, mesmo quando o narrador propõe um nome válido.
    limite = min(3, 1 + nivel_heroi // 3)
    orcamento = 75 + nivel_heroi * 100
    for nome_proposto in nomes_propostos[:limite]:
        nome_proposto = str(nome_proposto).strip()[:80]
        if not nome_proposto:
            continue
        if regras.get_monster(nome_proposto) and nome_proposto in candidatos:
            inimigo = _criar_inimigo(nome_proposto)
            if inimigo:
                pares.append((inimigo, nome_proposto))
            continue
        if not candidatos:
            continue
        arquetipo = dado.choice(candidatos)
        inimigo = _criar_inimigo(arquetipo, nome_exibicao=nome_proposto)
        if inimigo:
            pares.append((inimigo, arquetipo))

    if not pares:
        candidatos = regras.get_monstros_nivel_1()
        if candidatos:
            escolhido_nome = dado.choice(candidatos)
            escolhido = _criar_inimigo(escolhido_nome)
            if escolhido:
                pares = [(escolhido, escolhido_nome)]

    selecionados: list[tuple[Inimigo, str]] = []
    custo = 0
    for inimigo, arquetipo in pares:
        if selecionados and custo + inimigo.xp > orcamento:
            continue
        custo += inimigo.xp
        selecionados.append((inimigo, arquetipo))
    pares = selecionados
    contagens: dict[str, int] = {}
    for inimigo, _ in pares:
        contagens[inimigo.nome] = contagens.get(inimigo.nome, 0) + 1
        if contagens[inimigo.nome] > 1:
            inimigo.nome += f" {contagens[inimigo.nome]}"
    inimigos = [i for i, _ in pares]
    foco = limite_foco(nivel_heroi)
    c_state = CombatState(ativo=bool(inimigos), inimigos=inimigos, foco=foco, foco_max=foco)
    if not inimigos:
        return c_state, ["A cena não tinha um monstro reconhecível no bestiário — combate não iniciado."], 0

    eventos: list[str] = [f"⚔️ Surge{'m' if len(inimigos) > 1 else ''}: {', '.join(i.nome for i in inimigos)}!"]

    # A iniciativa, a fila e quem age antes do herói são do motor de turnos
    # (`turnos.abrir`); aqui só nasce a lista de inimigos. O terceiro valor
    # (dano de surpresa) ficou em 0 por compatibilidade de assinatura.
    return c_state, eventos, 0


def turno_jogador(
    c_state: CombatState,
    atributos_heroi: dict,
    inventario: list[str],
    arma_proposta: str | None,
    alvo_proposto: str | None,
    rng: random.Random | None = None,
    nivel: int = 1,
    vantagem: bool | None = None,
    investida: bool = False,
    classe: str | None = None,
    arma_equipada: str | None = None,
    dano_extra: str | None = None,
) -> list[str]:
    """Resolve o ataque do jogador contra um inimigo vivo, mutando
    `c_state.inimigos` in place (mesmo padrão de reatribuição de coluna JSON
    do resto do projeto — quem chama ainda precisa reatribuir `combat_state`
    inteiro para o SQLAlchemy detectar a mudança, ver Lição 03).

    `investida` (Fase 1 da revisão de gameplay — o botão de risco tático):
    -2 no bônus de acerto, +50% no dano — a troca clássica de precisão por
    força, aplicada no servidor, nunca decidida pelo modelo."""
    vivos = [i for i in c_state.inimigos if i.hp > 0 and not i.afastado]
    if not vivos:
        return []

    alvo = next((i for i in vivos if i.nome == alvo_proposto), vivos[0])
    nome_arma, dados_arma = escolher_arma(inventario, arma_proposta, arma_equipada)
    mod_atributo, attr_usado = _mod_para_arma(atributos_heroi, dados_arma.get("propriedades", []))
    if classe in CONJURADORES and arma_proposta is None:
        attr_usado = perfil_classe(classe)["atributo"]
        mod_atributo = motor.calcular_modificador(atributos_heroi.get(attr_usado, 10))
        nome_arma, dados_arma = "Pulso " + ("sagrado" if classe == "Clérigo" else "mágico"), {
            "dano": dado_do_pulso(classe),
        }
    elif classe == "Monge" and arma_proposta is None:
        attr_usado = "destreza"
        mod_atributo = motor.calcular_modificador(atributos_heroi.get(attr_usado, 10))
        nome_arma, dados_arma = "Artes marciais", {"dano": "1d6"}
    if c_state.efeitos_heroi.get("precisao", 0):
        vantagem = _combinar_vantagem(vantagem, True)
        c_state.efeitos_heroi.pop("precisao", None)
    prof = motor.bonus_proficiencia(nivel)
    bonus_ataque = prof + mod_atributo + (-2 if investida else 0)

    ca_alvo = alvo.ca - (2 if alvo.efeitos.get("vulneravel", 0) else 0)
    resultado = motor.resolver_ataque(bonus_ataque, ca_alvo, rng, vantagem=vantagem)
    linha = (
        f"🎲 Você {'investe contra' if investida else 'ataca'} {alvo.nome} com {nome_arma}: "
        f"d20({resultado.rolagem})+{bonus_ataque}={resultado.total} vs CA {ca_alvo} → "
    )
    partes_bonus = [
        {"rotulo": motor.ATRIBUTO_LABEL[attr_usado], "valor": mod_atributo},
        {"rotulo": "Proficiência", "valor": prof},
    ]
    if investida:
        partes_bonus.append({"rotulo": "Investida", "valor": -2})
    dados = DadosRolagem(
        tipo="ataque", quem="heroi", alvo=alvo.nome, d20=resultado.rolagem, bonus=bonus_ataque,
        total=resultado.total, ca=ca_alvo, sucesso=resultado.acerto, critico=resultado.critico,
        falha_critica=resultado.falha_critica, atributo=attr_usado, arma=nome_arma,
        partes_bonus=partes_bonus,
        d20_extra=resultado.d20_extra, vantagem=resultado.vantagem,
    )
    if not resultado.acerto:
        return [EventoRolagem(linha + "ERROU.", dados)]

    # weapons.json só tem o dado base ("1d6"); o modificador de atributo —
    # o mesmo usado no bônus de ataque — entra aqui, fora do crítico (que
    # dobra dados, não modificador). O ataque de monstro já vem com o mod
    # embutido no texto de data/monsters.json (parse_ataque_monstro), por
    # isso o ataque do inimigo (`turnos._atacar`) não repete essa soma.
    dano = motor.calcular_dano(dados_arma["dano"], resultado.critico, rng) + mod_atributo
    if classe:
        dano += nivel // 2
        if nivel >= 5:
            dano += motor.calcular_dano("2d6" if nivel >= 10 else "1d6", resultado.critico, rng)
    if dano_extra:  # traço de classe (ex.: ataque furtivo do Ladino); o crítico dobra
        dano += motor.calcular_dano(dano_extra, resultado.critico, rng)
    dano += 3 if alvo.efeitos.get("marcado", 0) else 0
    dano += 2 if c_state.efeitos_heroi.get("furia", 0) else 0
    dano += 2 if c_state.efeitos_heroi.get("lamina", 0) else 0  # Óleo de Lâmina (Fase 1)
    dano = max(1, dano + c_state.bonus_especializacao)
    if c_state.efeitos_heroi.get("enfraquecido", 0):
        dano = max(1, dano - 3)
    if investida:
        dano = dano * 3 // 2
    alvo.hp = max(0, alvo.hp - dano)
    critico_txt = " CRÍTICO" if resultado.critico else ""
    linha += f"ACERTO{critico_txt}! {dano} de dano. {alvo.nome}: {alvo.hp}/{alvo.max_hp} PV."
    dados.dano = dano
    eventos: list[str] = [EventoRolagem(linha, dados)]
    if alvo.hp == 0:
        eventos.append(EventoRolagem(f"💀 {alvo.nome} cai morto.", EventoStatus(tipo="morte_inimigo", quem=alvo.nome)))
    return eventos


def turno_aliado(
    c_state: CombatState, aliado: Aliado, alvo_proposto: str | None, rng: random.Random | None = None,
    vantagem: bool | None = None,
) -> list[str]:
    """Fase 3 da revisão de gameplay (ADR-0027) — resolve o ataque de um
    aliado recrutado contra um inimigo vivo. Mais simples que
    `turno_jogador`: um `Aliado` já carrega `bonus_ataque`/`dano_dado`
    prontos (mesma forma de `Inimigo`, ver domain/state.py), sem escolha de
    arma nem lookup de atributo — ele ainda não tem inventário de combate
    próprio. Quem chama garante que `aliado` está vivo (`ToolExecutor.
    atacar_com_aliado`); esta função não revalida."""
    vivos = [i for i in c_state.inimigos if i.hp > 0 and not i.afastado]
    if not vivos:
        return []
    alvo = next((i for i in vivos if i.nome == alvo_proposto), vivos[0])
    resultado = motor.resolver_ataque(aliado.bonus_ataque, alvo.ca, rng, vantagem=vantagem)
    linha = (
        f"🎲 {aliado.nome} ataca {alvo.nome} com {aliado.nome_ataque or 'um golpe'}: "
        f"d20({resultado.rolagem})+{resultado.bonus}={resultado.total} vs CA {alvo.ca} → "
    )
    dados = DadosRolagem(
        tipo="ataque", quem=aliado.nome, alvo=alvo.nome, d20=resultado.rolagem, bonus=resultado.bonus,
        total=resultado.total, ca=alvo.ca, sucesso=resultado.acerto, critico=resultado.critico,
        falha_critica=resultado.falha_critica, d20_extra=resultado.d20_extra, vantagem=resultado.vantagem,
    )
    if not resultado.acerto:
        return [EventoRolagem(linha + "ERROU.", dados)]

    dano = motor.calcular_dano(aliado.dano_dado, resultado.critico, rng)
    alvo.hp = max(0, alvo.hp - dano)
    critico_txt = " CRÍTICO" if resultado.critico else ""
    linha += f"ACERTO{critico_txt}! {dano} de dano. {alvo.nome}: {alvo.hp}/{alvo.max_hp} PV."
    dados.dano = dano
    eventos: list[str] = [EventoRolagem(linha, dados)]
    if alvo.hp == 0:
        eventos.append(EventoRolagem(f"💀 {alvo.nome} cai morto.", EventoStatus(tipo="morte_inimigo", quem=alvo.nome)))
    return eventos


def _combinar_vantagem(a: bool | None, b: bool | None) -> bool | None:
    """Regra real do 5e: vantagem e desvantagem de fontes diferentes não se
    somam — se as duas se aplicam ao mesmo dado, elas se cancelam. Usado
    para combinar o efeito de uma ação tática do herói (esquivar/investir,
    Fase 1) com o comportamento de matilha de um inimigo específico."""
    if a is None:
        return b
    if b is None:
        return a
    return a if a == b else None


def _escolher_alvo(c_state: CombatState, rng: random.Random | None) -> tuple[str, int | None]:
    """Fase 2 da revisão de gameplay — o inimigo escolhe entre o herói e os
    aliados vivos, peso aleatório entre os dois (regra de primeira passada,
    ver ADR-0027 — ajustar depois com `evals/simulador.py` se um alvo
    "certo" fizer diferença mensurável). Sem aliados vivos — ainda o caso
    comum, só a Fase 3 dá um jeito de recrutar — o alvo é sempre o herói,
    **sem consumir nenhum rng**: byte a byte o comportamento de antes desta
    fase, o que é o que permite testar isto contra a suíte antiga sem
    tocar em nenhum `RngFixo` existente."""
    vivos = [i for i, a in enumerate(c_state.aliados) if a.hp > 0]
    if not vivos:
        return "heroi", None
    dado = rng or random
    candidatos: list[tuple[str, int | None]] = [("heroi", None)] + [("aliado", i) for i in vivos]
    return dado.choice(candidatos)


def _avancar_efeitos(efeitos: dict[str, int]) -> dict[str, int]:
    return {nome: duracao - 1 for nome, duracao in efeitos.items() if duracao > 1}


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

