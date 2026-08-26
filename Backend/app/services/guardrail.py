"""Guardrail de estado (Etapa 4, PLANO_MESTRE.md): confere heuristicamente se
a narrativa final contradiz o que o servidor sabe ser verdade — item fora do
inventário, inimigo morto tratado como vivo, local errado. Não é um
LLM-as-judge (isso é a Etapa 6): é checagem textual simples, documentada como
tal — falso negativo (uma contradição sutil que passa) é esperado; o que
importa é pegar o caso óbvio sem gastar uma chamada de LLM extra por turno."""

import re

from app.domain.state import CombatState, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.infra.llm_client import ErroMestre, chamar_com_fallback

# Etapa 10 (A-7) — o prompt já pede "sem markdown" (narrator.montar_contexto
# e a bíblia), mas pedir ao modelo é a primeira linha, não a que vale: isto
# é a segunda, determinística, aplicada antes de persistir. Importa
# persistir limpo porque o histórico vira contexto do próximo turno —
# markdown sujo no histórico ensina o modelo a formatar mais, não menos.
_PADRAO_NEGRITO_ITALICO = re.compile(r"\*{1,3}([^*\n]+?)\*{1,3}")
_PADRAO_TITULO = re.compile(r"^#{1,6}\s*", flags=re.MULTILINE)
_PADRAO_LISTA = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", flags=re.MULTILINE)
_PADRAO_BLOCO_CODIGO = re.compile(r"```.*?```", flags=re.DOTALL)
_PADRAO_CODIGO_INLINE = re.compile(r"`([^`\n]+?)`")

# Fase 1 da revisão de gameplay (Etapa 12/13) — `narrator.montar_contexto`
# instrui o modelo a escrever exatamente "[OPCOES]" (sem acento), mas ao
# vivo o modelo "corrige" pra grafia correta em português — "[OPÇÕES]" —
# quebrando um regex exato (achado testando contra a Groq de verdade, não
# em teste com RNG fixo). `OP.{0,2}ES` casa "OPCOES", "OPÇÕES", "OPÇOES" e
# "OPCÕES" sem enumerar cada combinação de acento. DOTALL porque o resto do
# texto até o fim da string são as opções — a tag é sempre a última coisa
# que o modelo escreve, por instrução do prompt.
_PADRAO_OPCOES = re.compile(r"\[OP.{0,2}ES\]:?\s*(.+)", re.IGNORECASE | re.DOTALL)


def extrair_opcoes(texto: str) -> tuple[str, list[str]]:
    """Separa a tag `[OPCOES]: opt1|opt2|opt3` do texto exibido/persistido.
    Sem a tag (ex: o prompt de morte, que não a pede), devolve o texto
    intacto e lista vazia — o frontend simplesmente não mostra botões."""
    m = _PADRAO_OPCOES.search(texto)
    if not m:
        return texto, []
    opcoes = [o.strip(" .") for o in m.group(1).split("|") if o.strip()]
    return texto[: m.start()].rstrip(), opcoes[:3]


def limpar_formatacao(texto: str) -> str:
    """Remove marcação markdown da narrativa, mantendo o texto — o jogador
    nunca deveria ver um `**`/`#`/`-` cru numa tela de chat que não
    interpreta markdown nenhum (`GameChat.tsx` renderiza texto puro)."""
    texto = _PADRAO_BLOCO_CODIGO.sub(lambda m: m.group(0).strip("`"), texto)
    texto = _PADRAO_CODIGO_INLINE.sub(r"\1", texto)
    texto = _PADRAO_NEGRITO_ITALICO.sub(r"\1", texto)
    texto = _PADRAO_TITULO.sub("", texto)
    texto = _PADRAO_LISTA.sub("", texto)
    return texto


def validar_narrativa(texto: str, heroi: Personagem, c_state: CombatState, w_state: WorldState) -> list[str]:
    violacoes: list[str] = []
    texto_lower = texto.lower()

    # Itens de outros personagens (bestiário/armas conhecidas) citados como
    # "seu/sua X" sem estarem no inventário do herói.
    for grupo in regras.weapons.values():
        for nome_arma in grupo:
            if nome_arma.lower() in texto_lower and nome_arma not in heroi.inventario:
                if f"sua {nome_arma.lower()}" in texto_lower or f"seu {nome_arma.lower()}" in texto_lower:
                    violacoes.append(f"menciona '{nome_arma}' como posse do herói, mas não está no inventário")

    # Inimigo já morto neste combate, tratado como ainda ativo/atacando.
    for inimigo in c_state.inimigos:
        if inimigo.hp <= 0 and inimigo.nome.lower() in texto_lower:
            for verbo in ("ataca", "avança", "ruge", "acerta", "investe"):
                if f"{inimigo.nome.lower()} {verbo}" in texto_lower:
                    violacoes.append(f"trata '{inimigo.nome}' (já morto) como se ainda estivesse agindo")
                    break

    # Local que existe no bestiário de locais mas não é o local atual, citado
    # como se o herói estivesse lá, sem ter havido `mover` para chegar.
    for nome_local in regras.get_locations_list():
        if nome_local != w_state.local and nome_local.lower() in texto_lower:
            if f"em {nome_local.lower()}" in texto_lower or f"chega a {nome_local.lower()}" in texto_lower:
                violacoes.append(f"narrativa se passa em '{nome_local}', mas o local atual é '{w_state.local}'")

    return violacoes


def corrigir_narrativa(texto: str, violacoes: list[str], msgs: list[dict]) -> str:
    """Uma única tentativa de correção — não é um segundo loop de agente,
    só um reprompt de texto puro (sem `tools=`, nada de mecânica de novo,
    só a prosa). Se falhar (erro de API, ou a correção continuar violando),
    fica a narrativa original: o guardrail é uma rede de segurança
    heurística, não uma garantia — documentado no diário da Etapa 4."""
    pedido = (
        "Sua narrativa anterior tem um problema: " + "; ".join(violacoes) + ". "
        "Reescreva a narrativa corrigindo isso, mantendo o mesmo resultado mecânico "
        "(não mude quem venceu, quanto de dano houve, etc.) — só a parte do texto que contradiz o estado."
    )
    msgs_correcao = [*msgs, {"role": "assistant", "content": texto}, {"role": "user", "content": pedido}]
    try:
        resp = chamar_com_fallback(msgs_correcao)
        return resp.choices[0].message.content or texto
    except ErroMestre:
        return texto
