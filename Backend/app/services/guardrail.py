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

__all__ = [
    "corrigir_narrativa",
    "extrair_opcoes",
    "limpar_formatacao",
    "sem_negrito",
    "opcoes_padrao",
    "validar_narrativa",
]

# Etapa 10 (A-7) — o prompt pede prosa sem títulos/listas/código e permite
# **negrito** só em uma ou duas descobertas novas (destaque dourado no
# frontend, ver renderizarNarrativa em Frontend/src/lib/utils.tsx). Pedir ao
# modelo é a primeira linha, não a que vale: isto é a segunda,
# determinística, aplicada antes de PERSISTIR.
#
# Até 05/10/2026 o negrito também era apagado aqui, com o argumento de que
# markdown no histórico ensina o modelo a formatar mais. O efeito para o
# jogador era o destaque dourado aparecer enquanto o texto chegava e sumir
# quando o turno fechava (e nunca voltar ao recarregar). Agora o negrito é
# preservado e o excesso é que é cortado: no máximo `MAX_DESTAQUES` por
# narração, os demais viram texto comum.
MAX_DESTAQUES = 3
_PADRAO_NEGRITO = re.compile(r"\*\*([^*\n]+?)\*\*")
_PADRAO_NEGRITO_ITALICO_JUNTOS = re.compile(r"\*{3}([^*\n]+?)\*{3}")
_PADRAO_ITALICO = re.compile(r"(?<!\*)\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?!\*)")
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
    opcoes = [sem_negrito(o).strip(" .") for o in m.group(1).split("|") if o.strip()]
    return texto[: m.start()].rstrip(), opcoes[:3]


def opcoes_padrao(heroi: Personagem, c_state: CombatState) -> list[str]:
    """Rodada de conserto — a tag `[OPCOES]` é a última linha de um system
    prompt enorme (`narrator.montar_contexto`), e `corrigir_narrativa`
    reescreve a narrativa sem nunca pedir para preservá-la: botões que só
    aparecem quando o modelo lembra não são um recurso, são um sorteio.
    Chamada quando `extrair_opcoes` não encontrou nada — o servidor monta
    a partir do que ele mesmo já sabe (mesmo padrão "o modelo propõe, o
    servidor decide" do ADR-0002, aplicado à UI), então os botões existem
    sempre, sem depender de o modelo escrever a tag certa."""
    if heroi.hp_atual <= 0:
        # Teste de morte: sem ferramenta disponível, sem ação estruturada
        # que faça sentido oferecer — só a caixa de texto livre.
        return []
    if c_state.ativo:
        vivos = [i.nome for i in c_state.inimigos if i.hp > 0]
        opcoes = [f"Atacar {vivos[0]}"] if vivos else []
        opcoes += ["Esquivar", "Fugir"]
        return opcoes[:3]
    return ["Observar os arredores", "Seguir em frente", "Verificar o inventário"]


def sem_negrito(texto: str) -> str:
    """O texto sem os `**` de destaque — para tudo que não é a tela do
    jogador: checagem do guardrail, memória de longo prazo, botões de opção."""
    return _PADRAO_NEGRITO.sub(r"\1", texto)


def limpar_formatacao(texto: str) -> str:
    """Remove marcação markdown da narrativa, mantendo o texto. A única que
    sobrevive é `**negrito**`, que a tela desenha em dourado — e só os
    primeiros `MAX_DESTAQUES` de cada narração."""
    texto = _PADRAO_BLOCO_CODIGO.sub(lambda m: m.group(0).strip("`"), texto)
    texto = _PADRAO_CODIGO_INLINE.sub(r"\1", texto)
    texto = _PADRAO_NEGRITO_ITALICO_JUNTOS.sub(r"**\1**", texto)
    texto = _PADRAO_ITALICO.sub(r"\1", texto)
    texto = _PADRAO_TITULO.sub("", texto)
    texto = _PADRAO_LISTA.sub("", texto)
    vistos = 0

    def _limitar(m: re.Match) -> str:
        nonlocal vistos
        vistos += 1
        return m.group(0) if vistos <= MAX_DESTAQUES else m.group(1)

    return _PADRAO_NEGRITO.sub(_limitar, texto)


def validar_narrativa(texto: str, heroi: Personagem, c_state: CombatState, w_state: WorldState) -> list[str]:
    violacoes: list[str] = []
    # Sem os `**`: "**lobo** ataca" tem de casar com "lobo ataca".
    texto_lower = sem_negrito(texto).lower()

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
        "(não mude quem venceu, quanto de dano houve, etc.) — só a parte do texto que contradiz o estado. "
        "Se a narrativa original terminava com uma linha '[OPCOES]: ...', mantenha essa linha também, "
        "por último, sem mudar as opções."
    )
    msgs_correcao = [*msgs, {"role": "assistant", "content": texto}, {"role": "user", "content": pedido}]
    try:
        resp = chamar_com_fallback(msgs_correcao)
        return resp.choices[0].message.content or texto
    except ErroMestre:
        return texto
