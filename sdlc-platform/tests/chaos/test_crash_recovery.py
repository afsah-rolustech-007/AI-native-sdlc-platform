"""Crash-recovery harness: SIGKILL mid-graph, restart, 20/20 complete.

Kill timing uses node-enter files (`SDLC_CHAOS_HOOK_DIR`), not wall-clock sleeps.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from tests.chaos.harness import send_go, sigkill, spawn_worker, wait_exit, wait_ready
from tests.factories import make_task

from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.sandbox import list_sandbox_container_ids
from common.task_repository import create_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import postgres_checkpointer
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.runtime import is_complete, thread_config

WINDOWS = ("pre_first_node", "mid_sequence", "at_interrupt", "post_resume")
TRIALS = 20


def _phase_completed(snapshot) -> list[str]:
    return [
        event["phase"]
        for event in (snapshot.values.get("agent_events") or [])
        if event.get("event_type") == "phase_completed"
    ]


def phases_are_complete_subsequence(observed: list[str], expected: tuple[str, ...]) -> bool:
    """All expected phases appear in order; duplicates from re-entry are allowed."""
    cursor = iter(observed)
    for want in expected:
        for got in cursor:
            if got == want:
                break
        else:
            return False
    return True


async def _create_task(database_url: str, task_id: str):
    engine = make_async_engine(database_url)
    factory = make_session_factory(engine)
    task = make_task(id=task_id)
    async with factory() as session:
        await create_task(session, task)
    await engine.dispose()
    return task


async def _snapshot(database_url: str, task):
    async with postgres_checkpointer(database_url, setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=False, sink=NoOpTelemetrySink())
        return await graph.aget_state(thread_config(task.id))


def _finish_without_hooks(task_id: str, database_url: str, *, checkpointer: str = "postgres") -> int:
    proc = spawn_worker(task_id, database_url=database_url, checkpointer=checkpointer)
    code = wait_exit(proc)
    if code == 10:
        proc = spawn_worker(
            task_id, database_url=database_url, resume="approve", checkpointer=checkpointer
        )
        code = wait_exit(proc)
    return code


def _run_until_interrupt(task_id: str, database_url: str, hook_dir: Path) -> None:
    proc = spawn_worker(task_id, database_url=database_url, hook_dir=hook_dir)
    try:
        for phase in ("intake", "requirements", "design"):
            wait_ready(hook_dir, phase)
            send_go(hook_dir, phase)
        code = wait_exit(proc)
        if code not in {0, 10}:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"worker failed ({code}): {stderr}")
    finally:
        if proc.poll() is None:
            sigkill(proc)


def _kill_at_window(window: str, task_id: str, database_url: str, hook_dir: Path) -> str:
    """Return how we killed, for the results log."""
    if window == "at_interrupt":
        _run_until_interrupt(task_id, database_url, hook_dir)
        return "at_interrupt: worker exited paused, then SIGKILL if needed"

    if window == "post_resume":
        _run_until_interrupt(task_id, database_url, hook_dir)
        resume_hooks = hook_dir / "resume"
        resume_hooks.mkdir()
        proc = spawn_worker(
            task_id, database_url=database_url, hook_dir=resume_hooks, resume="approve"
        )
        try:
            wait_ready(resume_hooks, "design")
            send_go(resume_hooks, "design")
            wait_ready(resume_hooks, "implementation")
            send_go(resume_hooks, "implementation")
            wait_ready(resume_hooks, "qa")
            sigkill(proc)
        finally:
            if proc.poll() is None:
                sigkill(proc)
        return "post_resume: SIGKILL at qa.ready"

    proc = spawn_worker(task_id, database_url=database_url, hook_dir=hook_dir)
    try:
        if window == "pre_first_node":
            wait_ready(hook_dir, "intake")
            sigkill(proc)
            return "pre_first_node: SIGKILL at intake.ready"
        wait_ready(hook_dir, "intake")
        send_go(hook_dir, "intake")
        wait_ready(hook_dir, "requirements")
        sigkill(proc)
        return "mid_sequence: SIGKILL at requirements.ready"
    finally:
        if proc.poll() is None:
            sigkill(proc)


async def test_twenty_crash_trials_all_recover(migrated_database_url: str, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    windows = [WINDOWS[i % len(WINDOWS)] for i in range(TRIALS)]
    random.Random(42).shuffle(windows)
    results: list[dict] = []

    for index, window in enumerate(windows):
        task_id = f"chaos-{index:02d}-{window}"
        task = await _create_task(migrated_database_url, task_id)
        hook_dir = tmp_path / task_id
        hook_dir.mkdir()
        note = _kill_at_window(window, task_id, migrated_database_url, hook_dir)
        code = _finish_without_hooks(task_id, migrated_database_url)
        snapshot = await _snapshot(migrated_database_url, task)
        observed = _phase_completed(snapshot)
        passed = (
            code == 0
            and is_complete(snapshot)
            and phases_are_complete_subsequence(observed, PHASE_ORDER)
            and list_sandbox_container_ids(task_id) == []
        )
        results.append(
            {
                "trial": index,
                "window": window,
                "kill": note,
                "passed": passed,
                "exit_code": code,
                "phases": observed,
            }
        )
        if not passed:
            stderr_hint = results[-1]
            raise AssertionError(f"trial {index} failed: {stderr_hint}")

    results_path = tmp_path / "crash_recovery_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"crash recovery {sum(r['passed'] for r in results)}/{TRIALS} -> {results_path}")
    assert all(row["passed"] for row in results)
    assert {row["window"] for row in results} == set(WINDOWS)

    reset_engine()
    get_settings.cache_clear()


async def test_harness_detects_missing_durable_checkpoint(
    migrated_database_url: str, monkeypatch, tmp_path: Path
) -> None:
    """Self-check: an in-memory checkpointer must not look recovered after SIGKILL."""
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task_id = "chaos-mutation-memory"
    task = await _create_task(migrated_database_url, task_id)
    hook_dir = tmp_path / task_id
    hook_dir.mkdir()
    proc = spawn_worker(
        task_id,
        database_url=migrated_database_url,
        hook_dir=hook_dir,
        checkpointer="memory",
    )
    try:
        wait_ready(hook_dir, "intake")
        send_go(hook_dir, "intake")
        wait_ready(hook_dir, "requirements")
        sigkill(proc)
    finally:
        if proc.poll() is None:
            sigkill(proc)

    snapshot = await _snapshot(migrated_database_url, task)
    assert not is_complete(snapshot)
    assert not phases_are_complete_subsequence(_phase_completed(snapshot), PHASE_ORDER)

    reset_engine()
    get_settings.cache_clear()
