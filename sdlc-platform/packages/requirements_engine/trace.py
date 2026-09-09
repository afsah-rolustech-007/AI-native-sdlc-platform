"""Append-only session trace for Screen 2 / Phase 15 labels. No LLM. No RI."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from requirements_engine.models import SessionEventKind

OutcomeName = Literal["spec_ready", "accept_gaps", "needs_hitl"]


class SessionCounters(BaseModel):
    """Benchmark counters. Structured, not print-based."""

    llm_calls: int = 0
    ri_calls: int = 0
    ri_cache_hits: int = 0
    snapshot_cache_hits: int = 0
    human_questions: int = 0
    auto_answers: int = 0
    semantic_calls: int = 0
    session_budget_consumed: int = 0
    final_outcome: OutcomeName | None = None


class TraceEvent(BaseModel):
    """One append-only record. Payloads stay compact (ids, hashes, counts)."""

    seq: int
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionTrace(BaseModel):
    """Deterministic audit log of one requirements-engine session."""

    events: list[TraceEvent] = Field(default_factory=list)
    counters: SessionCounters = Field(default_factory=SessionCounters)

    def append(self, kind: SessionEventKind | str, **payload: Any) -> TraceEvent:
        label = kind.value if isinstance(kind, SessionEventKind) else kind
        compact = {key: value for key, value in payload.items() if value is not None}
        event = TraceEvent(seq=len(self.events) + 1, kind=label, payload=compact)
        self.events.append(event)
        return event

    def kinds(self) -> list[str]:
        return [event.kind for event in self.events]

    def of_kind(self, kind: SessionEventKind | str) -> list[TraceEvent]:
        label = kind.value if isinstance(kind, SessionEventKind) else kind
        return [event for event in self.events if event.kind == label]

    def dump(self) -> dict[str, Any]:
        return {
            "counters": self.counters.model_dump(),
            "events": [event.model_dump() for event in self.events],
        }
