"""Phase 04 3-way sufficiency gate. No LLM. No B.4 placeholders.

The requirements loop exits here — never via the platform confidence formula.
Missing episodic/validator signals are simply not used.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from requirements_engine.claims import ClaimSet, has_contradiction

ExitOutcome = Literal["spec_ready", "accept_gaps", "needs_hitl"]
GateDecision = Literal["spec_ready", "accept_gaps", "needs_hitl", "continue"]


class SufficiencyReport(BaseModel):
    """Auditable gate result. `decision=continue` means ask another question."""

    decision: GateDecision
    reason: str
    mandatory_unanswered: list[str] = Field(default_factory=list)
    contradiction: bool = False
    high_impact_unknowns: int = 0
    evidence_coverage: float = 0.0
    accept_gaps: bool = False
    budget_exhausted: bool = False
    extract_failed: bool = False
    ri_unavailable: bool = False
    askable_remaining: list[str] = Field(default_factory=list)


def evaluate_sufficiency(
    *,
    claim_set: ClaimSet,
    mandatory_unanswered: list[str],
    askable_remaining: list[str],
    evidence_coverage: float,
    human_questions_asked: int,
    human_question_budget: int,
    accept_gaps: bool = False,
    ri_unavailable: bool = False,
    extract_failed: bool = False,
) -> SufficiencyReport:
    """Fail-closed 3-way exit. `spec_ready` cannot fire if RI is missing/stale."""
    contradictions = has_contradiction(claim_set)
    failed = extract_failed or claim_set.extract_failed
    budget_exhausted = human_questions_asked >= human_question_budget
    # Remaining UNKNOWNs are high-impact only while mandatory slots are open.
    # After mandatory slots are answered they become logged assumptions.
    high_impact = 0 if not mandatory_unanswered else _unknown_requirement_count(claim_set)

    report = SufficiencyReport(
        decision="continue",
        reason="",
        mandatory_unanswered=list(mandatory_unanswered),
        contradiction=contradictions,
        high_impact_unknowns=high_impact,
        evidence_coverage=evidence_coverage,
        accept_gaps=accept_gaps,
        budget_exhausted=budget_exhausted,
        extract_failed=failed,
        ri_unavailable=ri_unavailable,
        askable_remaining=list(askable_remaining),
    )

    if contradictions:
        return report.model_copy(
            update={
                "decision": "needs_hitl",
                "reason": "unresolved CONTRADICTION between explicit decisions",
            }
        )
    if accept_gaps:
        return report.model_copy(
            update={
                "decision": "accept_gaps",
                "reason": "engineer accepted remaining open assumptions",
            }
        )
    if failed:
        return report.model_copy(
            update={
                "decision": "needs_hitl",
                "reason": "structured extraction failed; request treated as unstructured",
            }
        )
    if ri_unavailable:
        return report.model_copy(
            update={
                "decision": "needs_hitl",
                "reason": "repository evidence is stale or unavailable; spec_ready cannot fire",
            }
        )
    if not mandatory_unanswered and high_impact == 0:
        return report.model_copy(
            update={
                "decision": "spec_ready",
                "reason": "mandatory slots answered, no contradictions, no high-impact UNKNOWNs",
            }
        )
    if budget_exhausted and not askable_remaining:
        return report.model_copy(
            update={
                "decision": "needs_hitl",
                "reason": "human-question budget exhausted with remaining unresolved slots",
            }
        )
    if not askable_remaining:
        return report.model_copy(
            update={
                "decision": "needs_hitl",
                "reason": "no askable slot remains; cannot raise sufficiency further",
            }
        )
    return report.model_copy(update={"reason": "ask the next highest-value unresolved slot"})


def _unknown_requirement_count(claim_set: ClaimSet) -> int:
    """UNKNOWNs that are requirements, not unresolved repository situation."""
    count = 0
    for claim in claim_set.claims:
        if claim.status.value != "UNKNOWN":
            continue
        if claim.kind.value == "repo_dependent":
            continue
        count += 1
    return count
