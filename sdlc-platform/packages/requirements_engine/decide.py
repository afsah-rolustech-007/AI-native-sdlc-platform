"""Assemble AUTO / ASK decisions. No LLM, no RI, no engine loop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from requirements_engine.auto_answer import try_answer
from requirements_engine.claims import ClaimSet, EvidenceRecord
from requirements_engine.classify import ClassifyNote, ClassifyResult, classify_claims
from requirements_engine.models import AutoAnswer, Question
from requirements_engine.rank import RankConfig, RankedQuestion, RankingResult, rank_questions
from requirements_engine.render import render_question
from requirements_engine.snapshot import SessionRepoSnapshot


class SlotDecision(BaseModel):
    """
    One slot's outcome: either AUTO (auto-answered by evidence) or ASK (needs human input).
    """
    action: Literal["AUTO", "ASK"]                       # Was this slot automatically answered, or does it need to be asked?
    question_id: str                                     # ID for the question
    question_text: str                                   # Question text (may be rendered with evidence context)
    mandatory: bool                                      # True if this is a required slot
    reason: str                                          # Why was this action taken (explanation for AUTO or ASK)
    auto_answer: AutoAnswer | None = None                # AutoAnswer object if auto-answered, else None
    unresolved_reason: str | None = None                 # Reason slot is unresolved, if relevant
    required: str | None = None                          # Description of what is required to answer this slot
    ranking_score: float | None = None                   # Score in ranking system (for ASK questions)
    selected: bool = True                                # True if selected for question to user (ASK), False for auto
    evidence_refs: list[str] = Field(default_factory=list) # List of evidence refs behind this answer
    confidence: str | None = None                        # Optional confidence value from auto-answer
    status: str | None = None                            # Optional status value from auto-answer


class DecisionReport(BaseModel):
    """
    Output for the group of candidate questions ("slots") processed:
    - classified: claims after classification
    - notes: classification/processing notes
    - auto: list of slots auto-answered (AUTO)
    - ask: list of slots to ask the human (ASK)
    - ranking: ranking result used to choose ASK slots
    """
    classified: ClaimSet
    notes: list[ClassifyNote] = Field(default_factory=list)
    auto: list[SlotDecision] = Field(default_factory=list)
    ask: list[SlotDecision] = Field(default_factory=list)
    ranking: RankingResult | None = None


def evaluate_slots(
    questions: list[Question],
    claim_set: ClaimSet,
    *,
    snapshot: SessionRepoSnapshot | None = None,
    evidence: list[EvidenceRecord] | None = None,
    config: RankConfig | None = None,
) -> DecisionReport:
    """
    Core routine to decide, for each slot/question:
    1. Classify the current set of claims.
    2. Try to auto-answer from evidence.
    3. Rank leftover questions to select which to ask the human.
    4. Bundle results as a DecisionReport.
    """
    records = list(evidence or [])  # Defensive: always a list
    classified: ClassifyResult = classify_claims(claim_set, records, snapshot)  # 1. Classify claims
    auto: list[SlotDecision] = []      # Will store SlotDecision for AUTO
    remaining: list[Question] = []     # Questions we couldn't auto-answer
    auto_ids: set[str] = set()         # Set of auto-answered question IDs

    # Try to auto-answer each question
    for question in questions:
        answer = try_answer(question, classified.claim_set, snapshot, records)
        if answer is not None:
            # This slot can be answered directly with evidence
            auto_ids.add(question.id)
            auto.append(
                SlotDecision(
                    action="AUTO",
                    question_id=question.id,
                    question_text=question.text,
                    mandatory=question.mandatory,
                    reason="deterministic repository evidence; not a user preference",
                    auto_answer=answer,
                    evidence_refs=list(answer.evidence_refs),
                    confidence=answer.confidence,
                    status=answer.status,
                    selected=False,  # Not presented for human answer
                )
            )
        else:
            # Can't auto-answer; keep for ranking/asking
            remaining.append(question)

    # Rank unanswered (remaining) questions to decide which to present to user
    ranking = rank_questions(
        remaining, classified.claim_set, auto_answered=auto_ids, config=config
    )

    # For each remaining question, build an ASK SlotDecision
    ask = [_ask_decision(question, ranking, records) for question in remaining]

    # Bundle all results together
    return DecisionReport(
        classified=classified.claim_set,
        notes=classified.notes,
        auto=auto,
        ask=ask,
        ranking=ranking,
    )


def _ask_decision(
    question: Question,
    ranking: RankingResult,
    evidence: list[EvidenceRecord],
) -> SlotDecision:
    """
    Construct a SlotDecision in ASK mode for this question,
    filling out required user actions and explanation.
    """
    row = _row(ranking, question.id)  # Find the rank info for this question, if any

    # Render the question text, potentially incorporating current evidence context
    rendered = render_question(question, evidence)

    # Decide what type of response is required (plain engineer decision or also repo evidence)
    required = "engineer decision" if question.evidence_plan is None else "repository evidence or engineer decision"

    # Special message if this is a security/compliance category question
    if question.category == "security_compliance":
        required = "engineer compliance/security decision (repository auth facts are not sufficient)"

    # Explain why the slot is still unanswered
    unresolved = row.reason if row is not None else "unanswered"

    # List all available evidence references, filtering out unavailable evidence
    evidence_refs = [
        ref for item in evidence if not item.unavailable for ref in item.refs
    ]

    # Build and return the ASK decision for the UI/report
    return SlotDecision(
        action="ASK",
        question_id=question.id,
        question_text=rendered,
        mandatory=question.mandatory,
        reason=unresolved,
        unresolved_reason=unresolved,
        required=required,
        ranking_score=None if row is None else row.score,
        selected=True if row is None else row.selected,
        evidence_refs=evidence_refs,
    )


def _row(ranking: RankingResult, question_id: str) -> RankedQuestion | None:
    """
    Helper: Find the RankedQuestion entry for a given question_id.
    Returns None if not found.
    """
    for item in ranking.ranked:
        if item.question_id == question_id:
            return item
    return None
