FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Etapa 10 (A-6) — baixa o modelo de embedding AGORA, uma vez, na imagem
# (não em `/tmp`, ver app/infra/embeddings.py:CACHE_DIR — alguns runtimes
# de container montam um tmpfs por cima de `/tmp`, o que apagaria isto
# antes do container sequer subir). Sem isto, o primeiro pedido da
# primeira sessão numa máquina nova pagava o download inteiro do
# HuggingFace dentro do turno de um jogador de verdade.
RUN uv run --no-dev python -c "from app.infra.embeddings import carregar_modelo; carregar_modelo()"

EXPOSE 8000

# `uv run` faz um sync implícito antes de rodar — sem --no-dev aqui, ele
# reinstalaria ruff/mypy/pytest no container em todo restart, gastando
# rede à toa num ambiente que não precisa de nenhum dos dois.
#
# `alembic upgrade head` SAIU daqui (Etapa 10, A-6) — rodava a cada boot de
# máquina (o Fly desliga a máquina quando ninguém joga e reboota no próximo
# pedido), não uma vez por deploy. Virou `release_command` em fly.toml.
CMD ["sh", "-c", "uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
