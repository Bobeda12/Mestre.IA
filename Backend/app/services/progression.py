"""Progressão curta, migração de campanhas e contrato público da ficha."""

from app.services.class_abilities import limite_foco, perfil_classe
from app.services.rules_engine import NIVEL_MAXIMO, XP_POR_NIVEL

XP_LEGADO = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500}


def migrar_progressao(heroi, w_state) -> None:
    """Preserva nível e fração até o próximo nível, sem promover saves antigos ao teto."""
    if w_state.versao_progressao >= 1:
        return
    nivel = max(1, min(heroi.nivel or 1, NIVEL_MAXIMO))
    xp = max(0, heroi.xp or 0)
    if nivel in XP_LEGADO:
        inicio = XP_LEGADO[nivel]
        fim = XP_LEGADO.get(nivel + 1, inicio + 3800)
        fracao = min(0.99, max(0, xp - inicio) / (fim - inicio))
        proximo = XP_POR_NIVEL.get(nivel + 1, XP_POR_NIVEL[nivel])
        heroi.xp = XP_POR_NIVEL[nivel] + int(fracao * (proximo - XP_POR_NIVEL[nivel]))
    heroi.nivel = nivel
    w_state.versao_progressao = 1


def migrar_equipamento(heroi) -> bool:
    """Fase 1 (ADR-0033) — save anterior aos slots: equipa a primeira arma,
    armadura e escudo do inventário e recalcula a defesa. Idempotente."""
    from app.services.items import auto_equipar

    if heroi.equipamento:
        return False
    return auto_equipar(heroi)


def painel_progressao(heroi, c_state) -> dict:
    nivel = heroi.nivel or 1
    perfil = perfil_classe(heroi.classe)
    habilidades = []
    for habilidade in perfil["habilidades"]:
        publica = {k: habilidade[k] for k in ("id", "nome", "descricao", "nivel", "custo", "alvo")}
        publica["disponivel"] = bool(
            c_state.ativo and heroi.hp_atual > 0 and nivel >= habilidade["nivel"]
            and c_state.foco >= habilidade["custo"]
        )
        habilidades.append(publica)
    marcos = {
        1: "Sua primeira técnica. Ataque básico recupera 1 Foco; defender recupera 2.",
        2: "Maestria I: +1 dano em ataques e técnicas.",
        3: f"Nova técnica: {perfil['habilidades'][1]['nome']}.",
        4: "4 Foco máximo e maestria II (+2 dano).",
        5: "Ataques básicos recebem +1d6 e proficiência sobe para +3.",
        6: "Maestria III: +3 dano em ataques e técnicas.",
        7: f"Técnica suprema: {perfil['habilidades'][2]['nome']}.",
        8: "5 Foco máximo e maestria IV (+4 dano).",
        9: "Proficiência sobe para +4: mais precisão em ataques.",
        10: "Lenda: ataques básicos recebem +2d6 e maestria V (+5 dano).",
    }
    return {
        "nivel_maximo": NIVEL_MAXIMO, "estilo": perfil["estilo"],
        "recurso": {"nome": "Foco", "atual": c_state.foco, "maximo": limite_foco(nivel)},
        "habilidades": habilidades,
        "niveis": [{"nivel": n, "xp": xp, "descricao": marcos[n]} for n, xp in XP_POR_NIVEL.items()],
    }
