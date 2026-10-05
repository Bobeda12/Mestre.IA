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
    # (ver embeddings.py) e as cadeias abaixo simplesmente pulam qualquer elo
    # "gemini:..." — o mesmo padrão condicional do Google OAuth/Langfuse.
    gemini_api_key: str | None = None
    # Um modelo por papel (ADR-0038, revisa o ADR-0008 e o ADR-0024). Antes
    # havia uma cadeia só (`cadeia_llm`) para tudo; em produção ela se
    # reduzia ao `gemini-3.5-flash`, que no plano gratuito dá 5 chamadas por
    # minuto e 20 por dia (medido em 05/10/2026, Diário 0041/0042). Cada
    # papel tem a própria lista de "provedor:modelo", tentada em ordem por
    # `app/infra/llm_client.py`; elos de provedor sem chave são pulados.
    #
    # volume — o que acontece a toda hora: turno de jogo, correção do
    # guardrail, Oráculo da criação. Só o Flash Lite tem cota para isso
    # (15/min, 500/dia). Os Flash de 20/dia vêm depois como reserva; o
    # 3.1 Flash Lite fica no fim porque na avaliação caiu numa injeção de
    # prompt e devolveu 503 em 12 de 30 chamadas.
    cadeia_volume: list[str] = [
        "gemini:gemini-3.5-flash-lite",
        "gemini:gemini-3.5-flash",
        "gemini:gemini-3.6-flash",
        "gemini:gemini-2.5-flash",
        "gemini:gemini-3.7-flash",
        "gemini:gemini-3.8-flash",
        "gemini:gemini-3.1-flash-lite",
        "groq:openai/gpt-oss-120b",
        "groq:openai/gpt-oss-20b",
    ]
    # destaque — poucas chamadas, lidas com atenção: prólogo, turno de
    # morte, epitáfio, desfecho de capítulo, crônica.
    #
    # A ideia original era abrir pelos Flash (modelo maior, 20/dia cada).
    # Medido em 05/10/2026, só no prólogo: o 3.5 Flash Lite entregou 13 de
    # 13 em cerca de 6 s; os Flash, quando responderam, levaram de 28 a
    # 47 s, e em duas baterias seguidas (2.5 e 3.6) não entregaram nenhum de
    # 7 — só 503, estouro de tempo e cota. Com 80 s de prazo para o prólogo
    # inteiro, dois Flash pendurados gastavam tudo antes de o Lite ser
    # tentado. Por isso os dois Lite abrem a fila (rápidos: falham ou
    # respondem em segundos, ver `timeouts_modelo`) e os Flash ficam com o
    # tempo que sobrar. O 3.1 Flash Lite foi mal nos turnos (ferramentas,
    # injeção de prompt), mas o prólogo é só texto e o dele saiu bom. Se o
    # Google estabilizar os Flash, basta reordenar aqui (ou em
    # `CADEIA_DESTAQUE`).
    cadeia_destaque: list[str] = [
        "gemini:gemini-3.5-flash-lite",
        "gemini:gemini-3.1-flash-lite",
        "gemini:gemini-3.5-flash",
        "gemini:gemini-3.6-flash",
        "gemini:gemini-2.5-flash",
        "gemini:gemini-3.7-flash",
        "gemini:gemini-3.8-flash",
        "groq:openai/gpt-oss-120b",
    ]
    # fundo — o resumo rolante da memória (services/memory.py): roda em
    # segundo plano a cada 8 turnos e, se falhar, o resumo antigo continua
    # valendo. Ordem invertida em relação a `cadeia_volume` para não gastar
    # a cota do Lite que sustenta os turnos.
    cadeia_fundo: list[str] = [
        "gemini:gemini-3.1-flash-lite",
        "gemini:gemini-3.5-flash-lite",
    ]
    # Tempo limite por chamada, em segundos, por papel. Estourou: o modelo
    # é pausado e a cadeia segue para o próximo. O turno responde em 2 a
    # 5 s no Flash Lite (p95 de 20 s na avaliação); o prólogo é um JSON
    # grande e já levou 47 s num Flash, por isso o destaque tem mais folga.
    timeouts_ia: dict[str, float] = {"volume": 25.0, "destaque": 50.0, "fundo": 30.0}
    # Tempo limite mais curto para modelos que respondem rápido quando
    # estão bem. O Flash Lite fez os prólogos medidos em 4 a 21 s; esperar os 50 s
    # do papel de destaque por ele, num dia ruim do Google, gastava mais da
    # metade do prazo do prólogo com um modelo que não ia responder. Vale o
    # menor entre este e o do papel.
    timeouts_modelo: dict[str, float] = {"gemini-3.5-flash-lite": 22.0, "gemini-3.1-flash-lite": 22.0}
    # Prazo da cadeia inteira, por papel: quanto o jogador espera no pior
    # caso, somando todos os modelos tentados. Acabou o prazo, a chamada
    # falha e quem chamou usa a sua saída de emergência (texto de reserva
    # no prólogo, turno só com o juiz no jogo).
    prazos_ia: dict[str, float] = {"volume": 45.0, "destaque": 90.0, "fundo": 60.0}
    # Limites do plano gratuito por modelo: [chamadas por minuto, chamadas
    # por dia]. Lidos no painel da conta (ai.dev/rate-limit) em 05/10/2026;
    # o Google muda esses números sem aviso, conferir de tempos em tempos.
    # `llm_client` conta as chamadas e pula o modelo que chegou ao limite.
    # Modelo ausente daqui (os da Groq) não é contado contra limite nenhum.
    limites_ia: dict[str, list[int]] = {
        "gemini-3.5-flash-lite": [15, 500],
        "gemini-3.1-flash-lite": [15, 500],
        "gemini-3.5-flash": [5, 20],
        "gemini-3.6-flash": [5, 20],
        "gemini-3.7-flash": [5, 20],
        "gemini-3.8-flash": [5, 20],
        "gemini-2.5-flash": [5, 20],
    }
    # Quanto os modelos Gemini "pensam" antes de responder, por papel
    # (`reasoning_effort`: minimal, low, medium, high). Papel ausente = o
    # padrão do modelo.
    esforco_raciocinio: dict[str, str] = {}
    # Modelo fixo do LLM-as-judge (evals/judge.py). O resumo rolante usa
    # `cadeia_fundo` acima, com a chave do servidor ou a do jogador.
    modelo_barato: str = "gemini:gemini-3.5-flash-lite"
    agent_max_passos: int = 6
    # Auditoria pré-lançamento (Fase 1/Mundo Vivo) mediu esta régua contra o
    # esquema COMPLETO de ferramentas (51, sem filtro de `tools_para`, como
    # os testes de `agent_loop` usam por padrão quando não passam `tools=`):
    # ~10500 estimado (chars/3) só de schema, sem nenhuma mensagem. 12000
    # já é pouca folga para esse caso sintético; reduzir mais quebra esses
    # testes sem refletir produção (que sempre usa `tools_para`, bem menor).
    # A contagem real da Groq, medida ao vivo (Diário 0026), fica mais perto
    # de chars/4 — ou seja, esta estimativa (chars/3) já é conservadora. Não
    # é um teto de cobrança do provedor (ver docs/eficiencia-ia.md); é só um
    # limite de sanidade local. A proteção de verdade contra o teto real de
    # 8000 tokens/minuto da Groq vem de manter `tools_para` enxuto por turno
    # (ver `_CAMPOS_DO_SERVIDOR`, `gatilhos`) — não deste número.
    agent_limite_entrada_estimado: int = 12000
    # Achado ao vivo em produção (15/09/2026, ver Diário 0040): com 24000, um
    # turno de só 4 chamadas (ação rejeitada → consultar_contexto →
    # rolar_teste → narrar) já estourava este teto ANTES de tentar a
    # narração — sem nenhuma chamada de rede sequer acontecer (o log do
    # Render mostrava as 3 chamadas anteriores voltando 200 OK da Gemini, e
    # a 4ª falhando em 1ms, tempo incompatível com uma requisição de
    # verdade). Ou seja: o próprio teto local, não o provedor, estava
    # forçando `NARRATIVA_SEM_VOZ` num turno comum, bem antes de
    # `agent_max_passos` (6) ser atingido. Cada chamada soma até
    # `agent_limite_entrada_estimado`; 60000 dá fôlego para as 6 chamadas
    # permitidas sem reabrir a proteção contra um turno de verdade fora de
    # controle (a defesa real contra o teto por minuto de cada provedor
    # continua sendo `tools_para` enxuto, não este número — ver comentário
    # acima).
    agent_limite_turno_estimado: int = 60000
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
    #
    # 05/10/2026 (ADR-0038) — revisto com números medidos e mantido em 20/8:
    # o servidor sustenta cerca de 185 turnos por dia (500 chamadas do 3.5
    # Flash Lite ÷ 2,7 chamadas por turno), então 20 por conta dá uns 9
    # jogadores ativos no mesmo dia. Subir o teto diminuiria esse número.
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
