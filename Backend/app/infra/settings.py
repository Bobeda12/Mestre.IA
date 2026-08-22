from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

SESSION_SECRET_DEV = "dev-secret-troque-em-producao"


class Settings(BaseSettings):
    """Config tipada — substitui os.getenv() solto (api.py, versão anterior à Etapa 2).
    Lida de variáveis de ambiente e de Backend/.env (ver ADR-0003)."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # "development" por padrão de propósito — só o `fly.toml`/secrets de
    # produção (Etapa 9) setam "production" explicitamente. Controla só a
    # trava do SESSION_SECRET abaixo, nada de lógica de negócio.
    environment: str = "development"
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
    # String simples separada por vírgula, não `list[str]` — pydantic-settings
    # exige JSON estrito (`["a","b"]`) para campos de lista vindos de env var,
    # o que é frágil de passar por linha de comando (aspas/colchetes viram
    # alvo de quoting do shell; foi exatamente o que quebrou o primeiro
    # `fly secrets set` desta origem na Etapa 9). `cors_origins_list` abaixo
    # faz o parse.
    cors_origins: str = "http://localhost:5173"
    data_dir: Path = BASE_DIR / "data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]

    # Etapa 8 (ADR-0014) — login por senha e cookie de sessão.
    session_secret: str = SESSION_SECRET_DEV
    frontend_url: str = "http://localhost:5173"

    # Login com Google (opcional) — sem estas duas, o botão "Entrar com
    # Google" fica desabilitado no front (GET /auth/opcoes) em vez de
    # quebrar. Criadas em https://console.cloud.google.com/apis/credentials.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # Etapa 9 — tracing de custo/latência/tokens por turno (app/infra/tracing.py).
    # Mesmo padrão do Google: sem as duas chaves, o tracing fica desligado em
    # vez de quebrar (útil em dev, onde ninguém precisa de conta no Langfuse
    # só para rodar o jogo localmente).
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    # Langfuse Cloud tem regiões separadas (EU vs US) com chaves que só
    # valem na própria região — "https://cloud.langfuse.com" (EU) devolvia
    # 401 com uma chave criada na região US. Confirmado com
    # `Langfuse.auth_check()` contra a conta real desta etapa.
    langfuse_host: str = "https://us.cloud.langfuse.com"


settings = Settings()

if settings.environment == "production" and settings.session_secret == SESSION_SECRET_DEV:
    # Falha alto e cedo, na inicialização — não em runtime, quando o
    # primeiro cookie já teria sido assinado com uma chave que qualquer
    # leitor deste repositório também conhece (Etapa 9).
    raise RuntimeError(
        "SESSION_SECRET ainda é o valor de desenvolvimento em produção (ENVIRONMENT=production). "
        'Gere um novo com `python -c "import secrets; print(secrets.token_hex(32))"` '
        "e configure via `fly secrets set SESSION_SECRET=...`."
    )
