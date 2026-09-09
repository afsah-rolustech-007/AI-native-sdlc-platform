"""ARQ worker runtime. No LangGraph here — Phase 01 will run the graph inside this process."""

from __future__ import annotations

from typing import ClassVar

from arq.connections import RedisSettings

from common.budget import BudgetTracker
from common.config import get_settings
from common.db import get_engine, make_session_factory
from common.task_repository import get_task
from common.tracing import emit_node_event, get_sink
from worker.hitl_jobs import escalate_expired_hitl


def redis_settings_from_config() -> RedisSettings:
    url = get_settings().redis_url
    from_dsn = getattr(RedisSettings, "from_dsn", None)
    if callable(from_dsn):
        return from_dsn(url)
    from urllib.parse import urlparse

    parsed = urlparse(url)
    database = 0
    if parsed.path and parsed.path not in {"", "/"}:
        database = int(parsed.path.lstrip("/").split("/")[0] or 0)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
    )


async def startup(ctx: dict) -> None:
    ctx["sink"] = get_sink()
    ctx["engine"] = get_engine()


async def shutdown(ctx: dict) -> None:
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


async def ping_task(ctx: dict, task_id: str) -> dict:
    """Proof-of-life job: emit a span and, if the Task exists, a zero-cost row."""
    sink = ctx.get("sink") or get_sink()
    emit_node_event(
        sink,
        task_id=task_id,
        node_id="ping_task",
        agent_id="worker",
        phase="intake",
        model_id=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        latency_ms=0,
        validation_result=None,
    )
    engine = ctx.get("engine") or get_engine()
    factory = make_session_factory(engine)
    async with factory() as session:
        task = await get_task(session, task_id)
        if task is not None:
            tracker = BudgetTracker(session)
            await tracker.record(
                task_id,
                "intake",
                "ping_task",
                0,
                0,
                0.0,
                idempotency_key=f"ping:{task_id}",
            )
    return {"ok": True, "task_id": task_id}


class WorkerSettings:
    functions: ClassVar[list] = [ping_task, escalate_expired_hitl]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings_from_config()
