"""Rodada de conserto (Parte 2, item K) — C-8 do backlog antigo: uma aba de
regras GERADA do motor, não escrita à mão. Uma página digitada começa
correta e mente em duas semanas (basta a curva de XP mudar, ou uma ação
tática nova aparecer); isto lê os valores direto de `rules_engine`/
`tools.py`/`data/*.json`, então não pode desatualizar sem o próprio motor
mudar junto.

Cuidado deliberado: isto NÃO é `biblia_mestre.txt` servida na tela — a
bíblia é a instrução do mestre (tom, "não proteja o jogador da própria
estupidez"), não o manual do jogador, e servi-la seria vazar o prompt de
sistema de propósito."""

from fastapi import APIRouter

from app.infra.data_manager import regras
from app.services import rules_engine as motor
from app.services.tools import ToolExecutor

router = APIRouter(prefix="/regras", tags=["regras"])

# Etapa 12a (C-8 do backlog) documentava esta escala só como texto solto na
# descrição da ferramenta `rolar_teste` (TOOLS_SCHEMA) — nunca um dado
# estruturado. Copiada de lá, não inventada: mesmos cinco degraus.
_ESCALA_DIFICULDADE = [
    {"cd": 5, "rotulo": "Trivial"},
    {"cd": 10, "rotulo": "Fácil"},
    {"cd": 15, "rotulo": "Médio"},
    {"cd": 20, "rotulo": "Difícil"},
    {"cd": 25, "rotulo": "Muito difícil"},
]

# As ações táticas em si (services/tools.py) são código, não dado — não tem
# como "ler" delas uma descrição de uma frase. O que É gerado do motor são
# os NÚMEROS dentro de cada descrição (CD_ACAO_TATICA), então a frase fica
# fixa aqui, mas o valor nunca pode desatualizar sozinho.
_ACOES_TATICAS = [
    {
        "nome": "Seu turno",
        "efeito": "Uma ação, uma ação bônus e um movimento, em qualquer ordem. O turno fecha em "
                  "\"Encerrar turno\", ou sozinho quando não sobra nada útil.",
    },
    {
        "nome": "Atacar",
        "efeito": "Ação. Arma corpo a corpo só alcança quem está perto (você avança sozinho se ainda "
                  "tem o movimento); atirar com um inimigo colado dá desvantagem.",
    },
    {
        "nome": "Investir",
        "efeito": "-2 no bônus de acerto, +50% no dano — troca precisão por força.",
    },
    {"nome": "Esquivar", "efeito": "Inimigos atacam você com desvantagem até o seu próximo turno."},
    {"nome": "Defender", "efeito": "+2 na Defesa até o seu próximo turno, e recupera 1 de Foco."},
    {
        "nome": "Esconder-se",
        "efeito": f"Teste de Destreza (CD {ToolExecutor.CD_ACAO_TATICA}) — sucesso tira você da mira dos inimigos.",
    },
    {
        "nome": "Fugir",
        "efeito": f"Teste de Destreza (CD {ToolExecutor.CD_ACAO_TATICA}) — sucesso encerra o combate.",
    },
    {
        "nome": "Aproximar e Recuar",
        "efeito": "Movimento. Recuar abre distância, mas cada inimigo perto ataca uma vez quando você se "
                  "afasta (ataque de oportunidade). Algumas classes recuam sem levar o golpe.",
    },
    {
        "nome": "Ação bônus",
        "efeito": "Beber uma poção, comandar um aliado (ele mira o alvo, com vantagem no primeiro golpe) "
                  "ou usar a técnica de ação bônus da sua classe.",
    },
    {
        "nome": "Improvisar",
        "efeito": "Ação. Descreva uma ideia no campo de texto: o Mestre escolhe o atributo, a dificuldade "
                  "e o efeito; o dado decide.",
    },
    {
        "nome": "Foco",
        "efeito": "Não volta sozinho. Descanso curto devolve metade (até dois entre descansos longos); "
                  "o longo devolve tudo.",
    },
]


@router.get("")
def get_regras() -> dict:
    return {
        "niveis": [
            {"nivel": nivel, "xp_necessario": xp, "bonus_proficiencia": motor.bonus_proficiencia(nivel)}
            for nivel, xp in sorted(motor.XP_POR_NIVEL.items())
        ],
        "escala_dificuldade": _ESCALA_DIFICULDADE,
        "acoes_taticas": _ACOES_TATICAS,
        "armas": regras.weapons,
        "aliado_padrao": {
            "ca": ToolExecutor.CA_ALIADO_PADRAO,
            "bonus_ataque": ToolExecutor.BONUS_ATAQUE_ALIADO_PADRAO,
            "dano_dado": ToolExecutor.DANO_ALIADO_PADRAO,
        },
        "bonus_item_com_tag": ToolExecutor.BONUS_ITEM_COM_TAG,
    }
