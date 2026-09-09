"""Planning Manager classification + MASC Check 1 on bad output."""

from __future__ import annotations

import json

import pytest
from tests.contract.fakes import FakeAdapter
from tests.factories import make_task

from agents.intake.node import build_intake_node
from agents.intake.planning_manager import UNAVAILABLE_SUMMARY, PlanningManager
from agents.prompts.planning_manager import SYSTEM_PROMPT
from common.task import RiskTier, WorkType
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import ModelRequest, ModelResponse, TokenUsage
from model_adapters.router import ModelRouter
from orchestration.masc import MASCEngine, MASCValidationError
from orchestration.state import initial_sdlc_state


class ScriptedAdapter(FakeAdapter):
    def __init__(self, bodies: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._bodies = list(bodies)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.requests.append(request)
        text = self._bodies.pop(0) if self._bodies else "{}"
        return ModelResponse(
            content=text,
            usage=TokenUsage(input_tokens=12, output_tokens=8),
            model_id=self._mid(),
            finish_reason="stop",
        )


def _body(
    work_type: str,
    risk_tier: str = "medium",
    rationale: str = "matches the request",
    confidence: float = 0.9,
) -> str:
    return json.dumps(
        {
            "work_type": work_type,
            "risk_tier": risk_tier,
            "rationale": rationale,
            "confidence": confidence,
        }
    )


def _manager(body: str | list[str], **kwargs) -> tuple[PlanningManager, ScriptedAdapter]:
    bodies = [body] if isinstance(body, str) else body
    adapter = ScriptedAdapter(bodies, capability_score=6)
    manager = PlanningManager(
        router=ModelRouter([adapter]),
        masc=MASCEngine(),
        sink=RecordingTelemetrySink(),
        request_text=kwargs.get("request_text", "Add SSO to the existing app"),
        architecture_summary=kwargs.get("architecture_summary", '{"services":["auth"]}'),
        max_retries=kwargs.get("max_retries", 0),
    )
    return manager, adapter


@pytest.mark.parametrize(
    ("work_type", "request_text"),
    [
        (WorkType.NEW_PROJECT, "Greenfield billing service from scratch"),
        (WorkType.FEATURE, "Add SSO login for existing users"),
        (WorkType.BUG, "Login returns 500 for expired sessions"),
        (WorkType.HOTFIX, "Production auth is down, need a hotfix now"),
        (WorkType.REFACTOR, "Refactor the invoice module without behavior change"),
        (WorkType.MIGRATION, "Migrate users from MySQL to Postgres"),
        (WorkType.TECH_DEBT, "Pay down auth tech debt in the token helper"),
        (WorkType.MAINTENANCE, "Bump dependency versions this sprint"),
    ],
)
async def test_each_work_type_is_accepted(work_type: WorkType, request_text: str) -> None:
    manager, _adapter = _manager(_body(work_type.value), request_text=request_text)
    result = await manager.run(initial_sdlc_state(make_task(id=f"task-{work_type.value}")))
    payload = result["agent_events"][-1]["payload"]
    assert payload["work_type"] == work_type.value
    assert result["intent_version"] == 1


async def test_missing_field_is_caught_by_masc_check1() -> None:
    manager, adapter = _manager(
        json.dumps({"work_type": "feature", "risk_tier": "low", "rationale": "x"})
    )
    with pytest.raises(MASCValidationError) as exc:
        await manager.run(initial_sdlc_state(make_task(id="task-pm-schema")))
    assert exc.value.flag["flag_type"] == "schema_violation"
    assert adapter.calls == 1
    assert not any(
        event["event_type"] == "agent_completed" for event in exc.value.state["agent_events"]
    )


async def test_invalid_work_type_is_caught_by_masc_check1() -> None:
    manager, _adapter = _manager(_body("not_a_work_type"))
    with pytest.raises(MASCValidationError) as exc:
        await manager.run(initial_sdlc_state(make_task(id="task-pm-bad-type")))
    assert exc.value.flag["flag_type"] == "schema_violation"


async def test_confidence_below_intake_floor_is_rejected() -> None:
    manager, adapter = _manager(_body("feature", confidence=0.79))
    with pytest.raises(MASCValidationError) as exc:
        await manager.run(initial_sdlc_state(make_task(id="task-pm-low-conf")))
    assert exc.value.flag["flag_type"] == "confidence_below_threshold"
    assert adapter.calls == 1


async def test_build_context_injects_request_and_architecture_summary() -> None:
    manager, adapter = _manager(_body("feature"), request_text="Add SSO")
    await manager.run(initial_sdlc_state(make_task(id="task-pm-context")))
    messages = adapter.requests[0].messages
    assert messages[0].role == "system"
    assert "[ROLE]" in (messages[0].content or "")
    assert "Planning Manager" in (messages[0].content or "")
    assert "Add SSO" in (messages[1].content or "")
    assert "auth" in (messages[2].content or "")


async def test_unavailable_summary_is_injected_explicitly() -> None:
    manager, adapter = _manager(_body("bug"), architecture_summary="  ")
    await manager.run(initial_sdlc_state(make_task(id="task-pm-no-ri")))
    assert UNAVAILABLE_SUMMARY in (adapter.requests[0].messages[2].content or "")
    assert "[ROLE]" in SYSTEM_PROMPT


async def test_judgment_examples_keep_canned_assignments() -> None:
    """Eyeball these in the demo; here we only prove the pipeline stores them.

    feature / bug / hotfix language is classified by the scripted model output,
    not by a live LLM (CI has no GLM key).
    """
    cases = [
        ("Add a new billing export CSV for finance", "feature", "medium"),
        ("Users cannot reset passwords — 500 on submit", "bug", "high"),
        ("Prod payments are failing, hotfix the charge path", "hotfix", "critical"),
    ]
    for request, work_type, risk in cases:
        manager, _adapter = _manager(_body(work_type, risk), request_text=request)
        result = await manager.run(initial_sdlc_state(make_task(id=f"task-judge-{work_type}")))
        payload = result["agent_events"][-1]["payload"]
        assert payload["work_type"] == work_type
        assert payload["risk_tier"] == risk
        assert RiskTier(payload["risk_tier"])


async def test_intake_node_writes_partial_state_without_postgres() -> None:
    adapter = ScriptedAdapter([_body("feature")], capability_score=6)
    node = build_intake_node(
        router=ModelRouter([adapter]),
        persist_classification=False,
        sink=RecordingTelemetrySink(),
        architecture_summary_loader=_async_summary,
    )
    state = initial_sdlc_state(make_task(id="task-intake-node"))
    state["messages"] = [{"role": "user", "content": "Add SSO login for existing users"}]
    updates = await node(state)
    assert updates["intent_version"] == 1
    assert updates["agent_events"][-1]["payload"]["work_type"] == "feature"
    assert updates["validation_flags"] == []


async def _async_summary() -> str:
    return '{"services":["auth"]}'
