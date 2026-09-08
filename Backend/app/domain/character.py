from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.adventure import INICIOS
from app.services.geracao_atributos import ler_token_atributos
from app.services.rules_engine import ATRIBUTOS_VALIDOS, MATRIZ_CLASSICA, validar_atributos_gerados


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
    # Remaster da criação (Fase 2, Oráculo) — frase-gancho curta; vazio
    # quando a origem foi escolhida manualmente (narrator.py cai para um
    # corte limpo de historia_texto nesse caso).
    resumo_historia: str = Field(default="", max_length=150)
    inicio_aventura: str = Field(default="surpresa", max_length=40)
    temperamento_mestre: Literal["Justo", "Épico", "Implacável"] = "Justo"
    dificuldade: Literal["História", "Normal", "Difícil"] = "Normal"
    # Etapa 11 (B-3) — URL da imagem já gerada pelo front (pollinations.ai);
    # o servidor só guarda, não valida conteúdo. Precisa ser http(s) porque
    # vira `<img src>` direto no HUD. 500 -> 900 no remaster da criação
    # (Fase 4): `pista_visual_en` do Oráculo alonga o prompt urlencoded o
    # bastante para estourar 500 (achado ao vivo, não teórico).
    imagem: str = Field(default="", max_length=900)
    # O cliente PROPÕE estes valores; o servidor sempre revalida (ver
    # routers/character.py). Ver ADR-0002 (Etapa 1).
    atributos: dict[str, int]
    atributos_livre: list[str] = []
    # Remaster da criação (Fase 3) — o point-buy matemático saiu. O cliente
    # escolhe a Matriz Clássica (fixa, sem round-trip) ou um conjunto rolado
    # no servidor (POST /gerar_atributos, ver services/geracao_atributos.py);
    # `token` só é exigido no segundo caso, e é o que prova que os valores
    # de fato vieram de uma rolagem do servidor, não do cliente.
    modo_atributos: Literal["classica", "dados"] = "classica"
    token_atributos: str | None = None

    @field_validator("inicio_aventura")
    @classmethod
    def valida_inicio_aventura(cls, valor: str) -> str:
        if valor != "surpresa" and valor not in INICIOS:
            raise ValueError("inicio_aventura precisa ser uma opção do catálogo de aventuras")
        return valor

    @field_validator("imagem")
    @classmethod
    def valida_imagem(cls, valor: str) -> str:
        if valor and not valor.startswith(("http://", "https://")):
            raise ValueError("imagem precisa ser uma URL http(s)")
        return valor

    @model_validator(mode="after")
    def valida_atributos(self) -> "CharacterCreationRequest":
        if self.modo_atributos == "classica":
            conjunto = MATRIZ_CLASSICA
        else:
            if not self.token_atributos:
                raise ValueError("modo_atributos='dados' precisa de um token_atributos (de POST /gerar_atributos)")
            conjunto = ler_token_atributos(self.token_atributos)
            if conjunto is None:
                raise ValueError("token_atributos inválido, expirado, ou adulterado — role de novo")
        validar_atributos_gerados(self.atributos, conjunto)
        return self

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
