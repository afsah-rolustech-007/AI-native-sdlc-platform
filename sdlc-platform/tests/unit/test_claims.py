"""Group A: kind vs status, FACT+DECISION vs CONTRADICTION, provenance."""

from __future__ import annotations

from typing import Literal

import pytest

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
    flag_contradiction,
    has_contradiction,
    is_fact_plus_decision,
)


def _claim(
    claim_id: str,
    text: str,
    *,
    kind: ClaimKind = ClaimKind.FUNCTIONAL,
    status: EpistemicStatus = EpistemicStatus.DECISION,
    source: Literal["request", "engineer", "repository", "derived", "assumption"] = "request",
) -> Claim:
    return Claim(
        id=claim_id,
        kind=kind,
        text=text,
        status=status,
        provenance=Provenance(source=source, ref=claim_id),
    )


def test_kind_and_status_are_separate_fields() -> None:
    claim = _claim("c1", "Use MongoDB")
    assert claim.kind is ClaimKind.FUNCTIONAL
    assert claim.status is EpistemicStatus.DECISION
    dumped = claim.model_dump()
    assert dumped["kind"] == "functional"
    assert dumped["status"] == "DECISION"


def test_repo_fact_plus_user_decision_is_not_contradiction() -> None:
    claim_set = ClaimSet(
        claims=[
            _claim(
                "c-pg",
                "PostgreSQL is configured",
                kind=ClaimKind.REPO_DEPENDENT,
                status=EpistemicStatus.FACT,
                source="repository",
            ),
            _claim("c-mongo", "Use MongoDB instead"),
        ]
    )
    assert is_fact_plus_decision(claim_set)
    assert not has_contradiction(claim_set)


def test_flag_contradiction_requires_explicit_decisions() -> None:
    claim_set = ClaimSet(
        claims=[
            _claim("a", "REST only"),
            _claim("b", "GraphQL only"),
        ]
    )
    conflicted = flag_contradiction(claim_set, "a", "b")
    assert has_contradiction(conflicted)
    assert {c.status for c in conflicted.claims} == {EpistemicStatus.CONTRADICTION}


def test_flag_contradiction_rejects_fact() -> None:
    claim_set = ClaimSet(
        claims=[
            _claim("a", "PostgreSQL", status=EpistemicStatus.FACT, source="repository"),
            _claim("b", "MongoDB"),
        ]
    )
    with pytest.raises(ValueError, match="explicit decisions"):
        flag_contradiction(claim_set, "a", "b")


def test_provenance_is_preserved_on_copy() -> None:
    claim = _claim("c1", "Keep PostgreSQL", source="request")
    claim.provenance.retrieved_via = "none"
    copied = claim.model_copy()
    assert copied.provenance.source == "request"
    assert copied.provenance.ref == "c1"
    assert copied.provenance.catalog_hash is None


def test_unknown_status_is_explicit() -> None:
    claim = _claim("c1", "maybe auth", status=EpistemicStatus.UNKNOWN)
    assert claim.status is EpistemicStatus.UNKNOWN
    assert claim.status != EpistemicStatus.DECISION
