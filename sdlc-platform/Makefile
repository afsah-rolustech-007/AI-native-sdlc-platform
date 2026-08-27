.PHONY: up migrate test lint typecheck dev checkpointer chaos

# uv + Python 3.12 are required (see docs/techstack.md).
UV ?= uv
COMPOSE ?= docker compose
export PYTHONPATH := packages:apps

up:
	$(COMPOSE) up -d postgres redis

migrate:
	$(UV) run alembic upgrade head
	$(UV) run python scripts/init_langgraph_tables.py

checkpointer:
	$(UV) run python scripts/init_langgraph_tables.py

test:
	$(UV) run pytest tests/unit tests/integration tests/contract -m "not live"

chaos:
	$(UV) run pytest tests/chaos -v

lint:
	$(UV) run ruff check packages tests scripts db apps

typecheck:
	$(UV) run mypy

# API on :8000 and ARQ worker. Ctrl-C stops the worker; kill the API pid if leftover.
dev:
	$(UV) run uvicorn api.main:app --host 0.0.0.0 --port 8000 & \
	$(UV) run arq worker.main.WorkerSettings
