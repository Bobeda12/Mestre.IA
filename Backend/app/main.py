from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infra.db import SessionLocal, garantir_usuario_local
from app.infra.settings import settings
from app.routers import character, game, options


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    db = SessionLocal()
    try:
        garantir_usuario_local(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Mestre.IA", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(options.router)
app.include_router(character.router)
app.include_router(game.router)
