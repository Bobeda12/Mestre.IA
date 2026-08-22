from pydantic import BaseModel, field_validator


def _valida_formato_email(valor: str) -> str:
    # Validação de formato só, não de existência. Evita puxar
    # `email-validator` como dependência para uma checagem deste tamanho.
    if "@" not in valor or "." not in valor.split("@")[-1] or valor.startswith("@"):
        raise ValueError("E-mail em formato inválido.")
    return valor.strip().lower()


class RegistrarRequest(BaseModel):
    email: str
    senha: str

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
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def valida_email(cls, valor: str) -> str:
        return _valida_formato_email(valor)
