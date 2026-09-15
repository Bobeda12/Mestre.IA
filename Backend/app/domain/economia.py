"""Mercadorias em trânsito; quantidades e prazos pertencem ao motor."""

from typing import Literal

from pydantic import Field

from app.domain.emergencia import Registro


class Remessa(Registro):
    remetente: str
    destinatario: str
    origem: str
    destino: str
    passagem: str
    item: str
    quantidade: int = Field(ge=1, le=3)
    acontecimento: str
    chegada_em: int
    estado: Literal["em_transito", "retida", "entregue"] = "em_transito"
