from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Config tipada — substitui os.getenv() solto (api.py, versão anterior à Etapa 2).
    Lida de variáveis de ambiente e de Backend/.env (ver ADR-0003)."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    groq_api_key: str | None = None
    model_name: str = "openai/gpt-oss-120b"
    database_url: str = f"sqlite:///{(BASE_DIR / 'rpg_save.db').as_posix()}"
    cors_origins: list[str] = ["*"]
    data_dir: Path = BASE_DIR / "data"


settings = Settings()
