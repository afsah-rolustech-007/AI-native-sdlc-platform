"""Repo-blind extract via ModelAdapter. Fake adapter only — no live GLM."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from model_adapters.base import (
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSpec,
    Vector,
)
from requirements_engine.claims import ClaimKind, EpistemicStatus
from requirements_engine.extract import EXTRACT_CLAIMS_TOOL, extract_claims


class RecordingAdapter:
    def __init__(
        self,
        *,
        arguments: dict | None = None,
        fail_times: int = 0,
        bad_payloads: list[dict] | None = None,
        raise_runtime: bool = False,
        content: str | None = None,
    ) -> None:
        self.requests: list[ModelRequest] = []
        self._arguments = arguments
        self._fail_times = fail_times
        self._bad_payloads = list(bad_payloads or [])
        self._raise_runtime = raise_runtime
        self._content = content
        self._pricing = ModelPricing(
            input_price_per_1m=0.0,
            output_price_per_1m=0.0,
            provider="test",
            model_id="fake-extract",
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        raise AssertionError("extract must use call_tools, not complete")

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        raise AssertionError("extract must not stream")

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        self.requests.append(request)
        assert [tool.name for tool in tools] == [EXTRACT_CLAIMS_TOOL.name]
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("provider down")
        if self._raise_runtime:
            raise RuntimeError("provider down")
        if self._bad_payloads:
            payload = self._bad_payloads.pop(0)
            return ModelResponse(
                content=self._content,
                tool_calls=[ToolCall(id="t1", name="extract_claims", arguments=payload)],
                model_id="fake-extract",
                finish_reason="tool_calls",
            )
        if self._content is not None and self._arguments is None:
            return ModelResponse(
                content=self._content,
                model_id="fake-extract",
                finish_reason="stop",
            )
        assert self._arguments is not None
        return ModelResponse(
            tool_calls=[ToolCall(id="t1", name="extract_claims", arguments=self._arguments)],
            model_id="fake-extract",
            finish_reason="tool_calls",
        )

    def embed(self, texts: list[str]) -> list[Vector]:
        raise AssertionError("extract must not embed")

    @property
    def pricing(self) -> ModelPricing:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return 1


def test_valid_structured_extract_is_repo_blind() -> None:
    adapter = RecordingAdapter(
        arguments={
            "claims": [
                {
                    "id": "c1",
                    "kind": "functional",
                    "text": "Add JWT refresh to existing auth",
                    "status": "DECISION",
                    "touches_auth": True,
                }
            ]
        }
    )
    claim_set = extract_claims("Add JWT refresh to the existing auth module", adapter)
    assert not claim_set.extract_failed
    assert len(claim_set.claims) == 1
    assert claim_set.claims[0].kind is ClaimKind.FUNCTIONAL
    assert claim_set.claims[0].status is EpistemicStatus.DECISION
    assert claim_set.claims[0].provenance.source == "request"
    sent = adapter.requests[0]
    blob = " ".join(message.content or "" for message in sent.messages).lower()
    assert "catalog_hash" not in blob
    assert "architecture_summary" not in blob
    assert "sessionreposnapshot" not in blob
    assert sent.operation == "extract_claims"
    assert extract_claims.__code__.co_varnames[:3] == ("request", "adapter", "extra_intake")


def test_malformed_then_valid_retries_once() -> None:
    adapter = RecordingAdapter(
        arguments={"claims": [{"kind": "functional", "text": "Ship it", "status": "DECISION"}]},
    )
    adapter._bad_payloads = [{"not_claims": []}]
    claim_set = extract_claims("Ship it", adapter)
    assert len(adapter.requests) == 2
    assert not claim_set.extract_failed
    assert claim_set.claims[0].text == "Ship it"


def test_missing_fields_fail_closed() -> None:
    adapter = RecordingAdapter(
        bad_payloads=[
            {"claims": [{"kind": "functional"}]},
            {"claims": [{"kind": "functional"}]},
        ]
    )
    claim_set = extract_claims("add auth", adapter)
    assert claim_set.extract_failed
    assert claim_set.claims == []


def test_invalid_kind_fail_closed() -> None:
    adapter = RecordingAdapter(
        bad_payloads=[
            {"claims": [{"kind": "vibe", "text": "x"}]},
            {"claims": [{"kind": "vibe", "text": "x"}]},
        ]
    )
    claim_set = extract_claims("x", adapter)
    assert claim_set.extract_failed
    assert claim_set.claims == []


def test_model_failure_does_not_invent_requirements() -> None:
    adapter = RecordingAdapter(raise_runtime=True)
    adapter._fail_times = 2
    claim_set = extract_claims("add auth", adapter)
    assert claim_set.extract_failed
    assert claim_set.claims == []


def test_fact_status_from_extract_is_not_locked_in() -> None:
    adapter = RecordingAdapter(
        arguments={"claims": [{"kind": "functional", "text": "Use FastAPI", "status": "FACT"}]}
    )
    claim_set = extract_claims("Use FastAPI", adapter)
    assert claim_set.claims[0].status is EpistemicStatus.UNKNOWN


def test_extract_has_no_repository_parameters() -> None:
    names = extract_claims.__code__.co_varnames
    for forbidden in ("snapshot", "ri", "repo", "summary", "catalog_hash"):
        assert forbidden not in names
