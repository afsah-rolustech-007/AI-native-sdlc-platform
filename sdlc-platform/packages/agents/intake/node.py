"""Wire Planning Manager into the LangGraph `intake` step.

Default `build_graph()` still uses a no-op stub so old Phase 01 tests keep
pausing at design. To use the real classifier:

    build_graph(node_overrides={"intake": build_intake_node(router=...)})
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.intake.planning_manager import (
    UNAVAILABLE_SUMMARY,
    PlanningManager,
    last_user_text,
)
from common.budget import BudgetTracker
from common.db import get_engine, make_session_factory
from common.task import RiskTier, WorkType
from common.task_repository import get_task, update_task_classification
from common.telemetry import NoOpTelemetrySink, TelemetrySink
from model_adapters.router import ModelRouter
from orchestration.masc import MASCEngine
from orchestration.state import SDLCState

ArchitectureSummaryLoader = Callable[[], Awaitable[str]]


def build_intake_node(
    *,
    router: ModelRouter,
    masc: MASCEngine | None = None,
    sink: TelemetrySink | None = None,
    persist_classification: bool = True,
    architecture_summary_loader: ArchitectureSummaryLoader | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> Callable[[SDLCState], Awaitable[dict]]:
    """Build the real intake node (not the Phase 01 stub).

    persist_classification=False: unit tests, no Postgres.
    persist_classification=True: write work_type / risk_tier onto the Task row.
    If MASC rejects the model JSON, run() raises and we never write Task.
    """
    engine = masc or MASCEngine()
    telemetry = sink if sink is not None else NoOpTelemetrySink()

    async def intake_node(state: SDLCState) -> dict:
        summary = await _architecture_summary(architecture_summary_loader)
        if not persist_classification:
            manager = PlanningManager(
                router=router,
                masc=engine,
                sink=telemetry,
                request_text=last_user_text(state),
                architecture_summary=summary,
            )
            updated = await manager.run(state)
            return _delta(state, updated)
        factory = session_factory or make_session_factory(get_engine())
        async with factory() as session:
            task = await get_task(session, state["task_id"])
            # Prefer the chat message; fall back to the Task title from Postgres.
            request = last_user_text(state) or (task.title if task is not None else "")
            manager = PlanningManager(
                router=router,
                masc=engine,
                sink=telemetry,
                task=task,
                # tracker writes cost_tracking rows (tokens / dollars) for this call.
                tracker=BudgetTracker(session) if task is not None else None,
                request_text=request,
                architecture_summary=summary,
            )
            updated = await manager.run(state)
            payload = _classification_payload(state, updated)
            # MASC failures raise inside run(), so we never reach this write.
            if payload is not None and task is not None:
                await update_task_classification(
                    session,
                    task.id,
                    WorkType(payload["work_type"]),
                    RiskTier(payload["risk_tier"]),
                )
            return _delta(state, updated)

    intake_node.__name__ = "intake_node"
    intake_node.__qualname__ = "build_intake_node.<locals>.intake_node"
    return intake_node


async def _architecture_summary(loader: ArchitectureSummaryLoader | None) -> str:
    # Fail-closed: if repo intel is missing/stale, tell the model that.
    # Do not invent a fake architecture so the classifier "has context".
    if loader is None:
        return UNAVAILABLE_SUMMARY
    try:
        text = (await loader()).strip()
    except Exception:
        return UNAVAILABLE_SUMMARY
    return text or UNAVAILABLE_SUMMARY


def _classification_payload(before: SDLCState, after: SDLCState) -> dict | None:
    start = len(before.get("agent_events") or [])
    for event in (after.get("agent_events") or [])[start:]:
        if event.get("event_type") == "agent_completed":
            payload = event.get("payload")
            if isinstance(payload, dict):
                return payload
    return None


def _delta(before: SDLCState, after: SDLCState) -> dict:
    """Return only *new* list items.

    `agent_events` / `validation_flags` are append_only. If we returned the
    full lists again, LangGraph would duplicate every old event.
    """
    n_events = len(before.get("agent_events") or [])
    n_flags = len(before.get("validation_flags") or [])
    return {
        "intent_version": after["intent_version"],
        "intent_last_updated": after["intent_last_updated"],
        "agent_events": (after.get("agent_events") or [])[n_events:],
        "validation_flags": (after.get("validation_flags") or [])[n_flags:],
    }
