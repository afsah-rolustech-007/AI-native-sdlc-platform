"""Background job: HITL questions that nobody answered in time.

Runs in the ARQ worker, not inside the graph. That is on purpose:

- LangGraph interrupt() has no wall-clock timer.
- If we resumed with "approve" from here, silence would become a yes.

This job only stamps the row as timed out / held. A human still has to resume.
"""

from __future__ import annotations

from datetime import UTC, datetime

from orchestration.hitl_store import TIMEOUT_ESCALATED, PostgresHitlStore


async def escalate_expired_hitl(ctx: dict) -> dict:
    """Mark expired `hitl_log` rows. Never Command(resume="approve")."""
    store = PostgresHitlStore()
    rows = await store.escalate_expired(datetime.now(UTC))
    sink = ctx.get("sink")
    for row in rows:
        # Belt-and-suspenders: escalate_expired must never produce approve.
        if (row.get("response") or "") == "approve":
            raise RuntimeError("timeout job attempted to approve; refusing")
        if sink is not None:
            try:
                sink.emit_event(
                    "hitl-timeout",
                    name="hitl_timeout_escalated",
                    attributes={
                        "task_id": row.get("task_id"),
                        "request_id": row.get("request_id"),
                        "checkpoint": row.get("checkpoint"),
                        "response": TIMEOUT_ESCALATED,
                    },
                )
            except Exception:
                pass
    return {
        "escalated": len(rows),
        "approved": 0,
        "request_ids": [row["request_id"] for row in rows],
    }
