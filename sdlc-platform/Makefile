.PHONY: up migrate test lint typecheck dev checkpointer chaos benchmark ri-demo zoekt-install zoekt-pull zoekt-webserver zoekt-webserver-stop

# uv + Python 3.12 are required (see docs/techstack.md).
UV ?= uv
COMPOSE ?= docker compose
export PYTHONPATH := packages:apps

# Optional human UI for Zoekt shards. Search itself is one-shot CLI (`zoekt -jsonl`),
# not this process. Phase 11 can operate a long-running Zoekt service.
ZOEKT_INDEX_DIR ?= $(HOME)/.cache/sdlc-platform/zoekt
ZOEKT_LISTEN ?= :6070
ZOEKT_IMAGE ?= ghcr.io/sourcegraph/zoekt

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

# Section 06 success@5 against the frozen labeled corpus. Needs `make up && make migrate`.
benchmark:
	$(UV) run python tests/benchmark/retrieval_precision.py

# Phase 03 live demo: uncommitted edit -> incremental reindex -> RepositoryIntelligence.
ri-demo:
	$(UV) run python scripts/demo_repo_intelligence.py

lint:
	$(UV) run ruff check packages tests scripts db apps

typecheck:
	$(UV) run mypy

# API on :8000 and ARQ worker. Ctrl-C stops the worker; kill the API pid if leftover.
dev:
	$(UV) run uvicorn api.main:app --host 0.0.0.0 --port 8000 & \
	$(UV) run arq worker.main.WorkerSettings

zoekt-install:
	@command -v go >/dev/null 2>&1 || { echo "install Go from https://go.dev/dl/ then re-run make zoekt-install"; exit 1; }
	go install github.com/sourcegraph/zoekt/cmd/zoekt-index@latest
	go install github.com/sourcegraph/zoekt/cmd/zoekt@latest
	go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver@latest

zoekt-pull:
	docker pull $(ZOEKT_IMAGE)

# Optional. Does not replace ZoektClient.search. Ctrl-C to stop.
zoekt-webserver:
	zoekt-webserver -index $(ZOEKT_INDEX_DIR) -listen $(ZOEKT_LISTEN)

zoekt-webserver-stop:
	-pkill -f 'zoekt-webserver -index'
