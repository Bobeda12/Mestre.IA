"""Catálogo de técnicas: números e efeitos pertencem ao servidor."""


def _h(id, nome, descricao, nivel, custo, alvo="inimigo", **efeitos):
    return dict(id=id, nome=nome, descricao=descricao, nivel=nivel, custo=custo, alvo=alvo, **efeitos)


CLASSES = {
    "Bárbaro": {
        "estilo": "Fúria e risco: golpes pesados, resistência e dano em área.",
        "atributo": "forca",
        "habilidades": [
            _h(
                "furia",
                "Fúria primordial",
                "Golpe certeiro de 1d8; +2 dano e reduz 2 de cada golpe por 2 rodadas.",
                1,
                2,
                dano="1d8",
                furia=2,
            ),
            _h(
                "rompe_guardas",
                "Rompe-guardas",
                "2d8 de dano; rompe 2 de CA do alvo por 2 rodadas.",
                3,
                2,
                dano="2d8",
                vulneravel=2,
            ),
            _h(
                "terremoto",
                "Terremoto",
                "2d8 em todos os inimigos e reduz 2 de cada golpe recebido nesta rodada.",
                7,
                3,
                "todos",
                dano="2d8",
                protecao=1,
            ),
        ],
    },
    "Guerreiro": {
        "estilo": "Controle marcial: precisão, aparar golpes e abrir a guarda.",
        "atributo": "forca",
        "habilidades": [
            _h(
                "golpe_tatico",
                "Golpe tático",
                "1d8 de dano certeiro; +2 CA contra a reação inimiga.",
                1,
                1,
                dano="1d8",
                guarda=1,
            ),
            _h(
                "desarmar",
                "Desarmar",
                "2d6 de dano e enfraquece o alvo por 2 rodadas (-3 dano).",
                3,
                2,
                dano="2d6",
                enfraquecido=2,
            ),
            _h(
                "tempestade_aco",
                "Tempestade de aço",
                "3d8 de dano em um alvo e +2 CA por 2 rodadas.",
                7,
                3,
                dano="3d8",
                guarda=2,
            ),
        ],
    },
    "Ladino": {
        "estilo": "Emboscadas: preparar vantagem, explorar feridas e impedir reações.",
        "atributo": "destreza",
        "habilidades": [
            _h(
                "ataque_furtivo",
                "Ataque furtivo",
                "1d8 de dano; +1d6 se o alvo já estiver ferido ou vulnerável.",
                1,
                1,
                dano="1d8",
                oportunista=True,
            ),
            _h(
                "bomba_fumaca",
                "Bomba de fumaça",
                "Evita toda a reação inimiga e prepara vantagem no próximo ataque.",
                3,
                2,
                "heroi",
                sumir=True,
                precisao=2,
            ),
            _h(
                "execucao",
                "Execução",
                "3d8 de dano; +2d6 se o alvo estiver abaixo de metade da vida.",
                7,
                3,
                dano="3d8",
                executar=True,
            ),
        ],
    },
    "Monge": {
        "estilo": "Ritmo e mobilidade: punhos ágeis, desvio e interrupção.",
        "atributo": "destreza",
        "habilidades": [
            _h(
                "rajada_punhos",
                "Rajada de punhos",
                "2d4 de dano certeiro; a próxima reação tem desvantagem.",
                1,
                1,
                dano="2d4",
                esquiva=1,
            ),
            _h(
                "palma_atordoante",
                "Palma atordoante",
                "1d8 de dano e interrompe a próxima ação do alvo.",
                3,
                2,
                dano="1d8",
                atordoado=1,
            ),
            _h(
                "sete_estrelas",
                "Sete estrelas",
                "4d6 de dano e desvantagem aos ataques inimigos por 2 rodadas.",
                7,
                3,
                dano="4d6",
                esquiva=2,
            ),
        ],
    },
    "Patrulheiro": {
        "estilo": "Caçada: marcar a presa, controlar ameaças e acertar a distância.",
        "atributo": "destreza",
        "habilidades": [
            _h(
                "marca_cacador",
                "Marca do caçador",
                "1d6 de dano e marca a presa: ataques causam +3 dano por 3 rodadas.",
                1,
                1,
                dano="1d6",
                marcado=3,
            ),
            _h(
                "disparo_enredante",
                "Disparo enredante",
                "2d6 de dano e interrompe a próxima ação do alvo.",
                3,
                2,
                dano="2d6",
                atordoado=1,
            ),
            _h(
                "chuva_flechas",
                "Chuva de flechas",
                "3d6 em todos os inimigos; presas marcadas recebem +3 dano.",
                7,
                3,
                "todos",
                dano="3d6",
            ),
        ],
    },
    "Paladino": {
        "estilo": "Juramento: dano radiante, recuperação e proteção do grupo.",
        "atributo": "carisma",
        "habilidades": [
            _h(
                "golpe_divino",
                "Golpe divino",
                "1d10 radiante e recupera 3 PV do herói.",
                1,
                2,
                dano="1d10",
                cura_fixa=3,
            ),
            _h(
                "aura_guardia",
                "Aura guardiã",
                "Cura 2d6 PV do grupo e reduz 2 de cada golpe recebido por 2 rodadas.",
                3,
                2,
                "heroi",
                cura="2d6",
                grupo=True,
                protecao=2,
            ),
            _h(
                "julgamento",
                "Julgamento",
                "3d8 radiante; inimigos abaixo de metade da vida recebem +2d6.",
                7,
                3,
                dano="3d8",
                executar=True,
            ),
        ],
    },
    "Bardo": {
        "estilo": "Inspiração e deboche: enfraquecer inimigos e sustentar companheiros.",
        "atributo": "carisma",
        "habilidades": [
            _h(
                "palavra_cortante",
                "Palavra cortante",
                "1d6 psíquico e enfraquece o alvo por 2 rodadas (-3 dano).",
                1,
                1,
                dano="1d6",
                enfraquecido=2,
            ),
            _h(
                "cancao_coragem",
                "Canção de coragem",
                "Cura 2d6 PV de todo o grupo; vantagem no próximo ataque do herói.",
                3,
                2,
                "heroi",
                cura="2d6",
                grupo=True,
                precisao=2,
            ),
            _h(
                "acorde_dissonante",
                "Acorde dissonante",
                "2d6 psíquico em todos e enfraquece os sobreviventes por 2 rodadas.",
                7,
                3,
                "todos",
                dano="2d6",
                enfraquecido=2,
            ),
        ],
    },
    "Clérigo": {
        "estilo": "Fé e sustentação: dano sagrado, cura e proteção duradoura.",
        "atributo": "sabedoria",
        "habilidades": [
            _h(
                "chama_sagrada",
                "Chama sagrada",
                "1d8 radiante e recupera 2 PV do herói.",
                1,
                1,
                dano="1d8",
                cura_fixa=2,
            ),
            _h(
                "santuario",
                "Santuário",
                "Cura 2d8 PV de todo o grupo e +2 CA ao herói nesta rodada.",
                3,
                2,
                "heroi",
                cura="2d8",
                grupo=True,
                guarda=1,
            ),
            _h(
                "aurora",
                "Aurora restauradora",
                "2d8 radiante em todos os inimigos e cura 2d6 PV do grupo.",
                7,
                3,
                "todos",
                dano="2d8",
                cura="2d6",
                grupo=True,
            ),
        ],
    },
    "Druida": {
        "estilo": "Natureza adaptável: raízes, forma selvagem e tempestades.",
        "atributo": "sabedoria",
        "habilidades": [
            _h(
                "raizes_vivas",
                "Raízes vivas",
                "1d6 de dano e enfraquece o alvo por 2 rodadas (-3 dano).",
                1,
                1,
                dano="1d6",
                enfraquecido=2,
            ),
            _h(
                "forma_urso",
                "Forma de urso",
                "Recupera 2d6 PV; +2 dano e reduz 2 de cada golpe por 3 rodadas.",
                3,
                2,
                "heroi",
                cura="2d6",
                furia=3,
            ),
            _h(
                "tempestade_natural",
                "Tempestade natural",
                "2d8 em todos os inimigos e interrompe a próxima ação de cada um.",
                7,
                3,
                "todos",
                dano="2d8",
                atordoado=1,
            ),
        ],
    },
    "Feiticeiro": {
        "estilo": "Magia explosiva: queimar, expandir dano e apostar em grandes impactos.",
        "atributo": "carisma",
        "habilidades": [
            _h(
                "chama_caotica",
                "Chama caótica",
                "1d10 de fogo e queimadura: 2 dano por 2 rodadas.",
                1,
                2,
                dano="1d10",
                queimando=2,
            ),
            _h("arco_elemental", "Arco elemental", "2d6 de energia em todos os inimigos.", 3, 2, "todos", dano="2d6"),
            _h(
                "supernova",
                "Supernova",
                "3d8 de fogo em todos; sobreviventes queimam por 2 rodadas.",
                7,
                3,
                "todos",
                dano="3d8",
                queimando=2,
            ),
        ],
    },
    "Bruxo": {
        "estilo": "Pacto e desgaste: maldição, dreno de vida e horror.",
        "atributo": "carisma",
        "habilidades": [
            _h(
                "maldicao",
                "Maldição do pacto",
                "1d6 sombrio; marca o alvo para sofrer +3 dano por 3 rodadas.",
                1,
                1,
                dano="1d6",
                marcado=3,
            ),
            _h(
                "drenar_vida",
                "Drenar vida",
                "2d8 sombrio e recupera metade do dano causado.",
                3,
                2,
                dano="2d8",
                dreno=True,
            ),
            _h(
                "horror_abissal",
                "Horror abissal",
                "3d6 sombrio em todos; enfraquece os sobreviventes por 3 rodadas.",
                7,
                3,
                "todos",
                dano="3d6",
                enfraquecido=3,
            ),
        ],
    },
    "Mago": {
        "estilo": "Preparação e controle: projéteis infalíveis, gelo e área.",
        "atributo": "inteligencia",
        "habilidades": [
            _h(
                "misseis_arcanos",
                "Mísseis arcanos",
                "2d4 arcanos certeiros e +2 CA contra a reação inimiga.",
                1,
                1,
                dano="2d4",
                guarda=1,
            ),
            _h(
                "prisao_gelo",
                "Prisão de gelo",
                "1d8 de gelo e interrompe a próxima ação do alvo.",
                3,
                2,
                dano="1d8",
                atordoado=1,
            ),
            _h(
                "meteoros",
                "Chuva de meteoros",
                "3d8 de fogo em todos; rompe 2 de CA por 2 rodadas.",
                7,
                3,
                "todos",
                dano="3d8",
                vulneravel=2,
            ),
        ],
    },
}

CONJURADORES = {"Bardo", "Clérigo", "Druida", "Feiticeiro", "Bruxo", "Mago"}


def perfil_classe(classe: str) -> dict:
    return CLASSES.get(classe, CLASSES["Guerreiro"])


def limite_foco(nivel: int, classe: str | None = None) -> int:
    """Foco máximo. Conjurador vive de técnica: tem 2 a mais (ADR-0042)."""
    return 3 + (nivel >= 4) + (nivel >= 8) + (FOCO_EXTRA_CONJURADOR if classe in CONJURADORES else 0)


FOCO_EXTRA_CONJURADOR = 2


def defesa_de_classe(classe: str | None, nivel: int) -> int:
    """Proteção mágica de quem não veste armadura pesada: cresce com o nível,
    porque o bônus de ataque dos monstros também cresce."""
    base = BONUS_DEFESA.get(classe or "", 0)
    return base + nivel // 3 if base else 0


def dado_do_pulso(classe: str | None) -> str:
    """Ataque básico de conjurador sem arma na mão."""
    return DADO_PULSO.get(classe or "", "1d6")


# -- Combate v2 (ADR-0042): o que cada técnica gasta, de onde alcança e a que
# o alvo resiste. Fica à parte do catálogo acima para a identidade de cada
# classe caber numa tela: quem tem técnica de ação bônus faz duas coisas por
# turno; quem luta corpo a corpo precisa chegar perto; efeito de controle
# (atordoar, enfraquecer, queimar, abrir a guarda) só entra se o alvo falhar
# no teste de resistência.

# Técnicas que custam a ação BÔNUS (as outras custam a ação).
TECNICAS_BONUS = {
    "furia",            # Bárbaro: entra em fúria e ainda ataca
    "golpe_tatico",     # Guerreiro: o segundo golpe do turno
    "bomba_fumaca",     # Ladino: some e prepara o próximo ataque
    "rajada_punhos",    # Monge: rajada depois do golpe
    "marca_cacador",    # Patrulheiro: marca e ainda atira
    "aura_guardia",     # Paladino: protege e ainda golpeia
    "palavra_cortante", # Bardo: a palavra é rápida
    "santuario",        # Clérigo: cura e ainda age
    "forma_urso",       # Druida: muda de forma e ainda ataca
    "maldicao",         # Bruxo: amaldiçoa e ainda ataca
}
CORPO_A_CORPO = {"Bárbaro", "Guerreiro", "Ladino", "Monge", "Paladino"}
# A que o alvo resiste para escapar de cada efeito de controle.
RESISTENCIA_DO_EFEITO = {
    "atordoado": "vigor", "enfraquecido": "vontade", "vulneravel": "reflexo", "queimando": "reflexo",
}

# O traço que faz a classe jogar diferente, sempre ligado. Texto para a ficha;
# a regra está em services/tools.py e services/turnos.py.
PASSIVAS: dict[str, dict] = {
    "Bárbaro": {"nome": "Sangue quente", "descricao": "Ao ser ferido, recupera 1 de Foco (uma vez por rodada)."},
    "Guerreiro": {"nome": "Veterano", "descricao": "Golpe tático é ação bônus: dois golpes no mesmo turno."},
    "Ladino": {"nome": "Ataque furtivo", "descricao": "+1d6 de dano com vantagem ou contra alvo abalado; "
                                                    "recua sem levar golpe de oportunidade."},
    "Monge": {"nome": "Passo leve",
              "descricao": "Recua sem levar golpe de oportunidade; rajada de punhos é ação bônus."},
    "Patrulheiro": {"nome": "Caçador", "descricao": "Vantagem ao atirar de longe num alvo marcado."},
    "Paladino": {"nome": "Aura de fé", "descricao": "+2 em todos os testes de resistência."},
    "Bardo": {"nome": "Língua afiada", "descricao": "Palavra cortante é ação bônus."},
    "Clérigo": {"nome": "Mãos que curam", "descricao": "Santuário é ação bônus: cura e ainda age no turno."},
    "Druida": {"nome": "Forma selvagem", "descricao": "Forma de urso é ação bônus."},
    "Feiticeiro": {"nome": "Magia potencializada",
                   "descricao": "O dano das técnicas é rolado duas vezes e vale o maior; "
                                "recua sem levar golpe de oportunidade."},
    "Bruxo": {"nome": "Pacto", "descricao": "O descanso curto devolve todo o Foco."},
    "Mago": {"nome": "Armadura arcana",
             "descricao": "Defesa extra que cresce com o nível; CD +1 nas técnicas; "
                          "recua sem levar golpe de oportunidade."},
}
BONUS_DEFESA = {"Mago": 2, "Feiticeiro": 2, "Bruxo": 2, "Bardo": 1, "Druida": 1}
DADO_PULSO = {"Mago": "1d10", "Feiticeiro": "1d10", "Bruxo": "1d10", "Clérigo": "1d8", "Druida": "1d8", "Bardo": "1d8"}
BONUS_RESISTENCIA = {"Paladino": 2}
BONUS_CD = {"Mago": 1}
RECUA_SEM_OPORTUNIDADE = {"Ladino", "Monge", "Mago", "Feiticeiro"}



def _aplicar_mecanica() -> None:
    for classe, perfil in CLASSES.items():
        habilidades: list[dict] = perfil["habilidades"]  # type: ignore[assignment]
        for h in habilidades:
            h["acao"] = "bonus" if h["id"] in TECNICAS_BONUS else "acao"
            if h["alvo"] == "heroi":
                h["alcance"] = "pessoal"
            elif h["alvo"] == "todos":
                h["alcance"] = "area"
            else:
                h["alcance"] = "corpo" if classe in CORPO_A_CORPO else "distancia"
        perfil["passiva"] = PASSIVAS[classe]  # type: ignore[assignment]


_aplicar_mecanica()
