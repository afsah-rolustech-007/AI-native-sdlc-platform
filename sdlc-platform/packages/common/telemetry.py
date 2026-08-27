"""Application telemetry contract — `final_plan.md` §B.8.3.

This module must never import OpenTelemetry. The SDK lives only in `tracing.py`.
Every method is fire-and-forget for the caller: implementations must not raise.
`span()` still re-raises the *inner* exception after recording status=error.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal, Protocol
from uuid import uuid4

SpanKind = Literal[
    "task",
    "phase",
    "manager",
    "agent",
    "llm_call",
    "tool_call",
    "validation",
    "fan_in",
    "hitl",
    "sandbox",
    "topology_selection",
    "wave_scheduler",
]


class TelemetrySink(Protocol):
    """Never raises. Never used for control flow."""

    def start_span(
        self,
        *,
        kind: SpanKind,
        name: str,
        task_id: str,
        phase: str | None = None,
        manager_id: str | None = None,
        agent_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ) -> str: ...

    def end_span(
        self,
        span_id: str,
        *,
        status: Literal["ok", "error", "cancelled"],
        error_type: str | None = None,
        error_message: str | None = None,
        attributes: dict | None = None,
    ) -> None: ...

    def emit_event(
        self,
        span_id: str,
        *,
        name: str,
        attributes: dict | None = None,
    ) -> None: ...

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        attributes: dict | None = None,
    ) -> None: ...

    @contextmanager
    def span(self, **kwargs) -> Iterator[str]: ...


class NoOpTelemetrySink:
    """Used in unit tests and when tracing is disabled."""

    def start_span(
        self,
        *,
        kind: SpanKind,
        name: str,
        task_id: str,
        phase: str | None = None,
        manager_id: str | None = None,
        agent_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ) -> str:
        return f"noop-{uuid4().hex[:8]}"

    def end_span(
        self,
        span_id: str,
        *,
        status: Literal["ok", "error", "cancelled"],
        error_type: str | None = None,
        error_message: str | None = None,
        attributes: dict | None = None,
    ) -> None:
        return None

    def emit_event(
        self,
        span_id: str,
        *,
        name: str,
        attributes: dict | None = None,
    ) -> None:
        return None

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        attributes: dict | None = None,
    ) -> None:
        return None

    @contextmanager
    def span(self, **kwargs) -> Iterator[str]:
        span_id = self.start_span(**kwargs)
        try:
            yield span_id
        except Exception as exc:
            self.end_span(
                span_id,
                status="error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        else:
            self.end_span(span_id, status="ok")


class RecordingTelemetrySink(NoOpTelemetrySink):
    """Test sink that remembers spans/events/metrics without OTel."""

    def __init__(self) -> None:
        self.started: list[dict] = []
        self.ended: list[dict] = []
        self.events: list[dict] = []
        self.metrics: list[dict] = []

    def start_span(
        self,
        *,
        kind: SpanKind,
        name: str,
        task_id: str,
        phase: str | None = None,
        manager_id: str | None = None,
        agent_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ) -> str:
        span_id = f"rec-{uuid4().hex[:8]}"
        self.started.append(
            {
                "span_id": span_id,
                "kind": kind,
                "name": name,
                "task_id": task_id,
                "phase": phase,
                "manager_id": manager_id,
                "agent_id": agent_id,
                "parent_span_id": parent_span_id,
                "attributes": attributes or {},
            }
        )
        return span_id

    def end_span(
        self,
        span_id: str,
        *,
        status: Literal["ok", "error", "cancelled"],
        error_type: str | None = None,
        error_message: str | None = None,
        attributes: dict | None = None,
    ) -> None:
        self.ended.append(
            {
                "span_id": span_id,
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "attributes": attributes or {},
            }
        )

    def emit_event(
        self,
        span_id: str,
        *,
        name: str,
        attributes: dict | None = None,
    ) -> None:
        self.events.append({"span_id": span_id, "name": name, "attributes": attributes or {}})

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        attributes: dict | None = None,
    ) -> None:
        self.metrics.append(
            {"name": name, "value": value, "unit": unit, "attributes": attributes or {}}
        )
