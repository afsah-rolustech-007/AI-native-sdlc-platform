"""Phase 01 orchestration must not import OpenTelemetry (only tracing.py may)."""

from pathlib import Path


def test_orchestration_has_no_opentelemetry_import() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "orchestration"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "opentelemetry" in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
