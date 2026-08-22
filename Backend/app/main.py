import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infra.settings import settings
from app.routers import auth, character, game, options, personagens

# Sem isto, `logger.info(...)`/`logger.error(...)` de qualquer módulo da app
# não aparecem no console: uvicorn configura só os próprios loggers
# ("uvicorn", "uvicorn.access"), não o root — e o root sem handler fica mudo
# abaixo de WARNING (achado ao vivo na Etapa 8, ver docs/diario/0009-etapa-8.md).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Mestre.IA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # exigido pelo cookie de sessão (Etapa 8, ADR-0014)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(options.router)
app.include_router(auth.router)
app.include_router(character.router)
app.include_router(game.router)
app.include_router(personagens.router)
