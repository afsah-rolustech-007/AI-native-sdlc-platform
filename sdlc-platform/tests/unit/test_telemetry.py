"""TelemetrySink contract tests — no OpenTelemetry."""

from pathlib import Path

import pytest

from common.telemetry import NoOpTelemetrySink, RecordingTelemetrySink


def test_telemetry_py_does_not_import_opentelemetry() -> None:
    path = Path(__file__).resolve().parents[2] / "packages" / "common" / "telemetry.py"
    text = path.read_text(encoding="utf-8")
    assert "opentelemetry" not in text


def test_recording_sink_captures_required_span_fields() -> None:
    sink = RecordingTelemetrySink()
    span_id = sink.start_span(
        kind="sandbox",
        name="run_in_sandbox",
        task_id="task-tel-1",
        phase="intake",
        attributes={"input_tokens": 0, "output_tokens": 0, "cost_usd": 0},
    )
    sink.end_span(span_id, status="ok", attributes={"latency_ms": 12})
    assert sink.started[0]["task_id"] == "task-tel-1"
    assert sink.started[0]["kind"] == "sandbox"
    assert sink.started[0]["attributes"]["input_tokens"] == 0
    assert sink.ended[0]["status"] == "ok"


def test_span_context_manager_records_error_and_reraises() -> None:
    sink = RecordingTelemetrySink()
    with pytest.raises(RuntimeError, match="boom"), sink.span(kind="agent", name="x", task_id="t"):
        raise RuntimeError("boom")
    assert sink.ended[0]["status"] == "error"
    assert sink.ended[0]["error_type"] == "RuntimeError"


def test_noop_methods_do_not_raise() -> None:
    sink = NoOpTelemetrySink()
    span_id = sink.start_span(kind="task", name="t", task_id="t1")
    sink.end_span(span_id, status="ok")
    sink.emit_event(span_id, name="noop")
    sink.record_metric("tokens", 1.0, unit="count")
