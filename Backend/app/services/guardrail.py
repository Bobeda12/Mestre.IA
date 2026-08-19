"""Guardrail de estado (Etapa 4, PLANO_MESTRE.md): confere heuristicamente se
a narrativa final contradiz o que o servidor sabe ser verdade — item fora do
inventário, inimigo morto tratado como vivo, local errado. Não é um
LLM-as-judge (isso é a Etapa 6): é checagem textual simples, documentada como
tal — falso negativo (uma contradição sutil que passa) é esperado; o que
importa é pegar o caso óbvio sem gastar uma chamada de LLM extra por turno."""

from app.domain.state import CombatState, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.infra.llm_client import ErroMestre, chamar_com_fallback


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
