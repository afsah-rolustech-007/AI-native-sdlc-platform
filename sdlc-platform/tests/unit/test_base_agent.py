"""BaseAgent: router + MASC + retry + TelemetrySink spans. No OpenTelemetry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel
from tests.contract.fakes import FakeAdapter
from tests.factories import make_task

from agents.base import BaseAgent
from common.task import TaskBudget
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import ChatMessage, ModelRequest, ModelResponse, TokenUsage
from model_adapters.circuit_breaker import ProviderUnavailable
from model_adapters.router import ModelRouter
from orchestration.masc import MASCEngine, MASCValidationError
from orchestration.state import SDLCState, initial_sdlc_state


class EchoOutput(BaseModel):
    echo: str
    confidence: float


class ScriptedAdapter(FakeAdapter):
    """Returns JSON bodies in order. Used to drive MASC pass/fail and retries."""

    def __init__(self, bodies: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._bodies = list(bodies)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self._maybe_fail()
        text = self._bodies.pop(0) if self._bodies else "{}"
        return ModelResponse(
            content=text,
            usage=TokenUsage(input_tokens=10, output_tokens=2),
            model_id=self._mid(),
            finish_reason="stop",
        )


class EchoAgent(BaseAgent):
    agent_id = "echo"
    phase = "requirements"
    operation = "summarization"

    @property
    def output_schema(self) -> type[BaseModel]:
        return EchoOutput

    def build_context(self, state: SDLCState) -> list[ChatMessage]:
        return [ChatMessage(role="user", content="echo")]


def _payload(echo: str, confidence: float) -> str:
    return json.dumps({"echo": echo, "confidence": confidence})


def _agent(
    body: str | list[str],
    *,
    fail_times: int = 0,
    max_retries: int = 0,
    sink: RecordingTelemetrySink | None = None,
    task=None,
    sleep=None,
) -> tuple[EchoAgent, RecordingTelemetrySink, ScriptedAdapter]:
    bodies = [body] if isinstance(body, str) else body
    adapter = ScriptedAdapter(
        bodies,
        model_id="fake-small",
        capability_score=6,
        fail_times=fail_times,
    )
    recording = sink or RecordingTelemetrySink()
    agent = EchoAgent(
        router=ModelRouter([adapter]),
        masc=MASCEngine(),
        sink=recording,
        task=task,
        max_retries=max_retries,
        sleep=sleep,
        backoff_base_s=0.01,
    )
    return agent, recording, adapter


async def _noop_sleep(_delay: float) -> None:
    return None


async def test_valid_output_passes_masc_and_enters_state() -> None:
    agent, sink, _adapter = _agent(_payload("hello", 0.9))
    state = initial_sdlc_state(make_task(id="task-echo-ok"))
    result = await agent.run(state)
    events = [
        event
        for event in result["agent_events"]
        if event["event_type"] == "agent_completed"
    ]
    assert events[0]["payload"]["echo"] == "hello"
    assert result["validation_flags"] == []
    kinds = [span["kind"] for span in sink.started]
    assert kinds == ["agent", "llm_call", "validation"]
    agent_span = sink.started[0]
    assert agent_span["attributes"]["attempt_number"] == 1
    llm = sink.started[1]
    assert llm["parent_span_id"] == agent_span["span_id"]
    assert llm["attributes"]["model_id"] == "fake-small"
    llm_end = next(item for item in sink.ended if item["span_id"] == llm["span_id"])
    assert llm_end["attributes"]["input_tokens"] == 10
    assert llm_end["attributes"]["output_tokens"] == 2
    validation = sink.started[2]
    assert validation["parent_span_id"] == agent_span["span_id"]
    assert {item["status"] for item in sink.ended} == {"ok"}


async def test_low_confidence_is_rejected_before_state_write() -> None:
    agent, sink, _adapter = _agent(_payload("hello", 0.5))
    state = initial_sdlc_state(make_task(id="task-echo-low"))
    with pytest.raises(MASCValidationError) as exc:
        await agent.run(state)
    assert exc.value.flag["flag_type"] == "confidence_below_threshold"
    assert exc.value.state is not None
    assert exc.value.state["validation_flags"][0]["flag_type"] == "confidence_below_threshold"
    assert not any(
        event["event_type"] == "agent_completed" for event in exc.value.state["agent_events"]
    )
    validation_ids = {span["span_id"] for span in sink.started if span["kind"] == "validation"}
    validation_status = [
        item["status"] for item in sink.ended if item["span_id"] in validation_ids
    ]
    assert validation_status == ["error"]


async def test_schema_violation_is_rejected_before_state_write() -> None:
    agent, _sink, _adapter = _agent(json.dumps({"echo": "hello"}))
    state = initial_sdlc_state(make_task(id="task-echo-schema"))
    with pytest.raises(MASCValidationError) as exc:
        await agent.run(state)
    assert exc.value.flag["flag_type"] == "schema_violation"
    assert exc.value.retryable is True
    assert exc.value.state is not None
    assert not any(
        event["event_type"] == "agent_completed" for event in exc.value.state["agent_events"]
    )


async def test_schema_violation_retries_then_succeeds() -> None:
    agent, sink, adapter = _agent(
        [json.dumps({"echo": "bad"}), _payload("ok", 0.9)],
        max_retries=1,
    )
    state = initial_sdlc_state(make_task(id="task-echo-retry-schema"))
    result = await agent.run(state)
    assert adapter.calls == 2
    assert result["agent_events"][-1]["payload"]["echo"] == "ok"
    attempts = [
        span["attributes"]["attempt_number"]
        for span in sink.started
        if span["kind"] == "agent"
    ]
    assert attempts == [1, 2]


async def test_transient_model_error_retries_with_backoff() -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    agent, sink, adapter = _agent(
        _payload("ok", 0.9),
        fail_times=2,
        max_retries=2,
        sleep=record_sleep,
    )
    result = await agent.run(initial_sdlc_state(make_task(id="task-echo-retry")))
    assert adapter.calls == 3
    assert result["agent_events"][-1]["payload"]["echo"] == "ok"
    assert sleeps == [0.01, 0.02]
    attempts = [
        span["attributes"]["attempt_number"]
        for span in sink.started
        if span["kind"] == "agent"
    ]
    assert attempts == [1, 2, 3]


async def test_max_retries_comes_from_task_budget() -> None:
    task = make_task(id="task-echo-budget", budget=TaskBudget(max_retries_per_node=1))
    adapter = ScriptedAdapter(
        [_payload("ok", 0.9)],
        fail_times=2,
        capability_score=6,
    )
    agent = EchoAgent(
        router=ModelRouter([adapter]),
        masc=MASCEngine(),
        sink=RecordingTelemetrySink(),
        task=task,
        backoff_base_s=0.0,
        sleep=_noop_sleep,
    )
    with pytest.raises(RuntimeError, match="simulated provider error"):
        await agent.run(initial_sdlc_state(task))
    assert adapter.calls == 2


async def test_provider_unavailable_does_not_retry() -> None:
    class OpenCircuit(FakeAdapter):
        def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls += 1
            raise ProviderUnavailable("glm")

    adapter = OpenCircuit(capability_score=6)
    agent = EchoAgent(
        router=ModelRouter([adapter]),
        masc=MASCEngine(),
        sink=RecordingTelemetrySink(),
        max_retries=3,
        sleep=_noop_sleep,
    )
    with pytest.raises(ProviderUnavailable):
        await agent.run(initial_sdlc_state(make_task(id="task-echo-circuit")))
    assert adapter.calls == 1


async def test_low_confidence_is_not_retried() -> None:
    agent, _sink, adapter = _agent(_payload("hello", 0.1), max_retries=3)
    with pytest.raises(MASCValidationError) as exc:
        await agent.run(initial_sdlc_state(make_task(id="task-echo-no-retry")))
    assert exc.value.flag["flag_type"] == "confidence_below_threshold"
    assert adapter.calls == 1


def test_tool_span_records_tool_call_kind() -> None:
    agent, sink, _adapter = _agent(_payload("hello", 0.9))
    with agent.tool_span("lookup", task_id="task-tool", parent_span_id="agent-1"):
        pass
    assert sink.started[0]["kind"] == "tool_call"
    assert sink.started[0]["name"] == "lookup"
    assert sink.started[0]["parent_span_id"] == "agent-1"


def test_agents_package_has_no_opentelemetry_import() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "agents"
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "opentelemetry" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
