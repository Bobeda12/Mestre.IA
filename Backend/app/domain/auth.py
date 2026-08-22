from pydantic import BaseModel, Field, field_validator


def _valida_formato_email(valor: str) -> str:
    # Validação de formato só, não de existência. Evita puxar
    # `email-validator` como dependência para uma checagem deste tamanho.
    if "@" not in valor or "." not in valor.split("@")[-1] or valor.startswith("@"):
        raise ValueError("E-mail em formato inválido.")
    return valor.strip().lower()


class RegistrarRequest(BaseModel):
    email: str = Field(max_length=254)  # limite do próprio protocolo de e-mail (RFC 5321)
    # Sem limite de tamanho aqui (Etapa 9), uma senha de alguns MB chegava
    # inteira ao PBKDF2 (260 mil iterações sobre a string inteira) antes de
    # qualquer validação rejeitar — negação de serviço barata.
    senha: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def valida_email(cls, valor: str) -> str:
        return _valida_formato_email(valor)

    @field_validator("senha")
    @classmethod
    def valida_senha(cls, valor: str) -> str:
        if len(valor) < 8:
            raise ValueError("A senha precisa ter pelo menos 8 caracteres.")
        return valor


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def valida_email(cls, valor: str) -> str:
        return _valida_formato_email(valor)


class ReivindicarRequest(BaseModel):
    """Etapa 10 (A-1) — convidado vira conta com e-mail+senha, mesmo
    `usuario_id`. Mesma validação de `RegistrarRequest`, mas em outro
    endpoint porque o dono já está autenticado (não cria usuário novo)."""

    email: str = Field(max_length=254)
    senha: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def valida_email(cls, valor: str) -> str:
        return _valida_formato_email(valor)

    @field_validator("senha")
    @classmethod
    def valida_senha(cls, valor: str) -> str:
        if len(valor) < 8:
            raise ValueError("A senha precisa ter pelo menos 8 caracteres.")
        return valor
