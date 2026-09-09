"""Group C: classify claims from evidence. No LLM."""

from __future__ import annotations

from typing import Literal

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
    has_contradiction,
    is_fact_plus_decision,
)
from requirements_engine.classify import classify_claims
from requirements_engine.manifests import ManifestFact
from requirements_engine.snapshot import ServiceSlice, SessionRepoSnapshot


def _claim(
    claim_id: str,
    text: str,
    *,
    kind: ClaimKind = ClaimKind.FUNCTIONAL,
    status: EpistemicStatus = EpistemicStatus.UNKNOWN,
    source: Literal["request", "engineer", "repository", "derived", "assumption"] = "request",
) -> Claim:
    return Claim(
        id=claim_id,
        kind=kind,
        text=text,
        status=status,
        provenance=Provenance(source=source, ref=claim_id),
    )


def _snapshot(**kwargs: object) -> SessionRepoSnapshot:
    return SessionRepoSnapshot(
        repo_root="/tmp/repo",
        catalog_hash="hash1",
        file_count=10,
        index_state="fresh",
        **kwargs,  # type: ignore[arg-type]
    )


def test_postgres_fact_plus_mongodb_decision_both_preserved() -> None:
    snapshot = _snapshot(
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg", "fastapi"])]
    )
    claim_set = ClaimSet(
        claims=[
            _claim(
                "c-pg",
                "PostgreSQL is configured",
                kind=ClaimKind.REPO_DEPENDENT,
                source="repository",
            ),
            _claim("c-mongo", "Use MongoDB instead", status=EpistemicStatus.DECISION),
        ]
    )
    result = classify_claims(claim_set, snapshot=snapshot)
    by_id = {claim.id: claim for claim in result.claim_set.claims}
    assert by_id["c-pg"].status is EpistemicStatus.FACT
    assert by_id["c-mongo"].status is EpistemicStatus.DECISION
    assert is_fact_plus_decision(result.claim_set)
    assert not has_contradiction(result.claim_set)
    assert by_id["c-pg"].provenance.retrieved_via == "manifest"
    assert by_id["c-mongo"].provenance.source == "request"


def test_explicit_contradictory_decisions_are_flagged() -> None:
    claim_set = ClaimSet(
        claims=[
            _claim("a", "REST only", status=EpistemicStatus.DECISION),
            _claim("b", "GraphQL only", status=EpistemicStatus.DECISION),
        ]
    )
    result = classify_claims(claim_set)
    assert has_contradiction(result.claim_set)
    assert {claim.status for claim in result.claim_set.claims} == {EpistemicStatus.CONTRADICTION}


def test_semantic_evidence_is_inference_never_fact() -> None:
    claim = _claim(
        "c-sem",
        "code about session expiry",
        kind=ClaimKind.REPO_DEPENDENT,
        source="repository",
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="semantic",
            query="session expiry",
            refs=["auth/tokens.py::verify_token"],
            excerpt="verify bearer token signature",
            accept_as="inference",
            result_count=1,
        )
    ]
    result = classify_claims(ClaimSet(claims=[claim]), evidence)
    classified = result.claim_set.claims[0]
    assert classified.status is EpistemicStatus.INFERENCE
    assert classified.provenance.retrieved_via == "semantic"


def test_weak_graph_evidence_is_not_fact() -> None:
    claim = _claim(
        "c-g",
        "auth service related files",
        kind=ClaimKind.REPO_DEPENDENT,
        source="repository",
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="graph",
            query="auth service related files",
            refs=["web/main.py"],
            ri_method="get_dependents",
            accept_as="fact",
            result_count=1,
        )
    ]
    result = classify_claims(ClaimSet(claims=[claim]), evidence)
    assert result.claim_set.claims[0].status is EpistemicStatus.INFERENCE


def test_unknown_stays_unknown_without_evidence() -> None:
    claim_set = ClaimSet(claims=[_claim("c1", "maybe add a cache")])
    result = classify_claims(claim_set)
    assert result.claim_set.claims[0].status is EpistemicStatus.UNKNOWN


def test_user_decision_is_not_overwritten_by_repo_fact() -> None:
    snapshot = _snapshot(
        services=[ServiceSlice(name="auth", files=3, key_symbols=["auth/service.py::AuthService"])]
    )
    claim = _claim(
        "c1",
        "Use a new auth service, ignore existing auth",
        status=EpistemicStatus.DECISION,
    )
    result = classify_claims(ClaimSet(claims=[claim]), snapshot=snapshot)
    assert result.claim_set.claims[0].status is EpistemicStatus.DECISION
    assert result.claim_set.claims[0].provenance.source == "request"
