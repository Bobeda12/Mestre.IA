import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.routers import auth, character, game, options, personagens

# Sem isto, `logger.info(...)`/`logger.error(...)` de qualquer módulo da app
# não aparecem no console: uvicorn configura só os próprios loggers
# ("uvicorn", "uvicorn.access"), não o root — e o root sem handler fica mudo
# abaixo de WARNING (achado ao vivo na Etapa 8, ver docs/diario/0009-etapa-8.md).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

logger = logging.getLogger(__name__)

# Etapa 14 (ADR-0023) — não há mais `lifespan` nenhum aqui: o modelo de
# embedding que precisava de um preload em memória no boot (Etapa 10, A-6)
# virou uma chamada de API (app/infra/embeddings.py). Não existe mais custo
# de "primeira chamada" para pagar antes do primeiro pedido de um jogador.
app = FastAPI(title="Mestre.IA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # exigido pelo cookie de sessão (Etapa 8, ADR-0014)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit por IP (Etapa 9, app/infra/rate_limit.py) — aplicado nos
# endpoints sensíveis via @limiter.limit(...) em routers/auth.py e
# routers/game.py.
app.state.limiter = limiter


def _tratar_rate_limit_excedido(request: Request, exc: Exception) -> Response:
    # slowapi expõe `_rate_limit_exceeded_handler(Request, RateLimitExceeded)
    # -> Response`, mas `add_exception_handler` exige `(Request, Exception)`
    # — o wrapper só estreita o tipo pro mypy, sem mudar o comportamento.
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _tratar_rate_limit_excedido)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(options.router)
app.include_router(auth.router)
app.include_router(character.router)
app.include_router(game.router)
app.include_router(personagens.router)
