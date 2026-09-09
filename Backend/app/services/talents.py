"""Talentos e escolhas de nível (Fase 3 do plano "jogo completo", ADR-0034).

Subir de nível continua automático (PV, técnicas, Foco); o que muda é que
cada nível novo deixa uma ESCOLHA pendente para o jogador resolver na tela:
+1 num atributo ou um talento. Nos marcos 3 e 7 a escolha é a especialização
(explorador/diplomata/combatente) que já existia no Mundo Vivo. Nenhum
talento é regra em texto: cada um vira um número num canal que o motor já
tem (dano, defesa, PV por nível, vantagem em teste, desconto no mercador).

`escolher_nivel` nunca é ferramenta do narrador — decisão de jogador entra
só pela interface (`/game/action`), mesma regra de `escolher_especializacao`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.rules_engine import ATRIBUTOS_VALIDOS, NIVEL_MAXIMO

NIVEIS_COM_ESCOLHA = {2, 4, 5, 6, 8, 9, 10}
NIVEIS_DE_ESPECIALIZACAO = {3, 7}
ESPECIALIZACOES = ("explorador", "diplomata", "combatente")
ATRIBUTO_MAXIMO = 20


def _t(id_: str, nome: str, descricao: str, nivel_min: int = 2, **efeito: object) -> dict:
    return {"id": id_, "nome": nome, "descricao": descricao, "nivel_min": nivel_min, "efeito": efeito}


TALENTOS_COMUNS: list[dict] = [
    _t("robusto", "Robusto", "+1 PV máximo por nível (conta os níveis que você já tem).", hp_por_nivel=1),
    _t("couro_duro", "Couro duro", "+1 de Defesa permanente.", ca=1),
    _t("sortudo", "Sortudo", "Vantagem em testes de Destreza.", vantagem_atributo="destreza"),
    _t("olho_de_mercador", "Olho de mercador", "Preços 15% melhores ao comprar.", desconto=15),
    _t("pele_de_pedra", "Pele de pedra", "+1 de Defesa permanente.", nivel_min=6, ca=1),
    _t("presenca", "Presença", "Vantagem em testes de Carisma.", vantagem_atributo="carisma"),
    _t("olhar_atento", "Olhar atento", "Vantagem em testes de Sabedoria.", vantagem_atributo="sabedoria"),
]

TALENTOS_POR_CLASSE: dict[str, list[dict]] = {
    "Guerreiro": [_t("mestre_de_armas", "Mestre de armas", "+1 de dano em ataques e técnicas.", nivel_min=4, dano=1)],
    "Bárbaro": [_t("furia_maior", "Fúria maior", "+1 de dano em ataques e técnicas.", nivel_min=4, dano=1)],
    "Paladino": [_t("juramento", "Juramento firme", "+1 de Defesa permanente.", nivel_min=4, ca=1)],
    "Ladino": [_t("golpe_certeiro", "Golpe certeiro", "+1 de dano em ataques e técnicas.", nivel_min=4, dano=1)],
    "Patrulheiro": [_t("rastreador", "Rastreador", "Vantagem em testes de Sabedoria.", vantagem_atributo="sabedoria")],
    "Monge": [_t("corpo_de_ferro", "Corpo de ferro", "+1 de Defesa permanente.", nivel_min=4, ca=1)],
    "Clérigo": [_t("vigor_sagrado", "Vigor sagrado", "+1 PV máximo por nível.", hp_por_nivel=1)],
    "Druida": [_t("pele_de_carvalho", "Pele de carvalho", "+1 de Defesa permanente.", nivel_min=4, ca=1)],
    "Bardo": [_t("lingua_de_prata", "Língua de prata", "Vantagem em testes de Carisma.", vantagem_atributo="carisma")],
    "Mago": [
        _t("mente_afiada", "Mente afiada", "Vantagem em testes de Inteligência.", vantagem_atributo="inteligencia")
    ],
    "Feiticeiro": [_t("sangue_arcano", "Sangue arcano", "+1 de dano em ataques e técnicas.", nivel_min=4, dano=1)],
    "Bruxo": [_t("pacto_sombrio", "Pacto sombrio", "+1 de dano em ataques e técnicas.", nivel_min=4, dano=1)],
}


def catalogo(classe: str) -> list[dict]:
    return [*TALENTOS_COMUNS, *TALENTOS_POR_CLASSE.get(classe, [])]


def talento(id_: str, classe: str) -> dict | None:
    return next((t for t in catalogo(classe) if t["id"] == id_), None)


@dataclass
class Modificadores:
    dano: int = 0
    ca: int = 0
    hp_por_nivel: int = 0
    desconto: int = 0
    vantagens: set[str] = field(default_factory=set)


def modificadores(talentos: list[str], classe: str) -> Modificadores:
    mods = Modificadores()
    for id_ in talentos:
        t = talento(id_, classe)
        if not t:
            continue
        ef = t["efeito"]
        mods.dano += int(ef.get("dano", 0))
        mods.ca += int(ef.get("ca", 0))
        mods.hp_por_nivel += int(ef.get("hp_por_nivel", 0))
        mods.desconto += int(ef.get("desconto", 0))
        if ef.get("vantagem_atributo"):
            mods.vantagens.add(str(ef["vantagem_atributo"]))
    return mods


def opcoes_para(classe: str, nivel: int, talentos_ja: list[str], atributos: dict) -> list[dict]:
    """O que o jogador pode escolher no nível `nivel`."""
    if nivel in NIVEIS_DE_ESPECIALIZACAO:
        return [
            {"tipo": "especializacao", "id": e, "nome": e.capitalize(),
             "descricao": {"explorador": "+1 em testes de exploração", "diplomata": "+1 em testes sociais",
                           "combatente": "+1 de dano"}[e]}
            for e in ESPECIALIZACOES
        ]
    opcoes = []
    for a in sorted(ATRIBUTOS_VALIDOS):
        atual = atributos.get(a, 10)
        if atual < ATRIBUTO_MAXIMO:
            opcoes.append({
                "tipo": "atributo", "id": a, "nome": f"+1 em {a.capitalize()}",
                "descricao": f"{a.capitalize()} {atual} → {min(ATRIBUTO_MAXIMO, atual + 1)}",
            })
    opcoes += [
        {"tipo": "talento", "id": t["id"], "nome": t["nome"], "descricao": t["descricao"]}
        for t in catalogo(classe)
        if t["id"] not in talentos_ja and nivel >= t["nivel_min"]
    ]
    return opcoes


def nivel_com_escolha(nivel: int) -> bool:
    return nivel in NIVEIS_COM_ESCOLHA or nivel in NIVEIS_DE_ESPECIALIZACAO


assert NIVEL_MAXIMO >= max(NIVEIS_COM_ESCOLHA)
