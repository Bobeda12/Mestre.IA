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

    # "development" por padrão de propósito — só o `render.yaml`/variáveis
    # de ambiente de produção (Etapa 9/14) setam "production" explicitamente.
    # Controla só a trava do SESSION_SECRET abaixo, nada de lógica de negócio.
    environment: str = "development"
    groq_api_key: str | None = None
    # Gemini (AI Studio) — chave sem cartão. Serve dois papéis desde a
    # Etapa 14 (ADR-0023, ADR-0024): provedor dos embeddings
    # (app/infra/embeddings.py) e segundo provedor na cadeia de fallback
    # de chat abaixo. Sem esta chave, embeddings degradam para BM25 puro
    # (ver embeddings.py) e `cadeia_llm` simplesmente pula qualquer elo
    # "gemini:..." — o mesmo padrão condicional do Google OAuth/Langfuse.
    gemini_api_key: str | None = None
    # Cadeia de fallback (ADR-0008, revista pelo ADR-0024): cada item é
    # "provedor:modelo" — `app/infra/llm_client.py` tenta em ordem, e
    # `tenacity` cobre retry por erro transitório dentro de cada elo antes
    # de cair para o próximo. Atravessa provedores de propósito: a cota do
    # free tier da Groq (200k tokens/dia por modelo) e a do Gemini são
    # contas separadas — um provedor esgotado no dia não derruba o outro.
    cadeia_llm: list[str] = [
        "groq:openai/gpt-oss-120b",
        "gemini:gemini-3.5-flash",
        "groq:openai/gpt-oss-20b",
        "groq:qwen/qwen3.6-27b",
    ]
    # Chamada barata/de baixo risco: o resumo rolante (services/memory.py) e
    # o padrão do LLM-as-judge (evals/judge.py) — este último de propósito
    # num provedor DIFERENTE do primeiro elo de `cadeia_llm` acima, reduzindo
    # o viés de o juiz "gostar" do próprio estilo do narrador (a limitação
    # que o ADR-0011 já registrava como fica em aberto).
    modelo_barato: str = "gemini:gemini-3.5-flash-lite"
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

    # Etapa 10 (A-3) — teto de turnos por usuário/dia. A chave da Groq é
    # uma só, do autor; sem isto, dez amigos animados no mesmo dia drenam
    # a cota compartilhada de todo mundo. Convidado tem teto menor: quem
    # ainda nem criou conta tem menos a perder desistindo por hoje.
    #
    # Etapa 15 (BYOK) — baixado de 60/20 pra este valor mais conservador.
    # Não é um número calculado: o Google parou de publicar uma tabela fixa
    # de free tier pro Gemini (redireciona pro painel da conta), e a Groq
    # documenta só 1.000 requisições/dia POR MODELO (3 modelos na cadeia),
    # com cada "turno" podendo custar várias chamadas de verdade
    # (`agent_max_passos`, o loop de ferramentas). Ponto de partida
    # deliberadamente baixo, pra recalibrar depois com telemetria real
    # (`EventoTelemetria`) — quem quiser mais sem esperar essa calibração já
    # pode trazer a própria chave (`teto_turnos_conta`/`convidado` não se
    # aplicam a quem manda `X-Gemini-Key`, ver `routers/game.py`).
    teto_turnos_conta: int = 20
    teto_turnos_convidado: int = 8
    # Etapa 15 (BYOK) — quando a chave própria do jogador falha no meio do
    # jogo e ele topa usar a chave do servidor "por enquanto" (modo de
    # emergência), este teto (bem menor que o normal, contado à parte)
    # evita que isso vire um jeito de sempre ter mais turnos trocando de
    # chave. Ver `routers/game.py._verificar_teto_diario`.
    teto_turnos_emergencia: int = 5

    # Etapa 10 (A-2) — confirmação de e-mail bloqueante. Mesmo padrão
    # condicional do Google/Langfuse: sem nenhum dos dois métodos abaixo
    # configurado, o link de confirmação só é logado (`app/infra/email.py`)
    # — dev continua funcionando sem conta nenhuma.
    #
    # SMTP do Gmail é o método preferido (checado primeiro): o remetente de
    # teste do Resend (`onboarding@resend.dev`) é compartilhado entre
    # milhares de contas, sem SPF/DKIM alinhado a este projeto — cai em
    # spam quase sempre. Deliverability de verdade pediria um domínio
    # próprio verificado no Resend, que custa dinheiro; a alternativa sem
    # custo é autenticar como uma conta Gmail de verdade (a reputação é da
    # conta, não do provedor de e-mail transacional).
    smtp_email: str | None = None
    smtp_senha_app: str | None = None  # "senha de app" do Google, não a senha normal da conta
    smtp_host: str = "smtp.gmail.com"
    smtp_porta: int = 587

    # Resend como alternativa/fallback — mantido por se um domínio próprio
    # for verificado lá no futuro. `onboarding@resend.dev` funciona sem
    # verificar domínio, mas com o problema de deliverability acima.
    resend_api_key: str | None = None
    resend_from_email: str = "Mestre.IA <onboarding@resend.dev>"
    confirmacao_email_url: str = "http://localhost:8000/auth/confirmar"

    # Etapa 10 (A-6) — teto de eventos de memória trazidos do banco por
    # turno (services/memory.memorias_relevantes). Sem isto, a query cresce
    # com o tamanho da partida inteira, não com o turno atual.
    limite_eventos_memoria: int = 200


settings = Settings()

if settings.environment == "production" and settings.session_secret == SESSION_SECRET_DEV:
    # Falha alto e cedo, na inicialização — não em runtime, quando o
    # primeiro cookie já teria sido assinado com uma chave que qualquer
    # leitor deste repositório também conhece (Etapa 9).
    raise RuntimeError(
        "SESSION_SECRET ainda é o valor de desenvolvimento em produção (ENVIRONMENT=production). "
        'Gere um novo com `python -c "import secrets; print(secrets.token_hex(32))"` '
        "e configure em Environment, no dashboard do Render."
    )
