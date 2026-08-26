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
    {"nome": "Atacar", "efeito": "Ataque normal contra um inimigo."},
    {
        "nome": "Investir",
        "efeito": "-2 no bônus de acerto, +50% no dano — troca precisão por força.",
    },
    {"nome": "Esquivar", "efeito": "Remove a vantagem que um inimigo tinha em te acertar."},
    {"nome": "Defender", "efeito": "+2 na Defesa até o seu próximo turno."},
    {
        "nome": "Esconder-se",
        "efeito": f"Teste de Destreza (CD {ToolExecutor.CD_ACAO_TATICA}) — sucesso tira você da mira dos inimigos.",
    },
    {
        "nome": "Fugir",
        "efeito": f"Teste de Destreza (CD {ToolExecutor.CD_ACAO_TATICA}) — sucesso encerra o combate.",
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
