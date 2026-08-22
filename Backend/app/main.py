import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.infra import embeddings
from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.routers import auth, character, game, options, personagens

# Sem isto, `logger.info(...)`/`logger.error(...)` de qualquer módulo da app
# não aparecem no console: uvicorn configura só os próprios loggers
# ("uvicorn", "uvicorn.access"), não o root — e o root sem handler fica mudo
# abaixo de WARNING (achado ao vivo na Etapa 8, ver docs/diario/0009-etapa-8.md).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Etapa 10 (A-6) — antes disto, o modelo de embedding só carregava no
    # primeiro pedido que precisasse dele (`services/memory.py`), ou seja,
    # dentro do turno de algum jogador. Carregar no boot paga esse custo
    # antes do primeiro pedido, não durante ele — com o cache já baixado em
    # build time (Dockerfile), isto é leitura de disco, não download de
    # rede, então não atrasa o `/health` check do Fly.io de forma sensível.
    logger.info("Carregando modelo de embeddings no boot...")
    embeddings.carregar_modelo()
    logger.info("Modelo de embeddings carregado.")
    yield


app = FastAPI(title="Mestre.IA", lifespan=_lifespan)
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
