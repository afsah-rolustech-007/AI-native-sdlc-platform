"""RequirementsSufficiency 3-way gate. No B.4 placeholders."""

from __future__ import annotations

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
    flag_contradiction,
)
from requirements_engine.sufficiency import evaluate_sufficiency


def _claims(*rows: tuple[str, str, EpistemicStatus]) -> ClaimSet:
    return ClaimSet(
        claims=[
            Claim(
                id=claim_id,
                kind=ClaimKind.FUNCTIONAL,
                text=text,
                status=status,
                provenance=Provenance(source="request", ref=claim_id),
            )
            for claim_id, text, status in rows
        ]
    )


def test_spec_ready_when_mandatory_answered_and_no_contradiction() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "Export invoices", EpistemicStatus.DECISION)),
        mandatory_unanswered=[],
        askable_remaining=["Qdep1"],
        evidence_coverage=1.0,
        human_questions_asked=0,
        human_question_budget=12,
    )
    assert report.decision == "spec_ready"


def test_accept_gaps_when_engineer_confirms() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "maybe auth", EpistemicStatus.UNKNOWN)),
        mandatory_unanswered=["Q1"],
        askable_remaining=["Q1"],
        evidence_coverage=0.0,
        human_questions_asked=2,
        human_question_budget=12,
        accept_gaps=True,
    )
    assert report.decision == "accept_gaps"
    assert "accepted" in report.reason


def test_needs_hitl_on_contradiction_even_with_accept_gaps() -> None:
    claim_set = flag_contradiction(
        _claims(
            ("a", "REST only", EpistemicStatus.DECISION),
            ("b", "GraphQL only", EpistemicStatus.DECISION),
        ),
        "a",
        "b",
    )
    report = evaluate_sufficiency(
        claim_set=claim_set,
        mandatory_unanswered=[],
        askable_remaining=[],
        evidence_coverage=1.0,
        human_questions_asked=0,
        human_question_budget=12,
        accept_gaps=True,
    )
    assert report.decision == "needs_hitl"
    assert report.contradiction is True


def test_needs_hitl_on_stale_ri_cannot_be_spec_ready() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "Export invoices", EpistemicStatus.DECISION)),
        mandatory_unanswered=[],
        askable_remaining=[],
        evidence_coverage=0.0,
        human_questions_asked=0,
        human_question_budget=12,
        ri_unavailable=True,
    )
    assert report.decision == "needs_hitl"
    assert "stale" in report.reason or "unavailable" in report.reason


def test_needs_hitl_on_extract_failure() -> None:
    report = evaluate_sufficiency(
        claim_set=ClaimSet(extract_failed=True, raw_request="add auth"),
        mandatory_unanswered=["Q1"],
        askable_remaining=["Q1"],
        evidence_coverage=0.0,
        human_questions_asked=0,
        human_question_budget=12,
    )
    assert report.decision == "needs_hitl"


def test_unresolved_mandatory_is_not_spec_ready() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "unclear", EpistemicStatus.UNKNOWN)),
        mandatory_unanswered=["Qsec1"],
        askable_remaining=["Qsec1"],
        evidence_coverage=0.5,
        human_questions_asked=1,
        human_question_budget=12,
    )
    assert report.decision == "continue"
    assert "Qsec1" in report.mandatory_unanswered


def test_budget_exhausted_does_not_drop_mandatory() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "unclear", EpistemicStatus.UNKNOWN)),
        mandatory_unanswered=["Qsec1"],
        askable_remaining=["Qsec1"],
        evidence_coverage=0.0,
        human_questions_asked=12,
        human_question_budget=12,
    )
    assert report.decision == "continue"


def test_budget_exhausted_without_askable_is_needs_hitl() -> None:
    report = evaluate_sufficiency(
        claim_set=_claims(("c1", "unclear", EpistemicStatus.UNKNOWN)),
        mandatory_unanswered=["Q1"],
        askable_remaining=[],
        evidence_coverage=0.0,
        human_questions_asked=12,
        human_question_budget=12,
    )
    assert report.decision == "needs_hitl"
