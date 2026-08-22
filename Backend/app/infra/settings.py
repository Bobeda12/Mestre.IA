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
    # Cadeia de fallback (ADR-0008): se `model_name` falhar (cota, timeout,
    # indisponibilidade), tenta o próximo desta lista, na ordem. Todos na
    # própria Groq por ora — ver ADR-0008 para o porquê de não ser um
    # segundo provedor ainda.
    modelos_fallback: list[str] = ["openai/gpt-oss-20b", "qwen/qwen3.6-27b"]
    agent_max_passos: int = 6
    database_url: str = f"sqlite:///{(BASE_DIR / 'rpg_save.db').as_posix()}"
    # Cookie de sessão exige uma origem específica — "*" e credentials são
    # incompatíveis em qualquer navegador (ver ADR-0014). localhost:5173 é a
    # porta padrão do `vite dev`.
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = BASE_DIR / "data"

    # Etapa 8 (ADR-0014) — login por senha e cookie de sessão.
    session_secret: str = "dev-secret-troque-em-producao"
    frontend_url: str = "http://localhost:5173"

    # Login com Google (opcional) — sem estas duas, o botão "Entrar com
    # Google" fica desabilitado no front (GET /auth/opcoes) em vez de
    # quebrar. Criadas em https://console.cloud.google.com/apis/credentials.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"


settings = Settings()
