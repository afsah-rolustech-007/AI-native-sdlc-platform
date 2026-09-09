"""Additive question ranking. No BED-LLM, no learned ranker, no LLM.

Mandatory unanswered slots always stay in the queue (depends_on order).
`asking_cost` is a gate on optional slots, never a divisor.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from requirements_engine.claims import ClaimSet, EpistemicStatus
from requirements_engine.models import Question

WEIGHT_IMPACT = 0.35
WEIGHT_RISK = 0.25
WEIGHT_VALUE = 0.25
WEIGHT_UNRESOLVED = 0.15
SESSION_HUMAN_QUESTION_CAP = 12

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class RankConfig(BaseModel):
    """Session knobs. Mandatory questions ignore asking_cost and the cap."""

    human_question_budget: int = SESSION_HUMAN_QUESTION_CAP
    asking_cost_limit: float = 1.0


class RankedQuestion(BaseModel):
    """One slot's score plus why it was selected or skipped."""

    question_id: str
    score: float
    mandatory: bool
    selected: bool
    deferred: bool = False
    reason: str
    unresolvedness: float
    components: dict[str, float] = Field(default_factory=dict)


class RankingResult(BaseModel):
    ranked: list[RankedQuestion]
    selected_ids: list[str]


def rank_questions(
    questions: list[Question],
    claim_set: ClaimSet,
    *,
    auto_answered: set[str] | None = None,
    config: RankConfig | None = None,
) -> RankingResult:
    """Deterministic ranking. Same inputs always produce the same order."""
    cfg = config or RankConfig()
    answered = auto_answered or set()
    scored = [_score_one(question, claim_set, answered, cfg) for question in questions]
    mandatory_ids = _mandatory_order(questions, answered)
    optional_ok = [
        row
        for row, question in zip(scored, questions, strict=True)
        if not question.mandatory
        and question.id not in answered
        and not row.deferred
        and row.score > 0
    ]
    optional_ok.sort(key=lambda row: (-row.score, row.question_id))
    remaining = max(0, cfg.human_question_budget - len(mandatory_ids))
    optional_ids = [row.question_id for row in optional_ok[:remaining]]
    selected = set(mandatory_ids) | set(optional_ids)

    ranked: list[RankedQuestion] = []
    for row, question in zip(scored, questions, strict=True):
        ranked.append(_mark_selection(row, question, answered, selected, optional_ids))

    return RankingResult(ranked=ranked, selected_ids=mandatory_ids + optional_ids)


def _mark_selection(
    row: RankedQuestion,
    question: Question,
    answered: set[str],
    selected: set[str],
    optional_ids: list[str],
) -> RankedQuestion:
    if question.id in answered or (row.score == 0 and not question.mandatory):
        return row
    if question.mandatory:
        return row.model_copy(update={"selected": True})
    if row.deferred:
        return row
    if question.id in selected:
        place = next(i for i, qid in enumerate(optional_ids, start=1) if qid == question.id)
        return row.model_copy(
            update={
                "selected": True,
                "reason": f"selected: additive score rank {place} among optional slots",
            }
        )
    return row.model_copy(
        update={
            "selected": False,
            "reason": "not selected: lower additive score than the session budget allows",
        }
    )


def _score_one(
    question: Question,
    claim_set: ClaimSet,
    answered: set[str],
    cfg: RankConfig,
) -> RankedQuestion:
    components = {
        "impact": question.impact,
        "risk": question.risk,
        "value": question.information_value,
    }
    if question.id in answered:
        return RankedQuestion(
            question_id=question.id,
            score=0.0,
            mandatory=question.mandatory,
            selected=False,
            reason="evidence already suffices; score = 0",
            unresolvedness=0.0,
            components=components,
        )
    unresolved = _unresolvedness(question, claim_set)
    score = round(
        WEIGHT_IMPACT * question.impact
        + WEIGHT_RISK * question.risk
        + WEIGHT_VALUE * question.information_value
        + WEIGHT_UNRESOLVED * unresolved,
        6,
    )
    components = {**components, "unresolvedness": unresolved}
    if question.mandatory:
        return RankedQuestion(
            question_id=question.id,
            score=score,
            mandatory=True,
            selected=True,
            reason="mandatory gate: always queued; cannot be ranked away by score or asking_cost",
            unresolvedness=unresolved,
            components=components,
        )
    if question.asking_cost > cfg.asking_cost_limit:
        return RankedQuestion(
            question_id=question.id,
            score=score,
            mandatory=False,
            selected=False,
            deferred=True,
            reason="asking_cost gate deferred this optional slot (mandatory slots ignore the gate)",
            unresolvedness=unresolved,
            components=components,
        )
    return RankedQuestion(
        question_id=question.id,
        score=score,
        mandatory=False,
        selected=False,
        reason="optional additive score",
        unresolvedness=unresolved,
        components=components,
    )


def _mandatory_order(questions: list[Question], answered: set[str]) -> list[str]:
    """Keep unanswered mandatory slots; order by depends_on, then id."""
    mandatory = [
        question for question in questions if question.mandatory and question.id not in answered
    ]
    known = {question.id for question in mandatory}
    pending = {
        question.id: {dep for dep in question.depends_on if dep in known} for question in mandatory
    }
    ready = sorted(qid for qid, deps in pending.items() if not deps)
    ordered: list[str] = []
    seen: set[str] = set()
    while ready:
        current = ready.pop(0)
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        newly: list[str] = []
        for qid, deps in pending.items():
            if current in deps:
                deps.remove(current)
                if not deps and qid not in seen:
                    newly.append(qid)
        ready.extend(sorted(newly))
    leftover = sorted(qid for qid in pending if qid not in seen)
    return ordered + leftover


def _unresolvedness(question: Question, claim_set: ClaimSet) -> float:
    """1 UNKNOWN, 0.5 INFERENCE, 0 FACT/DECISION. CONTRADICTION stays unresolved."""
    related = [claim for claim in claim_set.claims if _related(question, claim.text)]
    if not related:
        return 1.0
    statuses = {claim.status for claim in related}
    if EpistemicStatus.CONTRADICTION in statuses:
        return 1.0
    if statuses <= {EpistemicStatus.FACT, EpistemicStatus.DECISION}:
        return 0.0
    if EpistemicStatus.INFERENCE in statuses and EpistemicStatus.UNKNOWN not in statuses:
        return 0.5
    if EpistemicStatus.UNKNOWN in statuses:
        return 1.0
    return 0.5


def _related(question: Question, text: str) -> bool:
    q_tokens = {
        match.group(0).lower() for match in _TOKEN.finditer(question.text) if len(match.group(0)) >= 4
    }
    c_tokens = {match.group(0).lower() for match in _TOKEN.finditer(text) if len(match.group(0)) >= 4}
    if not q_tokens or not c_tokens:
        return False
    return bool(q_tokens & c_tokens)
