"""Regras de item: ficha, efeito de consumível, preço (Fase 1, ADR-0033).

Tudo aqui é servidor: o narrador nunca escreve cura, CA ou preço. Quem chama
é `tools.ToolExecutor` (usar_item/equipar/comerciar) e `routers/game.py`
(`catalogo_itens` no frame de estado).
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any

from app.domain.eventos import EventoRolagem, EventoStatus
from app.domain.items import Equipamento, ItemCatalogo, ItemInventado
from app.infra.data_manager import regras
from app.services import rules_engine as motor

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor

DUAS_MAOS = "Duas Mãos"


def normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFD", nome)
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn").casefold().strip()


def resolver_nome(nome: str, inventario: list[str]) -> str | None:
    """Nome exato do inventário para um nome "quase" (acento/caixa)."""
    alvo = normalizar(nome)
    return next((i for i in inventario if normalizar(i) == alvo), None)


def ficha(nome: str, inventados: dict[str, ItemInventado] | None = None) -> dict[str, Any] | None:
    """Ficha pública de um item: catálogo, arma ou inventado. `None` = desconhecido."""
    item = regras.get_item(nome)
    if item is not None:
        return {"nome": nome, **item}
    arma = regras.get_weapon(nome)
    if arma is not None:
        return {
            "nome": nome, "tipo": "arma", "descricao": f"{arma['dano']} {arma['tipo'].lower()}",
            "tags": list(arma.get("propriedades", [])), "preco": arma.get("preco", 0), "dano": arma["dano"],
            "propriedades": arma.get("propriedades", []),
        }
    inv = (inventados or {}).get(nome)
    if inv is not None:
        return {"nome": nome, "tipo": "inventado", "descricao": inv.descricao, "tags": list(inv.tags), "preco": 1}
    return None


def slot_de(nome: str) -> str | None:
    f = ficha(nome)
    if not f:
        return None
    return {"arma": "arma", "armadura": "armadura", "escudo": "escudo"}.get(f["tipo"])


def tags_de(nome: str, inventados: dict[str, ItemInventado] | None = None) -> list[str]:
    f = ficha(nome, inventados)
    return list(f.get("tags", [])) if f else []


# ----------------------------------------------------------------- defesa
def calcular_defesa(atributos: dict, equipamento: Equipamento, bonus_extra: int = 0) -> int:
    armadura = regras.get_item(equipamento.armadura) if equipamento.armadura else None
    escudo = regras.get_item(equipamento.escudo) if equipamento.escudo else None
    return motor.calcular_defesa(atributos, armadura, escudo, bonus_extra)


def equipamento_de(heroi) -> Equipamento:
    return Equipamento.model_validate(heroi.equipamento or {})


def equipar(heroi, nome: str, bonus_defesa: int = 0) -> dict:
    """Decide o slot pela ficha, valida posse, força mínima e escudo × duas mãos, recalcula a defesa."""
    real = resolver_nome(nome, heroi.inventario or [])
    if real is None:
        return {"erro": f"'{nome}' não está no inventário"}
    slot = slot_de(real)
    if slot is None:
        return {"erro": f"'{real}' não é arma, armadura nem escudo"}
    eq = equipamento_de(heroi)
    f = ficha(real) or {}
    if slot == "armadura" and (heroi.atributos or {}).get("forca", 10) < f.get("forca_min", 0):
        return {"erro": f"{real} exige Força {f['forca_min']}"}
    if slot == "escudo" and eq.arma and DUAS_MAOS in (ficha(eq.arma) or {}).get("propriedades", []):
        return {"erro": f"não dá para usar escudo com {eq.arma} (duas mãos)"}
    if slot == "arma" and eq.escudo and DUAS_MAOS in f.get("propriedades", []):
        return {"erro": f"{real} exige as duas mãos: tire o escudo antes"}
    setattr(eq, slot, real)
    heroi.equipamento = eq.model_dump()
    heroi.defesa = calcular_defesa(heroi.atributos or {}, eq, bonus_defesa)
    return {"equipado": real, "slot": slot, "defesa": heroi.defesa, "equipamento": heroi.equipamento}


def desequipar(heroi, slot: str, bonus_defesa: int = 0) -> dict:
    eq = equipamento_de(heroi)
    if slot not in ("arma", "armadura", "escudo"):
        return {"erro": "slot inválido"}
    if getattr(eq, slot) is None:
        return {"erro": f"nada equipado em {slot}"}
    removido = getattr(eq, slot)
    setattr(eq, slot, None)
    heroi.equipamento = eq.model_dump()
    heroi.defesa = calcular_defesa(heroi.atributos or {}, eq, bonus_defesa)
    return {"desequipado": removido, "slot": slot, "defesa": heroi.defesa, "equipamento": heroi.equipamento}


def auto_equipar(heroi) -> bool:
    """Backfill (saves anteriores à Fase 1 e criação): primeira arma, armadura e escudo do inventário."""
    eq = equipamento_de(heroi)
    mudou = False
    for item in heroi.inventario or []:
        slot = slot_de(item)
        if slot and getattr(eq, slot) is None:
            f = ficha(item) or {}
            if slot == "armadura" and (heroi.atributos or {}).get("forca", 10) < f.get("forca_min", 0):
                continue
            if slot == "escudo" and eq.arma and DUAS_MAOS in (ficha(eq.arma) or {}).get("propriedades", []):
                continue
            if slot == "arma" and eq.escudo and DUAS_MAOS in f.get("propriedades", []):
                continue
            setattr(eq, slot, item)
            mudou = True
    heroi.equipamento = eq.model_dump()
    defesa = calcular_defesa(heroi.atributos or {}, eq)
    if defesa != heroi.defesa:
        heroi.defesa = defesa
        mudou = True
    return mudou


# ------------------------------------------------------------- consumíveis
def aplicar_efeito_consumivel(executor: ToolExecutor, nome: str, item: ItemCatalogo) -> dict:
    ef = item.efeito
    heroi, c_state = executor.heroi, executor.c_state
    resultado: dict[str, Any] = {"usado": nome}
    if ef is None:
        return {"usado": nome, "efeito": "sem efeito mecânico — narre livremente o uso"}
    if ef.cura:
        cura = motor.calcular_dano(ef.cura, rng=executor.rng)
        heroi.hp_atual = min(heroi.hp_max, heroi.hp_atual + cura)
        executor.eventos.append(
            EventoRolagem(
                f"🧪 {nome}: recupera {cura} PV. HP: {heroi.hp_atual}/{heroi.hp_max}.",
                EventoStatus(tipo="cura", quem="heroi", valor=cura),
            )
        )
        resultado.update(cura=cura, hp_atual=heroi.hp_atual)
    if ef.foco:
        antes = c_state.foco
        c_state.foco = min(c_state.foco_max, c_state.foco + ef.foco)
        executor.eventos.append(f"🔹 {nome}: recupera {c_state.foco - antes} Foco.")
        resultado["foco"] = c_state.foco
    if ef.remover_efeitos:
        removidos = [e for e in ef.remover_efeitos if c_state.efeitos_heroi.pop(e, None) is not None]
        executor.eventos.append(f"🧪 {nome}: {'limpa ' + ', '.join(removidos) if removidos else 'nada para curar'}.")
        resultado["removidos"] = removidos
    if ef.bonus_dano_temporario:
        # "lamina" é um efeito com duração como "furia": combat.turno_jogador
        # e tools.usar_habilidade somam +2 enquanto ele existir.
        c_state.efeitos_heroi["lamina"] = ef.rodadas or 1
        executor.eventos.append(f"🔥 {nome}: +2 de dano por {ef.rodadas or 1} rodadas.")
        resultado["bonus_dano"] = 2
    if ef.dano_area:
        if not c_state.ativo:
            executor.eventos.append(f"💥 {nome} arde no chão — não há inimigos por perto.")
        else:
            total = 0
            for inimigo in c_state.inimigos:
                if inimigo.hp <= 0 or inimigo.afastado:
                    continue
                dano = max(1, motor.calcular_dano(ef.dano_area, rng=executor.rng))
                inimigo.hp = max(0, inimigo.hp - dano)
                total += dano
                executor.eventos.append(
                    f"💥 {nome} atinge {inimigo.nome}: {dano} de dano ({inimigo.hp}/{inimigo.max_hp})."
                )
                if inimigo.hp == 0:
                    executor.eventos.append(
                        EventoRolagem(
                            f"💀 {inimigo.nome} cai morto.", EventoStatus(tipo="morte_inimigo", quem=inimigo.nome)
                        )
                    )
            resultado["dano_total"] = total
            resultado.update(executor._verificar_vitoria())
    if ef.esconder and c_state.ativo:
        c_state.heroi_escondido = True
        executor.eventos.append(f"🌫️ {nome}: os inimigos perdem você de vista nesta rodada.")
        resultado["escondido"] = True
    return resultado


# ------------------------------------------------------------------ preços
def preco_compra(preco_base: int, confianca: int, desconto_pct: int = 0) -> int:
    """Confiança 100 = 25% de desconto; -100 = 25% mais caro; `desconto_pct`
    vem de talento (Fase 3). Nunca abaixo de 1."""
    return max(1, round(preco_base * (1 - confianca / 400) * (1 - desconto_pct / 100)))


def preco_venda(preco_base: int) -> int:
    return max(1, preco_base // 2)
