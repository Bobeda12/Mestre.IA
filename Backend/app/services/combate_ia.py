"""As duas chamadas de IA do combate v2, ambas pequenas e sem ferramentas.

- `narrar_rodada`: prosa curta sobre o que o juiz JÁ resolveu. A IA não
  decide nada; se falhar, o texto do servidor continua valendo.
- `julgar_improviso`: o jogador descreve uma ação criativa; a IA só escolhe
  atributo, dificuldade e um efeito de uma lista fechada. Quem rola e aplica
  é o servidor (`ToolExecutor.improvisar`).

Nenhuma das duas trava a luta: sem provedor, sem cota ou com resposta ruim,
há sempre um caminho determinístico (ADR-0006, ADR-0041)."""

import functools
import logging
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.domain.eventos import DadosRolagem, EventoRolagem, EventoStatus
from app.domain.state import CombatState, Inimigo
from app.infra import llm_client
from app.services.turnos import NOME_CONDICAO, vivos

logger = logging.getLogger(__name__)

PRAZO_IA = 8.0
MAX_FATOS = 14
PROSA_MAX = 600
TEXTO_IMPROVISO_MAX = 200

# id → o que o efeito faz, na frase que a IA lê. Os números são do servidor.
EFEITOS: dict[str, str] = {
    "dano_leve": "fere um inimigo de leve",
    "dano_area_leve": "fere de leve todos os inimigos (algo que desaba, explode ou se espalha)",
    "derrubar": "derruba ou atordoa um inimigo, que perde a próxima vez",
    "desequilibrar": "abre a guarda de um inimigo, que fica mais fácil de acertar",
    "distrair": "atrapalha a mira dos inimigos até o próximo turno do herói",
    "empurrar": "afasta um inimigo que está perto, sem levar golpe ao se soltar",
    "cobertura": "protege o herói atrás de algo até o próximo turno dele",
    "vantagem": "prepara o próximo ataque do herói, que sai com vantagem",
    "intimidar": "abala um inimigo, que passa a bater mais fraco",
    "nada": "é só encenação, sem efeito mecânico",
}
CD_POR_DIFICULDADE = {"facil": 10, "media": 13, "dificil": 16}
Atributo = Literal["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"]


class JulgamentoImproviso(BaseModel):
    atributo: Atributo
    dificuldade: Literal["facil", "media", "dificil"]
    efeito: Literal[
        "dano_leve", "dano_area_leve", "derrubar", "desequilibrar", "distrair", "empurrar", "cobertura",
        "vantagem", "intimidar", "nada",
    ]
    alvo: str = ""


# -- fatos: o que o juiz resolveu, sem número ---------------------------------

_SIMBOLOS = re.compile(r"^[^\wÀ-ÿ\"'(]+")


def _quem(nome: str | None) -> str:
    return "Você" if nome in (None, "heroi") else str(nome)


def _fato(evento: object) -> str | None:
    dados = evento.dados if isinstance(evento, EventoRolagem) else None
    if isinstance(dados, EventoStatus):
        if dados.tipo == "cura":
            return f"{_quem(dados.quem)} recupera o fôlego."
        if dados.tipo == "condicao":
            return f"Você fica {NOME_CONDICAO.get(dados.detalhe or '', dados.detalhe or 'abalado')}."
        return f"{dados.quem} cai."
    if isinstance(dados, DadosRolagem):
        if dados.tipo == "ataque":
            desfecho = "acerta em cheio" if dados.critico else "acerta" if dados.sucesso else "erra"
            alvo = "você" if dados.alvo == "heroi" else dados.alvo
            arma = f" com {dados.arma}" if dados.arma and dados.quem == "heroi" else ""
            return f"{_quem(dados.quem)} ataca {alvo}{arma} e {desfecho}."
        if dados.tipo == "resistencia":
            return f"Você {'resiste a' if dados.sucesso else 'não resiste a'} {dados.motivo or 'um efeito'}."
        if dados.tipo == "teste":
            return f"Você tenta {dados.motivo or 'algo arriscado'} e {'consegue' if dados.sucesso else 'falha'}."
        if dados.tipo == "dano":
            if dados.quem == "condicao":
                return "O mal que aflige você cobra o seu preço."
            return f"{'Você' if dados.alvo == 'heroi' else dados.alvo} é ferido."
        if dados.tipo == "morte":
            return "Você, caído, luta para não morrer."
        return None
    texto = _SIMBOLOS.sub("", str(evento)).strip()
    # Linhas com número são contabilidade (XP, ouro, PV): não viram prosa.
    return texto if texto and not any(ch.isdigit() for ch in texto) else None


def fatos_da_jogada(rotulo: str, eventos: list) -> list[str]:
    """O que entra no pedido de narração: a intenção do jogador e os fatos
    do juiz, em ordem, sem dado, sem PV e sem CA."""
    fatos = [f"O jogador escolheu: {rotulo}."] if rotulo else []
    fatos += [f for f in (_fato(e) for e in eventos) if f]
    return fatos[:MAX_FATOS]


# -- narração -----------------------------------------------------------------

def _estado(inimigo: Inimigo) -> str:
    if inimigo.afastado:
        return "fugiu"
    if inimigo.hp <= 0:
        return "caído"
    fracao = inimigo.hp / inimigo.max_hp if inimigo.max_hp else 1
    saude = "ileso" if fracao >= 1 else "ferido" if fracao >= 0.5 else "muito ferido"
    return f"{saude}, {inimigo.distancia}"


def prompt_narracao(heroi, c_state: CombatState, local: str, fatos: list[str]) -> str:
    inimigos = "; ".join(f"{i.nome} ({_estado(i)})" for i in c_state.inimigos[:6]) or "nenhum de pé"
    vida = "por um fio" if heroi.hp_max and heroi.hp_atual / heroi.hp_max < 0.25 else "de pé"
    if heroi.hp_atual <= 0:
        vida = "caído, inconsciente"
    lista = "\n".join(f"- {f[:160]}" for f in fatos[:MAX_FATOS])
    return (
        "Você é o narrador de um RPG de fantasia. Narre UMA rodada de combate que já foi resolvida.\n"
        f"Herói: {heroi.nome}, {heroi.raca} {heroi.classe} ({vida}). Local: {local[:80] or 'campo aberto'}.\n"
        f"Inimigos: {inimigos}.\n"
        f"O que aconteceu, na ordem (fatos já decididos; não mude nem acrescente nenhum):\n{lista}\n\n"
        "Escreva 2 ou 3 frases em português do Brasil, no presente, tratando o herói por \"você\" (nunca "
        "\"tu\") e sem adjetivo que lhe dê gênero. Mostre o movimento e o impacto. Sem números, sem termos de "
        "regra (dado, CA, PV, teste, turno, dano), sem golpes, mortes, falas, equipamentos ou efeitos que não "
        "estejam na lista, e sem dizer o que o herói fará em seguida. Responda só com a narração."
    )


def validar_prosa(texto: object) -> str | None:
    """Determinístico: a prosa não pode trazer número (o juiz é a única
    fonte de números) nem passar do tamanho. Não há chamada de correção."""
    if not isinstance(texto, str):
        return None
    limpo = " ".join(texto.replace("*", "").split())
    if not 20 <= len(limpo) <= PROSA_MAX or any(ch.isdigit() for ch in limpo):
        return None
    return limpo


def narrar_rodada(heroi, c_state: CombatState, local: str, fatos: list[str],
                  chamar_fn: Callable[..., Any] | None = None) -> str | None:
    if not fatos or (chamar_fn is None and not llm_client.clients):
        return None
    chamar = chamar_fn or functools.partial(llm_client.chamar_com_fallback, papel="volume", prazo=PRAZO_IA)
    try:
        resp = chamar([{"role": "user", "content": prompt_narracao(heroi, c_state, local, fatos)}])
        return validar_prosa(resp.choices[0].message.content)
    except Exception as erro:  # a luta nunca espera pela voz do narrador
        logger.warning("narrar_rodada: IA indisponível (%s)", type(erro).__name__)
        return None


# -- improviso ----------------------------------------------------------------

_PALAVRAS_ATRIBUTO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("carisma", ("grit", "provoc", "intimid", "engan", "blef", "distra", "ameac", "convenc")),
    ("destreza", ("salt", "pul", "rol", "desliz", "escorreg", "arremess", "atir", "jog", "corr", "equilibr")),
    ("inteligencia", ("analis", "armadilh", "mecan", "calcul", "improvis", "engenh")),
    ("sabedoria", ("perceb", "observ", "escut", "pressent", "acalm")),
    ("forca", ("empurr", "derrub", "quebr", "levant", "arrast", "chut", "arromb", "puxa")),
)


def julgamento_padrao(texto: str, alvo: str) -> JulgamentoImproviso:
    """Sem IA: o atributo sai de palavras do texto, o efeito é o mais neutro
    que ainda recompensa a ideia, e a dificuldade é a média."""
    baixo = texto.casefold()
    atributo = next((a for a, raizes in _PALAVRAS_ATRIBUTO if any(r in baixo for r in raizes)), "forca")
    return JulgamentoImproviso(atributo=atributo, dificuldade="media", efeito="desequilibrar", alvo=alvo)  # type: ignore[arg-type]


def prompt_improviso(texto: str, heroi, c_state: CombatState, cenario: str) -> str:
    atributos = ", ".join(f"{a} {v}" for a, v in (heroi.atributos or {}).items())
    inimigos = "; ".join(f"{i.id} = {i.nome} ({i.distancia})" for i in vivos(c_state)[:6])
    itens = ", ".join((heroi.inventario or [])[:10]) or "nada"
    efeitos = "\n".join(f"- {nome}: {descricao}" for nome, descricao in EFEITOS.items())
    return (
        "Você é o juiz de um RPG. Em combate, o jogador improvisou esta ação:\n"
        f'"{texto[:TEXTO_IMPROVISO_MAX]}"\n\n'
        f"Herói: {heroi.classe}. Atributos: {atributos}. Itens: {itens}.\n"
        f"Inimigos de pé: {inimigos}.\nCenário: {cenario[:200] or 'sem detalhe'}.\n\n"
        "Decida três coisas, sem inventar nada fora das listas:\n"
        "1. atributo que a ação exige: forca, destreza, constituicao, inteligencia, sabedoria ou carisma.\n"
        "2. dificuldade: facil (qualquer um faz), media, ou dificil (ousado, ou depende de algo que talvez "
        "nem exista na cena).\n"
        f"3. efeito, se der certo (escolha o mais modesto que combina com a ação):\n{efeitos}\n"
        'Em "alvo", o id do inimigo visado (ex.: i1), ou "" se a ação não mira ninguém.\n'
        'Responda APENAS JSON: {"atributo": "...", "dificuldade": "...", "efeito": "...", "alvo": "..."}'
    )


def julgar_improviso(texto: str, heroi, c_state: CombatState, cenario: str = "", alvo: str = "",
                     chamar_fn: Callable[..., Any] | None = None) -> tuple[JulgamentoImproviso, bool]:
    """Devolve (julgamento, veio_da_ia). Alvo inválido vira o alvo pedido
    pelo jogador ou nenhum: quem valida de novo é o servidor, ao aplicar."""
    padrao = julgamento_padrao(texto, alvo)
    if chamar_fn is None and not llm_client.clients:
        return padrao, False
    from app.services.narrator import _ler_json

    chamar = chamar_fn or functools.partial(llm_client.chamar_com_fallback, papel="volume", prazo=PRAZO_IA)
    try:
        dados = _ler_json(chamar(
            [{"role": "user", "content": prompt_improviso(texto, heroi, c_state, cenario)}],
            response_format={"type": "json_object"},
        ))
        julgamento = JulgamentoImproviso.model_validate(dados)
    except ValidationError:
        return padrao, False
    except Exception as erro:
        logger.warning("julgar_improviso: IA indisponível (%s)", type(erro).__name__)
        return padrao, False
    ids = {i.id for i in vivos(c_state)}
    if julgamento.alvo not in ids:
        julgamento.alvo = alvo if alvo in ids else ""
    return julgamento, True
