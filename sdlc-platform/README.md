# sdlc-platform

Application code for the AI-Native SDLC Orchestration Platform.

Specs: `../docs/` and `../final_plan.md`.

## Setup (Python 3.12 + uv)

```bash
cd sdlc-platform
uv python pin 3.12
uv sync --extra dev
cp .env.example .env
make up
make migrate
make test
```

## Run API + worker

```bash
make dev
# other terminal: curl localhost:8000/health
```

Or two terminals:

```bash
uv run uvicorn api.main:app --port 8000
uv run arq worker.main.WorkerSettings
```

## Demos

```bash
uv run python scripts/demo_section04.py
uv run python scripts/demo_phase0.py
uv run python scripts/demo_phase0.py --breach
uv run python scripts/demo_section01.py
uv run python scripts/demo_section02.py
uv run python scripts/resume_task.py <task_id> approve
uv run python scripts/demo_phase02.py
uv run pytest tests/chaos -v
```
