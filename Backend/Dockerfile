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
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
