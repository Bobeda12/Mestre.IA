"""Itens com ficha (Fase 1 do plano "jogo completo", 08/09/2026 — ADR-0033).

Dois mundos, uma fronteira: o CATÁLOGO (`data/items.json` + `data/weapons.json`)
tem números — cura, CA, preço — e é validado no boot; um item INVENTADO pelo
narrador só pode carregar tags de um vocabulário fechado e nunca move número
nenhum além do bônus de tag em `rolar_teste`. Mesmo padrão "pele × ficha" dos
monstros (ADR-0029): o modelo nomeia, o servidor decide o que aquilo faz.
"""

from typing import Literal

from pydantic import BaseModel, Field

Tag = Literal[
    "Fogo", "Luz", "Sagrado", "Utilidade", "Cura", "Foco", "Veneno", "Gelo", "Leve", "Pesada", "Afiado", "Arcano"
]
TAGS_VALIDAS: tuple[str, ...] = (
    "Fogo", "Luz", "Sagrado", "Utilidade", "Cura", "Foco", "Veneno", "Gelo", "Leve", "Pesada", "Afiado", "Arcano"
)
TipoItem = Literal["consumivel", "ferramenta", "armadura", "escudo"]
Slot = Literal["arma", "armadura", "escudo"]


class EfeitoConsumivel(BaseModel):
    cura: str | None = None  # notação de dado, ex. "2d4+2"
    foco: int = 0
    remover_efeitos: list[str] = Field(default_factory=list)
    dano_area: str | None = None  # dado aplicado a TODOS os inimigos vivos
    bonus_dano_temporario: int = 0
    rodadas: int = 0
    esconder: bool = False


class ItemCatalogo(BaseModel):
    tipo: TipoItem
    descricao: str = ""
    tags: list[Tag] = Field(default_factory=list)
    efeito: EfeitoConsumivel | None = None
    preco: int = Field(default=0, ge=0)
    # armadura
    categoria: Literal["leve", "media", "pesada"] | None = None
    ca_base: int | None = None
    forca_min: int = 0
    # escudo
    ca_bonus: int = 0


class ItemInventado(BaseModel):
    """O que o narrador pode criar por `dar_item` fora do catálogo."""

    nome: str = Field(min_length=1, max_length=60)
    descricao: str = Field(min_length=1, max_length=200)
    tags: list[Tag] = Field(default_factory=list, max_length=3)


class Equipamento(BaseModel):
    arma: str | None = None
    armadura: str | None = None
    escudo: str | None = None
