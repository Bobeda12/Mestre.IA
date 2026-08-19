# justfile — comandos do Mestre.IA
#
# Instale o `just`: https://github.com/casey/just#installation
# (no Windows: `winget install --id Casey.Just -e`)
#
# Rode `just` sozinho para listar todos os comandos.

default:
    @just --list

# ============================================================
# Backend (FastAPI + uv)
# ============================================================

# Instala as dependências do backend
backend-install:
    cd Backend && uv sync

# Aplica as migrations do Alembic (cria/atualiza rpg_save.db)
backend-migrate: backend-install
    cd Backend && uv run alembic upgrade head

# Sobe o backend em modo desenvolvimento (recarrega a cada mudança), porta 8000
backend-dev: backend-migrate
    cd Backend && uv run uvicorn app.main:app --reload --port 8000

# Roda a suíte de testes do backend, com cobertura em domain/ e services/
backend-test: backend-install
    cd Backend && uv run pytest -v --cov=app/domain --cov=app/services --cov-report=term-missing

# Roda ruff (lint) e mypy (tipos) no backend
backend-lint: backend-install
    cd Backend && uv run ruff check . && uv run mypy app

# ============================================================
# Frontend (Vite + React)
# ============================================================

# Instala as dependências do frontend
frontend-install:
    cd Frontend && npm install

# Sobe o frontend em modo desenvolvimento, porta 5173
frontend-dev: frontend-install
    cd Frontend && npm run dev

# Roda o linter do frontend
frontend-lint: frontend-install
    cd Frontend && npm run lint

# ============================================================
# Atalhos que cobrem o projeto inteiro
# ============================================================

# Instala as dependências dos dois lados
install: backend-install frontend-install

# Roda toda a suíte de testes automatizada do projeto
# (só o backend tem testes até a Etapa 7; Vitest/Playwright entram lá)
test: backend-test

# Roda o lint dos dois lados
lint: backend-lint frontend-lint

# Sobe o backend em modo dev — o frontend sobe à parte, em outro
# terminal, com `just frontend-dev` (são dois processos bloqueantes,
# não dá para rodar os dois num só comando)
dev: backend-dev
