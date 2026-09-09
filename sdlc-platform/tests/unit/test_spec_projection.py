"""ClaimSet → §B.2 RequirementsSpec. Must stay aligned with orchestration.state."""

from __future__ import annotations

from typing import Literal

from orchestration.state import RequirementsSpec as GraphRequirementsSpec
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
    flag_contradiction,
)
from requirements_engine.project import RequirementsSpec, project_spec


def _claim(
    claim_id: str,
    text: str,
    *,
    kind: ClaimKind = ClaimKind.FUNCTIONAL,
    status: EpistemicStatus = EpistemicStatus.DECISION,
    source: Literal["request", "engineer", "repository", "derived", "assumption"] = "request",
    nfr_type: str | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        kind=kind,
        text=text,
        status=status,
        nfr_type=nfr_type,
        provenance=Provenance(source=source, ref=claim_id),
    )


def test_projected_spec_fields_match_orchestration_state() -> None:
    assert set(RequirementsSpec.__annotations__) == set(GraphRequirementsSpec.__annotations__)


def test_projection_maps_decisions_and_keeps_unknowns() -> None:
    spec = project_spec(
        ClaimSet(
            claims=[
                _claim("c1", "Add refresh tokens"),
                _claim("c2", "p95 under 200ms", kind=ClaimKind.NFR, nfr_type="latency"),
                _claim("c3", "Given a valid user, refresh succeeds", kind=ClaimKind.ACCEPTANCE),
                _claim("c4", "Mobile client is out of scope", kind=ClaimKind.OUT_OF_SCOPE),
                _claim("c5", "Auth method unspecified", status=EpistemicStatus.UNKNOWN),
            ]
        )
    )
    assert spec["functional"] == ["Add refresh tokens"]
    assert spec["non_functional"] == {"latency": "p95 under 200ms"}
    assert spec["acceptance_criteria"] == ["Given a valid user, refresh succeeds"]
    assert spec["out_of_scope"] == ["Mobile client is out of scope"]
    assert spec["open_ambiguities"] == ["Auth method unspecified"]
    assert spec["version"] == 1
    assert spec["approved_at"] is None
    assert spec["approved_by"] is None


def test_repo_fact_does_not_become_a_requirement() -> None:
    spec = project_spec(
        ClaimSet(
            claims=[
                _claim(
                    "c-pg",
                    "PostgreSQL is configured",
                    kind=ClaimKind.REPO_DEPENDENT,
                    status=EpistemicStatus.FACT,
                    source="repository",
                ),
                _claim("c-mongo", "Use MongoDB"),
            ]
        )
    )
    assert spec["functional"] == ["Use MongoDB"]
    assert spec["assumptions"] == ["Repository fact: PostgreSQL is configured"]
    assert spec["open_ambiguities"] == []


def test_contradiction_is_not_dropped() -> None:
    claim_set = flag_contradiction(
        ClaimSet(claims=[_claim("a", "REST only"), _claim("b", "GraphQL only")]),
        "a",
        "b",
    )
    spec = project_spec(claim_set)
    assert spec["functional"] == []
    assert any("REST only" in item for item in spec["open_ambiguities"])
    assert any("GraphQL only" in item for item in spec["open_ambiguities"])


def test_inference_goes_to_assumptions() -> None:
    spec = project_spec(
        ClaimSet(
            claims=[
                _claim(
                    "c1",
                    "Auth probably uses JWT",
                    status=EpistemicStatus.INFERENCE,
                    source="derived",
                )
            ]
        )
    )
    assert spec["assumptions"] == ["Auth probably uses JWT"]
    assert spec["functional"] == []


def test_failed_extract_does_not_invent_functional_requirements() -> None:
    spec = project_spec(ClaimSet(claims=[], raw_request="add auth", extract_failed=True))
    assert spec["functional"] == []
    assert spec["acceptance_criteria"] == []
    assert spec["open_ambiguities"] == ["extraction failed; request treated as unstructured"]
