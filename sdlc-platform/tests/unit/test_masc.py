"""MASC Checks 1 and 2, plus Fail-Closed when validate() itself throws."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from tests.factories import make_task

from orchestration.masc import CONFIDENCE_THRESHOLDS, MASCEngine
from orchestration.state import initial_sdlc_state


class EchoOutput(BaseModel):
    echo: str
    confidence: float


def _engine() -> MASCEngine:
    return MASCEngine({"echo": EchoOutput})


def _state():
    return initial_sdlc_state(make_task(id="task-masc-1"))


def test_check1_rejects_missing_required_field() -> None:
    ok, flag = _engine().validate({"confidence": 0.9}, "echo", "requirements", _state())
    assert ok is False
    assert flag is not None
    assert flag["flag_type"] == "schema_violation"
    assert flag["severity"] == "error"
    assert flag["source"] == "masc"


def test_check1_rejects_unknown_agent_schema() -> None:
    ok, flag = _engine().validate(
        {"echo": "hi", "confidence": 0.9}, "not-registered", "requirements", _state()
    )
    assert ok is False
    assert flag is not None
    assert flag["flag_type"] == "schema_violation"


def test_check1_accepts_valid_schema() -> None:
    ok, flag = _engine().validate(
        {"echo": "hi", "confidence": 0.9}, "echo", "requirements", _state()
    )
    assert ok is True
    assert flag is None


def test_check2_rejects_confidence_below_phase_floor() -> None:
    floor = CONFIDENCE_THRESHOLDS["requirements"]
    ok, flag = _engine().validate(
        {"echo": "hi", "confidence": floor - 0.01}, "echo", "requirements", _state()
    )
    assert ok is False
    assert flag is not None
    assert flag["flag_type"] == "confidence_below_threshold"
    assert flag["severity"] == "warning"
    assert str(floor) in flag["detail"]


def test_check2_accepts_confidence_at_floor() -> None:
    ok, flag = _engine().validate(
        {"echo": "hi", "confidence": CONFIDENCE_THRESHOLDS["requirements"]},
        "echo",
        "requirements",
        _state(),
    )
    assert ok is True
    assert flag is None


def test_check2_unknown_phase_uses_requirements_floor() -> None:
    ok, flag = _engine().validate(
        {"echo": "hi", "confidence": 0.79}, "echo", "intake", _state()
    )
    assert ok is False
    assert flag is not None
    assert flag["flag_type"] == "confidence_below_threshold"


def test_check3_stub_does_not_fail_high_stakes_phase() -> None:
    engine = _engine()
    assert engine.check_semantic_drift({}, None, 0) == "not checked"
    ok, flag = engine.validate(
        {"echo": "hi", "confidence": 0.9}, "echo", "design", _state()
    )
    assert ok is True
    assert flag is None


def test_masc_internal_exception_is_error_not_pass() -> None:
    engine = _engine()

    def boom(output: dict, agent_id: str) -> bool:
        raise RuntimeError("checker crashed")

    engine._validate_schema = boom  # type: ignore[method-assign]
    ok, flag = engine.validate(
        {"echo": "hi", "confidence": 0.9}, "echo", "requirements", _state()
    )
    assert ok is False
    assert flag is not None
    assert flag["severity"] == "error"
    assert flag["flag_type"] == "tool_error"
    assert "MASC internal error" in flag["detail"]
    assert "checker crashed" in flag["detail"]


def test_orchestration_masc_has_no_opentelemetry_import() -> None:
    text = Path(__file__).resolve().parents[2].joinpath(
        "packages", "orchestration", "masc.py"
    ).read_text(encoding="utf-8")
    assert "opentelemetry" not in text
