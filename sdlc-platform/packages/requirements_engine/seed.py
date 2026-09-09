"""Fill human-decision slots from explicit request/engineer DECISIONs.

Does not use repository FACTs. Does not close compliance slots from JWT/auth
wording — only from explicit compliance/regulatory decisions.
"""

from __future__ import annotations

from requirements_engine.claims import Claim, ClaimSet, EpistemicStatus, has_contradiction
from requirements_engine.dag import QuestionQueue
from requirements_engine.models import Question

_USER_HINTS = ("user", "consumer", "customer", "clients")
_COMPLIANCE_HINTS = ("compliance", "gdpr", "pci", "soc2", "hipaa", "regulatory")


def seed_slots_from_decisions(queue: QuestionQueue, claims: ClaimSet) -> list[str]:
    """Answer activated policy slots already decided in the request. Returns ids."""
    if has_contradiction(claims):
        return []
    decisions = [
        claim
        for claim in claims.claims
        if claim.status is EpistemicStatus.DECISION
        and claim.provenance.source == "request"
    ]
    seeded: list[str] = []
    for question in list(queue.activated()):
        if question.id in queue.answers:
            continue
        if question.evidence_plan is not None:
            continue
        text = _decision_text_for_slot(question, decisions)
        if text is None:
            continue
        queue.answer(question.id, text, source="human")
        seeded.append(question.id)
    return seeded


def _decision_text_for_slot(question: Question, decisions: list[Claim]) -> str | None:
    if question.category == "business_objective":
        return _first_text(decisions, kinds=("objective", "functional"))
    if question.category == "security_compliance":
        return _first_matching(decisions, _COMPLIANCE_HINTS)
    text = question.text.lower()
    if "acceptance" in text:
        return _first_text(decisions, kinds=("acceptance",))
    if any(word in text for word in ("user", "consumer")):
        return _first_matching(decisions, _USER_HINTS)
    return None


def _first_text(decisions: list[Claim], *, kinds: tuple[str, ...]) -> str | None:
    for claim in decisions:
        if claim.kind.value in kinds:
            return claim.text
    return None


def _first_matching(decisions: list[Claim], hints: tuple[str, ...]) -> str | None:
    for claim in decisions:
        lowered = claim.text.lower()
        if any(hint in lowered for hint in hints):
            return claim.text
    return None
