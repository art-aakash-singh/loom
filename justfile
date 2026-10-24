set dotenv-load := false

default:
    @just --list

# Install all dependencies
setup:
    uv sync
    pnpm install

# Start infra, then API + web together (Ctrl-C stops both)
dev: infra
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn loom_api.main:app --reload --reload-dir apps/api --app-dir apps/api/src --port 8000 &
    pnpm --filter web dev &
    wait

infra:
    docker compose up -d --wait

infra-down:
    docker compose down

# Apply database migrations (run after `just infra`)
migrate:
    uv run alembic -c apps/api/alembic.ini upgrade head

test:
    uv run pytest
    pnpm --filter web test

lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy
    pnpm --filter web lint
    pnpm --filter web typecheck

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Regenerate the TS client from the FastAPI OpenAPI schema
gen-client:
    uv run python scripts/dump_openapi.py apps/web/openapi.json
    pnpm --filter web gen-client
