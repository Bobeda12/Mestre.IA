from pydantic import BaseModel, Field, field_validator

from app.services.rules_engine import ATRIBUTOS_VALIDOS, validar_point_buy


class CharacterCreationRequest(BaseModel):
    # Limites de tamanho (Etapa 9) — estes campos vão direto pro prompt do
    # narrador (services/narrator.py); sem limite, um texto gigante inflava
    # o custo/contexto de cada chamada à Groq sem passar por nenhuma
    # validação antes.
    nome: str = Field(max_length=60)
    raca: str = Field(max_length=60)  # validado contra o catálogo em routers/character.py
    classe: str = Field(max_length=60)  # idem
    alinhamento: str = Field(max_length=60)
    background: str = Field(max_length=500)
    objetivo: str = Field(max_length=500)
    historia_texto: str = Field(default="", max_length=4000)
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
    # 2000 caracteres é generoso para uma ação de turno — sem limite, uma
    # mensagem gigante entrava direto no prompt do narrador (Etapa 9).
    action: str = Field(max_length=2000)


class LoadRequest(BaseModel):
    session_id: str
