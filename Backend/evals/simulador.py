"""Simulador de balanceamento: duelos sem LLM e sem banco, pelo caminho real do
juiz (`ToolExecutor.executar`, o mesmo que `/game/action` chama a cada clique).

Uso:
    uv run python -m evals.simulador --n 200 --niveis 1-10 --classes Guerreiro --bot basico
    uv run python -m evals.simulador --n 300 --classes todas --bot tatico

Os números que saem daqui são a referência para mexer em fichas de monstro,
custo de técnica e CD — não a intuição. Ver docs/relatorios/."""

import argparse
import json
import random
from dataclasses import dataclass, field

from app.domain.state import CombatState, Inimigo, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.services import combat, turnos
from app.services import rules_engine as motor
from app.services.class_abilities import RECUA_SEM_OPORTUNIDADE, limite_foco, perfil_classe
from app.services.encounters import preparar_encontro
from app.services.items import auto_equipar
from app.services.tools import ToolExecutor, alcance_do_ataque

POCAO = "Poção de Cura"
LIMIAR_POCAO = 0.35
MAX_TURNOS = 60
MAX_JOGADAS = 400

@dataclass
class Duelo:
    vitoria: bool
    pv_restante: float  # fração do PV máximo; 0 na derrota
    turnos: int
    foco_gasto: int
    caiu_no_turno_1: bool


@dataclass
class Resumo:
    classe: str
    nivel: int
    encontro: str
    banda: str
    bot: str
    n: int
    vitoria: float
    pv_restante: float  # média só entre as vitórias
    turnos: float
    foco_gasto: float
    queda_turno_1: float
    duelos: list[Duelo] = field(default_factory=list, repr=False)


def heroi_de_referencia(classe: str, nivel: int) -> Personagem:
    """Herói em memória, nunca gravado: atributo da classe em 16, o resto
    mediano, o equipamento inicial da classe vestido pelo mesmo
    `auto_equipar` da criação de personagem, e duas poções."""
    detalhes = regras.get_class_details(classe) or {}
    principal = perfil_classe(classe)["atributo"]
    atributos = {a: 10 for a in ("forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma")}
    atributos.update({"constituicao": 12, "destreza": 12, principal: 16})
    # Quem joga de Clérigo ou Paladino põe Força suficiente para vestir a
    # armadura com que a classe começa; sem isso ela fica na mochila.
    inicial = detalhes.get("equipamento_inicial", [])
    exigida = max(((regras.get_item(i) or {}).get("forca_min", 0) for i in inicial), default=0)
    atributos["forca"] = max(atributos["forca"], exigida)
    dado_vida = detalhes.get("dado_vida", 8)
    mod_con = motor.calcular_modificador(atributos["constituicao"])
    hp = dado_vida + mod_con + (nivel - 1) * (dado_vida // 2 + 1 + mod_con)
    heroi = Personagem(
        nome="Referência", raca="Humano", classe=classe, nivel=nivel, xp=motor.XP_POR_NIVEL.get(nivel, 0),
        hp_atual=hp, hp_max=hp, defesa=10, atributos=atributos,
        inventario=[*inicial, POCAO, POCAO], equipamento={},
        dificuldade="Normal", reputacao_npcs={}, monstros_derrotados={}, aliados=[], ouro=0,
    )
    auto_equipar(heroi)
    return heroi


def _abrir_luta(heroi: Personagem, monstros: list[str], rng: random.Random) -> tuple[CombatState, WorldState]:
    """Abre o combate direto no motor: `chefe_reservado` é o que deixa um
    chefe entrar com a própria ficha, fora do orçamento da banda."""
    reservado = monstros[0] if monstros[0] in regras.get_monstros_chefe() else None
    c_state, _, _ = combat.iniciar_combate(
        monstros, heroi.atributos, heroi.defesa, rng, nivel_heroi=heroi.nivel, chefe_reservado=reservado,
    )
    w_state = WorldState(local="Arena", versao_progressao=1, versao_mundo=2)
    preparar_encontro(c_state, w_state, "duelo")
    c_state.foco = c_state.foco_max = limite_foco(heroi.nivel, heroi.classe)  # chega descansado
    alvo = turnos.Alvo(hp=heroi.hp_atual, ca=heroi.defesa, atributos=heroi.atributos, nivel=heroi.nivel)
    turnos.abrir(c_state, alvo, rng)
    heroi.hp_atual = alvo.hp
    return c_state, w_state


def _vivos(c_state: CombatState) -> list[Inimigo]:
    return [i for i in c_state.inimigos if i.hp > 0 and not i.afastado]


ENCERRAR: tuple[str, dict] = ("encerrar_turno", {})


def _livre_para_mover(c_state: CombatState) -> bool:
    preso = any(c_state.efeitos_heroi.get(e, 0) for e in ("caido", "contido"))
    return not c_state.movimento_usado and not preso


def _alcanca(heroi: Personagem, c_state: CombatState, alvo: Inimigo, alcance: str) -> bool:
    """O herói consegue usar algo de `alcance` em `alvo` agora? Corpo a
    corpo num alvo longe só com o movimento livre e sem medo."""
    if alcance != "corpo" or alvo.distancia == "perto":
        return True
    return _livre_para_mover(c_state) and not c_state.efeitos_heroi.get("amedrontado", 0)


def _basico(heroi: Personagem, c_state: CombatState) -> tuple[str, dict]:
    """O que qualquer jogador faz: levanta se caiu, bebe poção com pouca
    vida (ação bônus), ataca o mais ferido que alcança."""
    if c_state.efeitos_heroi.get("caido", 0) and not c_state.movimento_usado:
        return "levantar", {}
    if not c_state.bonus_usada and heroi.hp_atual < LIMIAR_POCAO * heroi.hp_max and POCAO in heroi.inventario:
        return "usar_item", {"item": POCAO}
    if c_state.acao_usada:
        return ENCERRAR
    alcance = alcance_do_ataque(heroi)
    alvos = [i for i in _vivos(c_state) if _alcanca(heroi, c_state, i, alcance)]
    if not alvos:
        return ENCERRAR
    return "atacar", {"alvo": min(alvos, key=lambda i: i.hp).id}


def _jogada_basica(heroi: Personagem, c_state: CombatState) -> tuple[str, dict]:
    return _basico(heroi, c_state)


def _jogada_tatica(heroi: Personagem, c_state: CombatState) -> tuple[str, dict]:
    """Um jogador que aprendeu o sistema: usa a ação bônus da classe, a
    técnica mais forte que o Foco paga, cura só quando ferido, e quem luta de
    longe abre distância depois de agir."""
    nome, args = _basico(heroi, c_state)
    if nome in ("levantar", "usar_item"):
        return nome, args
    vivos = _vivos(c_state)
    disponiveis = [
        h for h in perfil_classe(heroi.classe)["habilidades"]
        if h["nivel"] <= heroi.nivel and h["custo"] <= c_state.foco
    ]

    def escolher(custo: str) -> tuple[str, dict] | None:
        do_custo = [h for h in disponiveis if h["acao"] == custo]
        ferido = heroi.hp_atual < 0.6 * heroi.hp_max
        reforco = next((
            h for h in do_custo if h["alvo"] == "heroi"
            # cura só com vida faltando; reforço puro quando não há outro ativo
            and (ferido if (h.get("cura") or h.get("cura_fixa")) else not c_state.efeitos_heroi)
        ), None)
        if reforco is not None:
            return "usar_habilidade", {"habilidade": reforco["id"]}
        melhor: tuple[tuple[int, int], dict, Inimigo | None] | None = None
        for h in do_custo:
            if not h.get("dano"):
                continue
            alvos = [i for i in vivos if _alcanca(heroi, c_state, i, h["alcance"])]
            if h["alvo"] == "inimigo" and not alvos:
                continue
            chave = (h["custo"], h["nivel"])
            if melhor is None or chave > melhor[0]:
                melhor = (chave, h, min(alvos, key=lambda i: i.hp) if h["alvo"] == "inimigo" else None)
        if melhor is None:
            return None
        _, h, alvo = melhor
        return "usar_habilidade", {"habilidade": h["id"], **({"alvo": alvo.nome} if alvo else {})}

    if not c_state.bonus_usada and vivos:
        bonus = escolher("bonus")
        if bonus is not None:
            return bonus
    if not c_state.acao_usada:
        return escolher("acao") or (nome, args)
    # Abrir distância só compensa para quem recua sem levar golpe: o inimigo
    # que volta a avançar ataca com desvantagem.
    de_longe = alcance_do_ataque(heroi) != "corpo" and heroi.classe in RECUA_SEM_OPORTUNIDADE
    if de_longe and _livre_para_mover(c_state) and any(i.distancia == "perto" for i in vivos):
        return "recuar", {}
    return ENCERRAR


BOTS = {"basico": _jogada_basica, "tatico": _jogada_tatica}


def simular_duelo(classe: str, nivel: int, monstros: list[str], bot: str, semente: str) -> Duelo:
    rng = random.Random(semente)
    heroi = heroi_de_referencia(classe, nivel)
    c_state, w_state = _abrir_luta(heroi, monstros, rng)
    q_state = QuestLog()
    foco_gasto, jogadas = 0, 0
    caiu_no_turno_1 = heroi.hp_atual <= 0
    rodadas = c_state.rodada
    while c_state.ativo and heroi.hp_atual > 0 and jogadas < MAX_JOGADAS and c_state.rodada <= MAX_TURNOS:
        jogadas += 1
        rodadas = c_state.rodada
        foco_antes = c_state.foco
        nome, args = BOTS[bot](heroi, c_state)
        # Um executor por jogada, como um clique.
        resultado, ok = ToolExecutor(heroi, c_state, w_state, q_state, rng).executar(
            nome, json.dumps(args, ensure_ascii=False)
        )
        if not ok:
            raise RuntimeError(f"jogada recusada pelo juiz: {nome} {args} → {resultado}")
        foco_gasto += max(0, foco_antes - c_state.foco)
        if rodadas <= 1 and heroi.hp_atual <= 0:
            caiu_no_turno_1 = True
    vitoria = c_state.resultado == "vitoria" and heroi.hp_atual > 0
    return Duelo(
        vitoria=vitoria, pv_restante=heroi.hp_atual / heroi.hp_max if vitoria else 0.0,
        turnos=rodadas, foco_gasto=foco_gasto, caiu_no_turno_1=caiu_no_turno_1,
    )


def simular(classe: str, nivel: int, monstros: list[str], bot: str, n: int, semente: int = 0,
            banda: str = "") -> Resumo:
    encontro = " + ".join(monstros)
    duelos = [simular_duelo(classe, nivel, monstros, bot, f"{semente}:{classe}:{nivel}:{encontro}:{bot}:{k}")
              for k in range(n)]
    vitorias = [d for d in duelos if d.vitoria]
    return Resumo(
        classe=classe, nivel=nivel, encontro=encontro, banda=banda, bot=bot, n=n,
        vitoria=len(vitorias) / n,
        pv_restante=sum(d.pv_restante for d in vitorias) / len(vitorias) if vitorias else 0.0,
        turnos=sum(d.turnos for d in duelos) / n,
        foco_gasto=sum(d.foco_gasto for d in duelos) / n,
        queda_turno_1=sum(d.caiu_no_turno_1 for d in duelos) / n,
        duelos=duelos,
    )


def encontros_do_nivel(nivel: int) -> list[tuple[str, list[str]]]:
    """Cada monstro das bandas sugeridas ao nível, sozinho, mais o chefe que
    um arco aberto naquele nível sortearia."""
    pares = [(banda, [nome]) for banda in motor.desafio_sugerido(nivel)
             for nome in regras.get_monstros_por_banda(banda)]
    ja = {m[0] for _, m in pares}
    pares += [("chefe do arco", [nome]) for nome in regras.chefes_para_nivel(nivel) if nome not in ja]
    return pares


def tabela(resumos: list[Resumo]) -> str:
    linhas = ["| Classe | Nível | Banda | Encontro | Vitória | PV restante | Turnos | Foco gasto | Queda no turno 1 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in resumos:
        linhas.append(
            f"| {r.classe} | {r.nivel} | {r.banda} | {r.encontro} | {r.vitoria:.0%} | {r.pv_restante:.0%} | "
            f"{r.turnos:.1f} | {r.foco_gasto:.1f} | {r.queda_turno_1:.0%} |"
        )
    return "\n".join(linhas)


def _faixa(texto: str) -> list[int]:
    inicio, _, fim = texto.partition("-")
    return list(range(int(inicio), int(fim or inicio) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=200, help="duelos por par (classe, nível, encontro)")
    parser.add_argument("--niveis", default="1-10")
    parser.add_argument("--classes", default="Guerreiro", help="nomes separados por vírgula, ou 'todas'")
    parser.add_argument("--bot", default="basico", choices=sorted(BOTS))
    parser.add_argument("--semente", type=int, default=0)
    opcoes = parser.parse_args()
    classes = regras.get_classes_list() if opcoes.classes == "todas" else opcoes.classes.split(",")
    resumos = [
        simular(classe, nivel, monstros, opcoes.bot, opcoes.n, opcoes.semente, banda)
        for classe in classes for nivel in _faixa(opcoes.niveis) for banda, monstros in encontros_do_nivel(nivel)
    ]
    print(tabela(resumos))


if __name__ == "__main__":
    main()
