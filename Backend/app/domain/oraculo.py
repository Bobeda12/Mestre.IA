from pydantic import BaseModel, Field, field_validator


class OraculoOrigemRequest(BaseModel):
    # Mesmo espírito dos campos livres de domain/character.py — um conceito
    # de uma frase, não um roteiro.
    conceito: str = Field(min_length=1, max_length=300)


class OraculoOrigemResponse(BaseModel):
    raca: str
    classe: str
    perguntas: list[str]
    pista_visual_en: str


class OraculoHistoriaRequest(BaseModel):
    conceito: str = Field(min_length=1, max_length=300)
    raca: str = Field(max_length=60)
    classe: str = Field(max_length=60)
    perguntas: list[str] = Field(min_length=2, max_length=2)
    respostas: list[str] = Field(min_length=2, max_length=2)

    @field_validator("respostas")
    @classmethod
    def valida_respostas(cls, valores: list[str]) -> list[str]:
        for resposta in valores:
            if len(resposta) > 500:
                raise ValueError("cada resposta pode ter no máximo 500 caracteres")
        return valores


class OraculoHistoriaResponse(BaseModel):
    historia_texto: str
    background: str
    resumo_historia: str
    alinhamento: str
    objetivo: str
