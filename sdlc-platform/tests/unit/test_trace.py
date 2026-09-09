"""Append-only session trace."""

from __future__ import annotations

from requirements_engine.models import SessionEventKind
from requirements_engine.trace import SessionTrace


def test_trace_is_append_only_and_structured() -> None:
    trace = SessionTrace()
    trace.append(SessionEventKind.START, request="add export")
    trace.append(SessionEventKind.EXTRACT, claim_count=1)
    trace.counters.llm_calls = 1
    dumped = trace.dump()
    assert dumped["events"][0]["seq"] == 1
    assert dumped["events"][1]["kind"] == "extract"
    assert dumped["counters"]["llm_calls"] == 1
    assert trace.kinds() == ["start", "extract"]
    assert len(trace.of_kind(SessionEventKind.EXTRACT)) == 1
