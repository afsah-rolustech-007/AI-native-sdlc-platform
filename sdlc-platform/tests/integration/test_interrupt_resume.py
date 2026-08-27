"""Process-boundary interrupt / resume against Postgres."""

from tests.factories import make_task

from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.task_repository import create_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import postgres_checkpointer
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.runtime import interrupt_value, is_complete, resume_graph, start_or_continue


async def test_resume_from_new_connection_completes(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(id="task-resume-proc")
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)

    async with postgres_checkpointer(migrated_database_url, setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        paused = await start_or_continue(graph, task)
        assert interrupt_value(paused) is not None
        assert "design" in tuple(paused.next or ())

    async with postgres_checkpointer(migrated_database_url, setup=False) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        snapshot = await resume_graph(graph, task, "approve")
        assert is_complete(snapshot)
        phases = [
            event["phase"]
            for event in snapshot.values["agent_events"]
            if event["event_type"] == "phase_completed"
        ]
        assert phases == list(PHASE_ORDER)

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()
