"""Group B targeted retrieval: budgets, cache, fail-closed sources, no FACT from semantic."""

from __future__ import annotations

import pytest
from tests.helpers.fake_repo_intel import FakeRI, embeddings_missing, zoekt_unavailable

from repo_intel.exceptions import StaleIndexError
from requirements_engine.plans import EvidencePlan, PlanMethod
from requirements_engine.retrieve import RetrievalSession, execute_plan
from requirements_engine.snapshot import SessionRepoSnapshot, SnapshotCache, build_snapshot


def _session(snapshot: SessionRepoSnapshot, *, budget: int = 16) -> RetrievalSession:
    return RetrievalSession(snapshot=snapshot, session_budget=budget)


async def _fresh_snapshot(ri: FakeRI | None = None) -> tuple[FakeRI, SessionRepoSnapshot]:
    client = ri or FakeRI()
    snapshot = await build_snapshot(client, cache=SnapshotCache())
    return client, snapshot


async def test_targeted_symbol_retrieval() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="does_auth_service_exist",
        methods=[
            PlanMethod(
                signal="symbol",
                symbol_id="auth/service.py::AuthService",
                extractor="symbol_exists",
            )
        ],
    )
    records = await execute_plan(plan, snapshot, ri, session)

    assert records[0].refs == ["auth/service.py::AuthService"]
    assert records[0].ri_method == "get_symbol_signature"
    assert records[0].accept_as == "fact"
    assert records[0].unavailable is False
    assert "auth/service.py" in records[0].refs[0]
    assert ri.call_count("get_symbol_signature") == 1
    assert ri.call_count("search_concepts") == 0


async def test_targeted_lexical_retrieval() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="references_AuthService",
        methods=[PlanMethod(signal="lexical", query="AuthService", extractor="identifier_in_snippet")],
    )
    records = await execute_plan(plan, snapshot, ri, session)

    assert any("auth/service.py" in ref for record in records for ref in record.refs)
    assert records[0].ri_method == "search_codebase"
    assert records[0].unavailable is False
    assert ri.call_count("search_codebase") == 1


async def test_semantic_retrieval_is_not_fact() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    semantic_plan = EvidencePlan(
        need="code_about_session_expiry",
        methods=[PlanMethod(signal="semantic", query="bearer token", top_k=3)],
        accept_as="inference",
    )
    records = await execute_plan(semantic_plan, snapshot, ri, session)

    assert records
    assert all(record.accept_as == "inference" for record in records)
    assert all(record.signal == "semantic" for record in records)
    assert ri.call_count("search_concepts") == 1
    kwargs = next(args for name, args in ri.calls if name == "search_concepts")
    assert kwargs["top_k"] == 3


async def test_graph_retrieval() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="blast_radius_auth",
        methods=[
            PlanMethod(
                signal="graph",
                graph_op="dependents",
                file_path="auth/service.py",
                extractor="neighborhood_nonempty",
            )
        ],
    )
    records = await execute_plan(plan, snapshot, ri, session)

    assert "web/main.py" in records[0].refs
    assert records[0].ri_method == "get_dependents"
    assert ri.call_count("get_dependents") == 1
    assert ri.call_count("search_concepts") == 0


async def test_retrieval_budget_enforcement() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot, budget=1)
    plan = EvidencePlan(
        need="many_lookups",
        methods=[
            PlanMethod(signal="symbol", symbol_id="missing.py::Nope"),
            PlanMethod(signal="symbol", symbol_id="auth/service.py::AuthService"),
            PlanMethod(signal="lexical", query="AuthService"),
            PlanMethod(signal="semantic", query="login"),
        ],
        accept_as="inference",
        max_ri_calls=8,
    )
    await execute_plan(plan, snapshot, ri, session)

    assert session.ri_calls == 1
    assert ri.call_count("get_symbol_signature") == 1
    assert ri.call_count("search_codebase") == 0
    assert ri.call_count("search_concepts") == 0


async def test_duplicate_query_cache_hit() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="does_auth_service_exist",
        methods=[PlanMethod(signal="symbol", symbol_id="auth/service.py::AuthService")],
    )
    first = await execute_plan(plan, snapshot, ri, session)
    second = await execute_plan(plan, snapshot, ri, session)

    assert ri.call_count("get_symbol_signature") == 1
    assert first[0].cache_hit is False
    assert second[0].cache_hit is True
    assert second[0].refs == first[0].refs
    assert any(trace.cache_hit for trace in session.traces)
    assert session.ri_calls == 1


async def test_zoekt_unavailable_is_not_zero_results() -> None:
    ri = FakeRI()
    ri.lexical_error = zoekt_unavailable()
    _, snapshot = await _fresh_snapshot(ri)
    session = _session(snapshot)
    plan = EvidencePlan(
        need="references_JWT",
        methods=[PlanMethod(signal="lexical", query="JWT")],
    )
    records = await execute_plan(plan, snapshot, ri, session)

    assert records[0].unavailable is True
    assert records[0].refs == []
    assert records[0].result_count == 0
    assert "ZoektUnavailable" in (records[0].unavailable_reason or "")
    assert session.zoekt == "unavailable"
    # A second identical query is a cache hit, still unavailable — not "no JWT".
    again = await execute_plan(plan, snapshot, ri, session)
    assert again[0].unavailable is True
    assert again[0].cache_hit is True
    assert ri.call_count("search_codebase") == 1


async def test_snapshot_hit_skips_later_ri_methods() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="existing_auth_module",
        methods=[
            PlanMethod(signal="snapshot", query="auth", extractor="service_exists"),
            PlanMethod(signal="lexical", query="AuthService"),
            PlanMethod(signal="semantic", query="login"),
        ],
    )
    records = await execute_plan(plan, snapshot, ri, session)

    assert any(ref == "service:auth" for record in records for ref in record.refs)
    assert any("auth/service.py" in ref for record in records for ref in record.refs)
    assert ri.call_count("search_codebase") == 0
    assert ri.call_count("search_concepts") == 0


async def test_find_relevant_context_is_never_called() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="existing_auth_module",
        methods=[
            PlanMethod(signal="snapshot", query="auth"),
            PlanMethod(signal="symbol", symbol_id="auth/service.py::AuthService"),
            PlanMethod(signal="lexical", query="AuthService"),
            PlanMethod(signal="graph", graph_op="impact", file_path="auth/service.py"),
            PlanMethod(signal="semantic", query="login"),
        ],
        accept_as="inference",
        max_ri_calls=8,
    )
    await execute_plan(plan, snapshot, ri, session)
    assert ri.call_count("find_relevant_context") == 0


async def test_refresh_true_is_never_passed() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot)
    plan = EvidencePlan(
        need="mix",
        methods=[
            PlanMethod(signal="symbol", symbol_id="missing.py::Nope"),
            PlanMethod(signal="lexical", query="AuthService"),
            PlanMethod(signal="semantic", query="token", top_k=3),
            PlanMethod(signal="graph", graph_op="dependents", file_path="auth/service.py"),
        ],
        accept_as="inference",
        max_ri_calls=8,
    )
    await execute_plan(plan, snapshot, ri, session)
    assert ri.refresh_true_calls() == []


async def test_stale_index_during_retrieve_fails_closed() -> None:
    ri, snapshot = await _fresh_snapshot()
    ri.stale_on_read = True
    session = _session(snapshot)
    plan = EvidencePlan(
        need="does_auth_service_exist",
        methods=[PlanMethod(signal="symbol", symbol_id="auth/service.py::AuthService")],
    )
    with pytest.raises(StaleIndexError):
        await execute_plan(plan, snapshot, ri, session)


async def test_embeddings_unavailable_is_not_empty_success() -> None:
    ri = FakeRI()
    ri.semantic_error = embeddings_missing()
    _, snapshot = await _fresh_snapshot(ri)
    session = _session(snapshot)
    plan = EvidencePlan(
        need="related_code",
        methods=[PlanMethod(signal="semantic", query="session expiry")],
        accept_as="inference",
    )
    records = await execute_plan(plan, snapshot, ri, session)
    assert records[0].unavailable is True
    assert records[0].accept_as == "inference"
    assert session.embeddings == "unavailable"


async def test_plan_max_ri_calls_caps_before_session_budget() -> None:
    ri, snapshot = await _fresh_snapshot()
    session = _session(snapshot, budget=16)
    plan = EvidencePlan(
        need="mix",
        methods=[
            PlanMethod(signal="symbol", symbol_id="missing.py::Nope"),
            PlanMethod(signal="lexical", query="AuthService"),
        ],
        accept_as="inference",
        max_ri_calls=1,
    )
    await execute_plan(plan, snapshot, ri, session)
    assert session.ri_calls == 1
    assert ri.call_count("search_codebase") == 0
