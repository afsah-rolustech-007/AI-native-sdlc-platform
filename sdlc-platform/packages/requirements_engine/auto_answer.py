"""Deterministic auto-answer. No LLM. No RI. Fail closed: when in doubt, ask.

Auto-answers describe *repository situation* only. They never overwrite a user
DECISION and never treat semantic/graph hits as a closed answer.
"""

from __future__ import annotations

import re

from requirements_engine.claims import ClaimSet, EpistemicStatus, EvidenceRecord
from requirements_engine.exceptions import EvidencePlanError
from requirements_engine.extractors import ExtractorHit, run_extractor
from requirements_engine.models import AutoAnswer, Question
from requirements_engine.plans import parse_evidence_plan
from requirements_engine.snapshot import SessionRepoSnapshot

# Policy slots always go to a human, even if the repo has related facts.
_POLICY_CATEGORIES = frozenset(
    {
        "business_objective",
        "security_compliance",
        "performance",
    }
)
_POLICY_TEXT = re.compile(
    r"\b(should|must we|compliance|regulatory|gdpr|pci|sla|rto|rpo|"
    r"additive|workaround|want|prefer)\b",
    re.IGNORECASE,
)

# Needs whose extractor answers the slot text (repo situation, not preference).
_SITUATION_NEEDS = frozenset(
    {
        "repo_languages",
        "declared_database",
        "declared_dependency",
        "existing_auth_module",
        "existing_database_entities",
        "symbol_exists",
        "does_auth_service_exist",
    }
)


def try_answer(
    slot: Question,
    claims: ClaimSet,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
) -> AutoAnswer | None:
    """Return a FACT auto-answer or None. Low confidence and inference → None."""
    blocked = _blocked_reason(slot, claims)
    if blocked is not None:
        return None
    if slot.evidence_plan is None:
        return None
    try:
        plan = parse_evidence_plan(slot.evidence_plan)
    except EvidencePlanError:
        return None
    if plan.accept_as != "fact":
        return None
    if plan.need not in _SITUATION_NEEDS and not _looks_like_situation_question(slot):
        return None

    for method in plan.methods:
        if method.extractor is None:
            continue
        hit = run_extractor(
            method.extractor,
            snapshot=snapshot,
            evidence=evidence,
            query=method.query or method.symbol_id,
        )
        answer = _hit_to_auto_answer(slot, hit)
        if answer is not None:
            return answer
    return None


def _hit_to_auto_answer(slot: Question, hit: ExtractorHit | None) -> AutoAnswer | None:
    if hit is None:
        return None
    if hit.status != "fact" or hit.confidence == "low":
        return None
    if not hit.refs:
        return None
    return AutoAnswer(
        slot_id=slot.id,
        answer=hit.answer,
        evidence_refs=list(hit.refs),
        status="fact",
        confidence=hit.confidence,
    )


def _blocked_reason(slot: Question, claims: ClaimSet) -> str | None:
    """Human-only slots. Returning a string means 'do not auto-answer'."""
    if slot.category in _POLICY_CATEGORIES:
        return "policy category"
    if _POLICY_TEXT.search(slot.text or ""):
        return "policy wording"
    # A user DECISION about this change is never replaced by a repo fact.
    has_user_decision = any(
        claim.status is EpistemicStatus.DECISION
        and claim.provenance.source in {"request", "engineer"}
        for claim in claims.claims
    )
    if has_user_decision and _slot_would_override_decision(slot):
        return "user DECISION must not be overwritten"
    return None


def _slot_would_override_decision(slot: Question) -> bool:
    """True when auto-answering this slot would present a repo fact as the requirement."""
    need = (slot.evidence_plan or {}).get("need") if slot.evidence_plan else None
    if need != "declared_database":
        return False
    # Qdb_tech is "what does the repo declare today" — that is not the requirement.
    text = slot.text.lower()
    return any(word in text for word in ("should", "use", "choose", "instead"))


def _looks_like_situation_question(slot: Question) -> bool:
    text = slot.text.lower()
    return any(
        phrase in text
        for phrase in (
            "currently use",
            "currently declare",
            "already exist",
            "repository currently",
            "does the repository",
        )
    )
