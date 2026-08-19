from pydantic import BaseModel, field_validator

from app.services.rules_engine import ATRIBUTOS_VALIDOS, validar_point_buy


class CharacterCreationRequest(BaseModel):
    nome: str
    raca: str
    classe: str
    alinhamento: str
    background: str
    objetivo: str
    historia_texto: str = ""
    # O cliente PROPÕE estes valores; o servidor sempre revalida (ver
    # routers/character.py). Ver ADR-0002 (Etapa 1).
    atributos: dict[str, int]
    atributos_livre: list[str] = []

    @field_validator("atributos")
    @classmethod
    def valida_point_buy(cls, valores: dict[str, int]) -> dict[str, int]:
        validar_point_buy(valores)
        return valores

    @field_validator("atributos_livre")
    @classmethod
    def valida_atributos_livre(cls, valores: list[str]) -> list[str]:
        if len(valores) != len(set(valores)):
            raise ValueError("atributos_livre não pode repetir o mesmo atributo")
        for attr in valores:
            if attr not in ATRIBUTOS_VALIDOS:
                raise ValueError(f"'{attr}' não é um atributo válido")
        return valores


class UserAction(BaseModel):
    session_id: str
    action: str


class LoadRequest(BaseModel):
    session_id: str
