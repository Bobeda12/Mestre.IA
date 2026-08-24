FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

# `uv run` faz um sync implícito antes de rodar — sem --no-dev aqui, ele
# reinstalaria ruff/mypy/pytest no container em todo restart, gastando
# rede à toa num ambiente que não precisa de nenhum dos dois.
#
# `alembic upgrade head` voltou pra cá (migração Fly.io → Render, ver
# ADR-0022). Na Etapa 10 (A-6) tinha saído daqui porque o Fly tinha um
# `release_command` (roda uma vez por deploy, fora do CMD); o Render no
# plano free não tem equivalente, então volta a rodar a cada boot de
# máquina — idempotente e barato (é um no-op se já está na head), o custo
# real é só a checagem contra o Neon a cada wake do free tier.
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
