"""Group D RequirementsEngine: one question per step, 3-way exit, no extra LLM."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.fake_repo_intel import FakeRI, zoekt_unavailable
from tests.unit.test_extract import RecordingAdapter

from common.task import WorkType
from requirements_engine.claims import EpistemicStatus
from requirements_engine.context import WorkflowContext
from requirements_engine.engine import RequirementsEngine
from requirements_engine.rank import RankConfig
from requirements_engine.snapshot import SnapshotCache

WELL_SPEC = {
    "claims": [
        {
            "id": "c1",
            "kind": "objective",
            "text": "Add invoice CSV export for billing admins",
            "status": "DECISION",
        },
        {
            "id": "c2",
            "kind": "functional",
            "text": "Billing admins are the consumers of this change",
            "status": "DECISION",
        },
        {
            "id": "c3",
            "kind": "acceptance",
            "text": "Given an invoice, a CSV downloads with id and amount",
            "status": "DECISION",
        },
    ]
}

VAGUE = {
    "claims": [
        {
            "id": "c1",
            "kind": "unknown",
            "text": "add auth",
            "status": "UNKNOWN",
            "touches_auth": True,
        }
    ]
}

CONTRADICTION = {
    "claims": [
        {"id": "a", "kind": "functional", "text": "REST only", "status": "DECISION"},
        {"id": "b", "kind": "functional", "text": "GraphQL only", "status": "DECISION"},
    ]
}


def _safe_context() -> WorkflowContext:
    return WorkflowContext(
        work_type=WorkType.FEATURE,
        touches_auth=False,
        touches_pii=False,
        touches_payments=False,
        has_database_changes=False,
    )


def _engine(
    arguments: dict,
    ri: FakeRI | None = None,
    *,
    context: WorkflowContext | None = None,
    rank_config: RankConfig | None = None,
    cache: SnapshotCache | None = None,
) -> RequirementsEngine:
    return RequirementsEngine(
        "request",
        RecordingAdapter(arguments=arguments),
        ri or FakeRI(),
        context=context,
        rank_config=rank_config,
        snapshot_cache=cache or SnapshotCache(),
    )


async def test_well_specified_exits_spec_ready_with_one_llm_call() -> None:
    engine = _engine(WELL_SPEC, context=_safe_context())
    result = await engine.run()
    assert result.action == "spec_ready"
    assert result.spec is not None
    assert "Add invoice CSV export for billing admins" in result.spec["functional"]
    assert result.counters.llm_calls == 1
    assert result.counters.human_questions == 0
    assert result.counters.auto_answers >= 1
    assert engine.trace.kinds()[0] == "start"
    assert "exit" in engine.trace.kinds()
    assert all(item.status == "fact" for item in result.auto_answers)


async def test_snapshot_is_reused_on_cache() -> None:
    cache = SnapshotCache()
    ri = FakeRI()
    first = _engine(WELL_SPEC, ri, context=_safe_context(), cache=cache)
    await first.run()
    second = _engine(WELL_SPEC, ri, context=_safe_context(), cache=cache)
    await second.run()
    assert cache.hits == 1
    assert second.trace.counters.snapshot_cache_hits == 1
    assert ri.call_count("get_architecture_summary") == 1


async def test_one_human_question_per_step() -> None:
    engine = _engine(VAGUE)
    first = await engine.step()
    assert first.action == "ask"
    assert first.question_id == "Q1"
    second = await engine.step()
    assert second.question_id == "Q1"
    engine.answer("Add SSO for employees")
    third = await engine.step()
    assert third.action == "ask"
    assert third.question_id != "Q1"
    assert third.question_id is not None


async def test_answer_updates_claims_and_dag() -> None:
    engine = _engine(VAGUE)
    await engine.step()
    engine.answer("Add SSO", context_updates={"touches_auth": True})
    assert "Q1" in engine.queue.answers
    added = next(claim for claim in engine.claims.claims if claim.id == "ans-Q1")
    assert added.status is EpistemicStatus.DECISION
    assert added.provenance.source == "engineer"
    assert engine.queue.context.touches_auth is True
    nxt = await engine.step()
    assert nxt.question_id in {"Q2", "Q3", "Qsec1"}


async def test_security_question_not_closed_by_repo_jwt() -> None:
    ri = FakeRI()
    ri.lexical_hits[0].snippet = "issue JWT for AuthService"
    engine = _engine(
        VAGUE,
        ri,
        context=WorkflowContext(touches_auth=True, touches_pii=None, touches_payments=None),
    )
    result = await engine.run({"Q1": "Add login", "Q2": "end users", "Q3": "user can log in"})
    asked = [event.payload.get("question_id") for event in engine.trace.of_kind("ask")]
    assert "Qsec1" in asked
    assert result.action in {"ask", "needs_hitl", "spec_ready", "accept_gaps"}
    if result.action == "ask":
        assert result.question_id in {"Qsec1", "Qsec2", "Qsec3"}


async def test_contradiction_is_needs_hitl() -> None:
    result = await _engine(CONTRADICTION, context=_safe_context()).run()
    assert result.action == "needs_hitl"
    assert result.spec is not None
    assert any("CONTRADICTION" in item for item in result.spec["open_ambiguities"])
    assert result.counters.human_questions == 0


async def test_stale_index_is_needs_hitl_not_spec_ready() -> None:
    result = await _engine(
        WELL_SPEC, FakeRI(state="stale", stale_paths=["touched.py"]), context=_safe_context()
    ).run()
    assert result.action == "needs_hitl"
    assert result.sufficiency is not None
    assert result.sufficiency.ri_unavailable is True


async def test_extract_failure_is_needs_hitl() -> None:
    adapter = RecordingAdapter(raise_runtime=True)
    adapter._fail_times = 2
    engine = RequirementsEngine("add auth", adapter, FakeRI(), context=_safe_context())
    result = await engine.run()
    assert result.action == "needs_hitl"
    assert engine.claims.extract_failed is True
    assert result.spec is not None
    assert result.spec["functional"] == []


async def test_accept_gaps_exit() -> None:
    engine = _engine(VAGUE)
    first = await engine.step()
    assert first.action == "ask"
    engine.accept_gaps()
    result = await engine.step()
    assert result.action == "accept_gaps"
    assert result.spec is not None
    assert any("unanswered Q1" in item for item in result.spec["open_ambiguities"])


async def test_user_decision_not_overwritten_by_repo_postgres(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["psycopg>=3"]\n', encoding="utf-8"
    )
    arguments = {
        "claims": [
            {
                "id": "c-obj",
                "kind": "objective",
                "text": "Migrate reporting off the current database",
                "status": "DECISION",
            },
            {
                "id": "c-user",
                "kind": "functional",
                "text": "Analysts are the consumers of this change",
                "status": "DECISION",
            },
            {
                "id": "c-acc",
                "kind": "acceptance",
                "text": "Reports read from MongoDB",
                "status": "DECISION",
            },
            {
                "id": "c-mongo",
                "kind": "functional",
                "text": "Use MongoDB instead",
                "status": "DECISION",
            },
        ]
    }
    engine = _engine(
        arguments,
        FakeRI(repo_root=tmp_path),
        context=_safe_context(),
    )
    result = await engine.run()
    mongo = next(claim for claim in engine.claims.claims if "MongoDB" in claim.text)
    assert mongo.status is EpistemicStatus.DECISION
    postgres = [claim for claim in engine.claims.claims if "postgres" in claim.text.lower()]
    assert all(claim.status is not EpistemicStatus.CONTRADICTION for claim in postgres)
    assert result.action in {"spec_ready", "ask", "needs_hitl"}


async def test_ri_budget_exhaustion_does_not_invent_spec_ready() -> None:
    engine = RequirementsEngine(
        "add auth",
        RecordingAdapter(arguments=VAGUE),
        FakeRI(),
        context=WorkflowContext(touches_auth=True),
        rank_config=RankConfig(human_question_budget=12),
    )
    first = await engine.step()
    assert first.action == "ask"
    if engine._session is not None:
        engine._session.ri_calls = engine._session.session_budget
    engine.answer("Add SSO")
    nxt = await engine.step()
    assert nxt.action in {"ask", "needs_hitl"}
    assert nxt.action != "spec_ready"


async def test_run_does_not_dump_the_whole_bank() -> None:
    engine = _engine(VAGUE)
    result = await engine.run()
    assert result.action == "ask"
    asked = engine.trace.of_kind("ask")
    assert len(asked) == 1


def test_zoekt_unavailable_helper_still_distinct_from_empty() -> None:
    err = zoekt_unavailable()
    assert "zoekt" in str(err).lower()
