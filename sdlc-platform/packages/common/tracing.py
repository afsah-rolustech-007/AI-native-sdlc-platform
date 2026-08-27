"""OpenTelemetry adapter for `TelemetrySink`. The only Phase 00 OTel import site."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal
from uuid import uuid4

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Status, StatusCode

from common.config import get_settings
from common.telemetry import NoOpTelemetrySink, SpanKind, TelemetrySink

_sink: TelemetrySink | None = None
_logging_configured = False


def get_logger() -> structlog.stdlib.BoundLogger:
    _configure_structlog()
    return structlog.get_logger("sdlc")


def get_sink() -> TelemetrySink:
    """Process-wide sink. Never raises — falls back to no-op."""
    global _sink
    if _sink is not None:
        return _sink
    try:
        _sink = OtelTelemetrySink()
    except Exception:
        _sink = NoOpTelemetrySink()
    return _sink


def reset_sink() -> None:
    global _sink
    _sink = None


def _configure_structlog() -> None:
    global _logging_configured
    if _logging_configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    _logging_configured = True


def emit_node_event(
    sink: TelemetrySink,
    *,
    task_id: str,
    node_id: str,
    agent_id: str | None,
    phase: str | None,
    model_id: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    latency_ms: int | None,
    validation_result: str | None,
) -> None:
    """Compatibility helper. Do not add parameters — put new data on span attributes."""
    kind: SpanKind = "sandbox" if node_id == "sandbox" else "agent"
    with sink.span(
        kind=kind,
        name=node_id,
        task_id=task_id,
        phase=phase,
        agent_id=agent_id,
        attributes={
            "model_id": model_id,
            "input_tokens": input_tokens if input_tokens is not None else 0,
            "output_tokens": output_tokens if output_tokens is not None else 0,
            "cost_usd": cost_usd if cost_usd is not None else 0,
            "latency_ms": latency_ms if latency_ms is not None else 0,
            "validation_result": validation_result,
        },
    ):
        pass


class OtelTelemetrySink:
    """TelemetrySink backed by the OpenTelemetry SDK. Every public method swallows errors."""

    def __init__(
        self,
        *,
        exporter: SpanExporter | None = None,
        console: bool | None = None,
    ) -> None:
        _configure_structlog()
        settings = get_settings()
        resource = Resource.create({"service.name": "sdlc-platform"})
        provider = TracerProvider(resource=resource)
        if exporter is not None:
            provider.add_span_processor(SimpleSpanProcessor(exporter))
        else:
            use_console = settings.environment != "test" if console is None else console
            if use_console:
                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            otlp = (settings.otlp_endpoint or "").strip()
            if otlp:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp))
                )
        self._tracer = trace.get_tracer("sdlc-platform", tracer_provider=provider)
        self._spans: dict[str, trace.Span] = {}

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
        try:
            otel_span = self._tracer.start_span(name)
            ctx = otel_span.get_span_context()
            span_id = format(ctx.span_id, "016x")
            trace_id = format(ctx.trace_id, "032x")
            attrs = {
                "task_id": task_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "kind": kind,
            }
            if parent_span_id:
                attrs["parent_span_id"] = parent_span_id
            if phase:
                attrs["phase"] = phase
            if manager_id:
                attrs["manager_id"] = manager_id
            if agent_id:
                attrs["agent_id"] = agent_id
            if attributes:
                attrs.update({k: v for k, v in attributes.items() if v is not None})
            otel_span.set_attributes(_otel_values(attrs))
            self._spans[span_id] = otel_span
            structlog.contextvars.bind_contextvars(task_id=task_id, trace_id=trace_id)
            get_logger().info("span_started", span_id=span_id, kind=kind, name=name)
            return span_id
        except Exception:
            return f"error-{uuid4().hex[:8]}"

    def end_span(
        self,
        span_id: str,
        *,
        status: Literal["ok", "error", "cancelled"],
        error_type: str | None = None,
        error_message: str | None = None,
        attributes: dict | None = None,
    ) -> None:
        try:
            otel_span = self._spans.pop(span_id, None)
            if otel_span is None:
                return
            if attributes:
                otel_span.set_attributes(_otel_values(attributes))
            if status == "ok":
                otel_span.set_status(Status(StatusCode.OK))
            else:
                otel_span.set_status(
                    Status(StatusCode.ERROR, error_message or status)
                )
                if error_type:
                    otel_span.set_attribute("error_type", error_type)
            otel_span.end()
        except Exception:
            return

    def emit_event(
        self,
        span_id: str,
        *,
        name: str,
        attributes: dict | None = None,
    ) -> None:
        try:
            otel_span = self._spans.get(span_id)
            if otel_span is None:
                return
            otel_span.add_event(name, attributes=_otel_values(attributes or {}))
        except Exception:
            return

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        attributes: dict | None = None,
    ) -> None:
        # Prometheus mapping is Phase 15. Keep the call so agents can emit now.
        try:
            get_logger().info("metric", name=name, value=value, unit=unit, **(attributes or {}))
        except Exception:
            return

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


def _otel_values(values: dict) -> dict:
    """OTel attributes must be primitives; stringify the rest."""
    out: dict = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, (bool, int, float, str)):
            out[key] = value
        else:
            out[key] = str(value)
    return out
