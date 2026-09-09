"""Save human-in-the-loop (HITL) questions to the database.

Two places hold HITL data — do not mix them up:

- `hitl_log` (Postgres): the real record. Survives a crash. The UI reads this.
- `SDLCState.hitl_queue`: a short list on the running graph only.

Unanswered rows have `responded_at IS NULL`. That is the pending inbox.

Timeouts must never write "approve". A human not answering is not a yes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.db import get_engine, make_session_factory
from common.models import ApprovalRow, HitlLogRow

# Stamp the timeout job writes. Not a human decision. Never treat as approve.
TIMEOUT_ESCALATED = "timeout_escalated"
SYSTEM_TIMEOUT_ACTOR = "system:timeout"


def utcnow() -> datetime:
    return datetime.now(UTC)


@runtime_checkable
class HitlStore(Protocol):
    """Same operations for tests (memory lists) and production (Postgres).

    insert_open = ask a human, nobody has answered yet.
    mark_responded = a human (or the timeout job) wrote an answer.
    """

    async def insert_open(self, record: dict[str, Any]) -> dict[str, Any]: ...

    async def get_open(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None: ...

    async def get_latest(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None: ...

    async def mark_responded(
        self,
        request_id: str,
        *,
        response: str,
        responded_by: str,
        responded_at: datetime | None = None,
    ) -> dict[str, Any]: ...

    async def escalate_expired(self, now: datetime | None = None) -> list[dict[str, Any]]: ...

    async def list_pending(self) -> list[dict[str, Any]]: ...

    async def record_approval(
        self,
        *,
        task_id: str,
        checkpoint: str,
        approver: str,
        decision: str,
        evidence_ref: str,
        decided_at: datetime | None = None,
    ) -> None: ...

    def approvals(self) -> list[dict[str, Any]]: ...


class MemoryHitlStore:
    """Process-local store. Used by unit tests that must not touch Postgres."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._approvals: list[dict[str, Any]] = []

    async def insert_open(self, record: dict[str, Any]) -> dict[str, Any]:
        # After resume, LangGraph re-runs this node from line 1. Reuse the
        # pending row so we do not create a second copy of the same question.
        existing = await self.get_open(
            task_id=str(record["task_id"]),
            checkpoint=str(record["checkpoint"]),
        )
        if existing is not None:
            return existing
        stored = dict(record)
        stored.setdefault("request_id", str(uuid4()))
        stored.setdefault("response", None)
        stored.setdefault("responded_by", None)
        stored.setdefault("responded_at", None)
        self.rows.append(stored)
        return stored

    async def get_open(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None:
        # Open = still waiting. responded_at stays None until a human answers.
        for row in reversed(self.rows):
            if (
                row["task_id"] == task_id
                and row["checkpoint"] == checkpoint
                and row.get("responded_at") is None
            ):
                return dict(row)
        return None

    async def get_latest(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None:
        for row in reversed(self.rows):
            if row["task_id"] == task_id and row["checkpoint"] == checkpoint:
                return dict(row)
        return None

    async def mark_responded(
        self,
        request_id: str,
        *,
        response: str,
        responded_by: str,
        responded_at: datetime | None = None,
    ) -> dict[str, Any]:
        when = responded_at or utcnow()
        for row in self.rows:
            if row["request_id"] == request_id:
                row["response"] = response
                row["responded_by"] = responded_by
                row["responded_at"] = when
                return dict(row)
        raise KeyError(request_id)

    async def escalate_expired(self, now: datetime | None = None) -> list[dict[str, Any]]:
        return _escalate_rows(self.rows, now or utcnow())

    async def list_pending(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows if row.get("responded_at") is None]

    async def record_approval(
        self,
        *,
        task_id: str,
        checkpoint: str,
        approver: str,
        decision: str,
        evidence_ref: str,
        decided_at: datetime | None = None,
    ) -> None:
        # Clock expiry is not a human. The timeout actor must never log approve.
        if _is_approve(decision) and approver == SYSTEM_TIMEOUT_ACTOR:
            raise ValueError("timeout path must never record an approve decision")
        self._approvals.append(
            {
                "task_id": task_id,
                "checkpoint": checkpoint,
                "approver": approver,
                "decision": decision,
                "evidence_ref": evidence_ref,
                "decided_at": decided_at or utcnow(),
            }
        )

    def approvals(self) -> list[dict[str, Any]]:
        return list(self._approvals)


class PostgresHitlStore:
    """Writes Phase 00 `hitl_log` / `approvals`. UI reads pending from here, not the graph."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory or make_session_factory(get_engine())

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        # sessionmaker() returns a session; `async with factory()` would be wrong.
        factory = self._factory()
        async with factory() as session:
            yield session

    async def insert_open(self, record: dict[str, Any]) -> dict[str, Any]:
        # Same as memory: one open question per (task, checkpoint).
        existing = await self.get_open(
            task_id=str(record["task_id"]),
            checkpoint=str(record["checkpoint"]),
        )
        if existing is not None:
            return existing
        request_id = UUID(str(record.get("request_id") or uuid4()))
        async with self._session() as session:
            row = HitlLogRow(
                id=request_id,
                task_id=str(record["task_id"]),
                request_type=str(record["request_type"]),
                phase=str(record.get("phase") or ""),
                reason=str(record.get("reason") or ""),
                evidence_ref=str(record.get("evidence_ref") or ""),
                options=_options_payload(record),
                timeout_at=record["timeout_at"],
            )
            session.add(row)
            await session.commit()
        loaded = await self.get_latest(
            task_id=str(record["task_id"]),
            checkpoint=str(record["checkpoint"]),
        )
        if loaded is None:
            raise RuntimeError("hitl_log row missing after insert")
        return loaded

    async def get_open(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None:
        async with self._session() as session:
            result = await session.execute(
                select(HitlLogRow)
                .where(HitlLogRow.task_id == task_id, HitlLogRow.responded_at.is_(None))
                .order_by(HitlLogRow.created_at.desc())
            )
            for row in result.scalars():
                parsed = _from_row(row)
                if parsed["checkpoint"] == checkpoint:
                    return parsed
        return None

    async def get_latest(self, *, task_id: str, checkpoint: str) -> dict[str, Any] | None:
        async with self._session() as session:
            result = await session.execute(
                select(HitlLogRow)
                .where(HitlLogRow.task_id == task_id)
                .order_by(HitlLogRow.created_at.desc())
            )
            for row in result.scalars():
                parsed = _from_row(row)
                if parsed["checkpoint"] == checkpoint:
                    return parsed
        return None

    async def mark_responded(
        self,
        request_id: str,
        *,
        response: str,
        responded_by: str,
        responded_at: datetime | None = None,
    ) -> dict[str, Any]:
        when = responded_at or utcnow()
        async with self._session() as session:
            row = await session.get(HitlLogRow, UUID(request_id))
            if row is None:
                raise KeyError(request_id)
            row.response = response
            row.responded_by = responded_by
            row.responded_at = when
            await session.commit()
            await session.refresh(row)
            return _from_row(row)

    async def escalate_expired(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Human never answered in time: hold the task. Do not auto-approve.

        Does not resume LangGraph. The graph stays paused until a person acts.
        """
        deadline = now or utcnow()
        escalated: list[dict[str, Any]] = []
        async with self._session() as session:
            result = await session.execute(
                select(HitlLogRow).where(
                    HitlLogRow.responded_at.is_(None),
                    HitlLogRow.timeout_at <= deadline,
                )
            )
            for row in result.scalars():
                if _is_approve(row.response):
                    continue
                if row.response == TIMEOUT_ESCALATED:
                    continue
                row.response = TIMEOUT_ESCALATED
                row.responded_by = SYSTEM_TIMEOUT_ACTOR
                # Keep responded_at NULL so the inbox still shows this as held,
                # not as a finished approval.
                escalated.append(_from_row(row))
            await session.commit()
        return escalated

    async def list_pending(self) -> list[dict[str, Any]]:
        # UI inbox: unanswered rows. Do not read SDLCState.hitl_queue for this.
        async with self._session() as session:
            result = await session.execute(
                select(HitlLogRow)
                .where(HitlLogRow.responded_at.is_(None))
                .order_by(HitlLogRow.created_at.asc())
            )
            return [_from_row(row) for row in result.scalars()]

    async def record_approval(
        self,
        *,
        task_id: str,
        checkpoint: str,
        approver: str,
        decision: str,
        evidence_ref: str,
        decided_at: datetime | None = None,
    ) -> None:
        if approver == SYSTEM_TIMEOUT_ACTOR and _is_approve(decision):
            raise ValueError("timeout path must never record an approve decision")
        when = decided_at or utcnow()
        async with self._session() as session:
            session.add(
                ApprovalRow(
                    task_id=task_id,
                    checkpoint=checkpoint,
                    approver=approver,
                    decision=decision,
                    evidence_ref=evidence_ref,
                    decided_at=when,
                )
            )
            await session.commit()

    def approvals(self) -> list[dict[str, Any]]:
        return []


def _is_approve(value: str | None) -> bool:
    return (value or "").strip().lower() in {"approve", "approved"}


def _escalate_rows(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """In-memory timeout: stamp hold, never approve, do not set responded_at."""
    escalated: list[dict[str, Any]] = []
    for row in rows:
        timeout_at = row.get("timeout_at")
        if row.get("responded_at") is not None or timeout_at is None:
            continue
        if timeout_at > now:
            continue
        if _is_approve(row.get("response")):
            continue
        if row.get("response") == TIMEOUT_ESCALATED:
            continue
        row["response"] = TIMEOUT_ESCALATED
        row["responded_by"] = SYSTEM_TIMEOUT_ACTOR
        escalated.append(dict(row))
    return escalated


def _options_payload(record: dict[str, Any]) -> dict[str, Any]:
    # hitl_log.options is JSONB (a dict). There is no checkpoint column, so
    # we store the checkpoint name next to the button labels.
    return {
        "choices": list(record.get("options") or []),
        "checkpoint": record["checkpoint"],
    }


def _from_row(row: HitlLogRow) -> dict[str, Any]:
    # Turn a SQLAlchemy row into the plain dict the rest of the code uses.
    options = row.options or {}
    choices = options.get("choices") if isinstance(options, dict) else None
    checkpoint = options.get("checkpoint") if isinstance(options, dict) else None
    return {
        "request_id": str(row.id),
        "task_id": row.task_id or "",
        "request_type": row.request_type,
        "phase": row.phase or "",
        "reason": row.reason or "",
        "evidence_ref": row.evidence_ref or "",
        "options": list(choices or []),
        "checkpoint": str(checkpoint or ""),
        "timeout_at": row.timeout_at,
        "response": row.response,
        "responded_by": row.responded_by,
        "responded_at": row.responded_at,
    }


async def list_pending_hitl(store: HitlStore | None = None) -> list[dict[str, Any]]:
    """Pending inbox: unanswered Postgres rows, not the in-graph queue."""
    active = store if store is not None else PostgresHitlStore()
    return await active.list_pending()
