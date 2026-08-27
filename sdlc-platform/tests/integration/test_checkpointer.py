"""Durable LangGraph checkpoints in Postgres."""

from sqlalchemy import text
from tests.factories import make_task

from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.task import TaskState
from common.task_repository import create_task, get_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import (
    get_thread_id,
    postgres_checkpointer,
)
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.runtime import is_complete, run_to_completion


async def test_checkpoints_survive_a_new_connection(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(id="task-ckpt-1")
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)

    thread_id = get_thread_id(task)
    config = {"configurable": {"thread_id": thread_id}}

    async with postgres_checkpointer(migrated_database_url, setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        snapshot = await run_to_completion(graph, task, decision="approve")
        phases = [
            event["phase"]
            for event in snapshot.values["agent_events"]
            if event["event_type"] == "phase_completed"
        ]
        assert phases == list(PHASE_ORDER)

    async with engine.connect() as conn:
        counts = await conn.execute(
            text(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = :tid"
            ),
            {"tid": thread_id},
        )
        checkpoint_count = counts.scalar_one()
    assert checkpoint_count >= 8

    async with postgres_checkpointer(migrated_database_url, setup=False) as saver:
        graph = build_graph(
            checkpointer=saver, persist_task_state=False, sink=NoOpTelemetrySink()
        )
        snapshot = await graph.aget_state(config)
        assert snapshot.values["task_id"] == task.id
        assert is_complete(snapshot)
        assert snapshot.values["requirements"] is not None
        assert snapshot.next == ()

    async with factory() as session:
        stored = await get_task(session, task.id)
        assert stored is not None
        assert stored.state is TaskState.DONE

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


async def test_thread_id_255_chars_is_stored_verbatim(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(id="b" * 255)
    assert get_thread_id(task) == task.id
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)

    async with postgres_checkpointer(migrated_database_url, setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        snapshot = await run_to_completion(graph, task, decision="approve")
        assert is_complete(snapshot)

    async with engine.connect() as conn:
        row = await conn.execute(
            text("SELECT thread_id FROM checkpoints WHERE thread_id = :tid LIMIT 1"),
            {"tid": task.id},
        )
        stored_id = row.scalar_one()
    assert stored_id == task.id
    assert len(stored_id) == 255

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()
