"""OTel adapter tests. Production code besides tracing.py must not import OTel."""

from pathlib import Path

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from common.sandbox import run_in_sandbox
from common.telemetry import RecordingTelemetrySink
from common.tracing import OtelTelemetrySink, emit_node_event, reset_sink


def test_opentelemetry_imports_only_allowed_in_tracing() -> None:
    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for folder in ("packages", "apps"):
        for path in (root / folder).rglob("*.py"):
            if path.name == "tracing.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "opentelemetry" in text:
                offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_otel_sink_sets_mvp_attributes() -> None:
    exporter = InMemorySpanExporter()
    sink = OtelTelemetrySink(exporter=exporter, console=False)
    with sink.span(kind="sandbox", name="demo", task_id="task-otel-1", phase="intake"):
        pass
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = dict(spans[0].attributes or {})
    assert attrs["task_id"] == "task-otel-1"
    assert attrs["kind"] == "sandbox"
    assert "trace_id" in attrs
    assert "span_id" in attrs


def test_emit_node_event_uses_original_field_list() -> None:
    sink = RecordingTelemetrySink()
    emit_node_event(
        sink,
        task_id="task-evt",
        node_id="sandbox",
        agent_id="sbx",
        phase="intake",
        model_id=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        latency_ms=3,
        validation_result=None,
    )
    assert sink.started[0]["kind"] == "sandbox"
    assert sink.started[0]["attributes"]["latency_ms"] == 3


def test_exporter_failure_does_not_fail_sandbox(monkeypatch) -> None:
    class BoomExporter(SpanExporter):
        def export(self, spans):
            raise RuntimeError("exporter down")

        def shutdown(self, timeout_millis: int = 30000) -> SpanExportResult:
            return SpanExportResult.SUCCESS

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    sink = OtelTelemetrySink(exporter=BoomExporter(), console=False)

    def fake_run(task_id, command, timeout_s, network):
        from common.sandbox import SandboxResult

        return SandboxResult(stdout="hello\n", stderr="", exit_code=0, duration_ms=1, timed_out=False)

    monkeypatch.setattr("common.sandbox._run_container", fake_run)
    reset_sink()
    result = run_in_sandbox("task-boom", ["echo", "hello"], timeout_s=5, sink=sink)
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    reset_sink()
