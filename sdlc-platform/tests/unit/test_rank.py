"""Group C ranking: additive score, mandatory gate, asking_cost gate."""

from __future__ import annotations

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
)
from requirements_engine.models import Question
from requirements_engine.rank import RankConfig, rank_questions


def _q(
    slot_id: str,
    *,
    mandatory: bool = False,
    impact: float = 0.5,
    risk: float = 0.5,
    information_value: float = 0.5,
    asking_cost: float = 0.0,
    category: str = "functional",
    text: str | None = None,
    depends_on: list[str] | None = None,
) -> Question:
    return Question(
        id=slot_id,
        text=text or f"Question {slot_id}?",
        category=category,
        applies_if={"always": True},
        depends_on=depends_on or [],
        mandatory=mandatory,
        impact=impact,
        risk=risk,
        information_value=information_value,
        asking_cost=asking_cost,
    )


def _unknown_claims() -> ClaimSet:
    return ClaimSet(
        claims=[
            Claim(
                id="c1",
                kind=ClaimKind.UNKNOWN,
                text="unclear change",
                status=EpistemicStatus.UNKNOWN,
                provenance=Provenance(source="request", ref="c1"),
            )
        ]
    )


def test_evidence_sufficient_slot_scores_zero() -> None:
    questions = [_q("Qstack1", impact=0.9, risk=0.9, information_value=0.9)]
    result = rank_questions(questions, _unknown_claims(), auto_answered={"Qstack1"})
    row = result.ranked[0]
    assert row.score == 0.0
    assert row.selected is False
    assert "suffices" in row.reason
    assert "Qstack1" not in result.selected_ids


def test_mandatory_security_cannot_be_ranked_away() -> None:
    questions = [
        _q("Qopt", impact=1.0, risk=1.0, information_value=1.0),
        _q(
            "Qsec1",
            mandatory=True,
            impact=0.1,
            risk=0.1,
            information_value=0.1,
            category="security_compliance",
            text="What compliance requirements apply?",
        ),
    ]
    result = rank_questions(questions, _unknown_claims(), config=RankConfig(human_question_budget=1))
    assert "Qsec1" in result.selected_ids
    sec = next(row for row in result.ranked if row.question_id == "Qsec1")
    assert sec.selected is True
    assert sec.mandatory is True


def test_asking_cost_cannot_suppress_mandatory() -> None:
    questions = [
        _q(
            "Qsec1",
            mandatory=True,
            asking_cost=99.0,
            category="security_compliance",
            text="What compliance requirements apply?",
        ),
        _q("Qopt", asking_cost=99.0, impact=1.0, risk=1.0, information_value=1.0),
    ]
    result = rank_questions(
        questions, _unknown_claims(), config=RankConfig(asking_cost_limit=1.0)
    )
    by_id = {row.question_id: row for row in result.ranked}
    assert by_id["Qsec1"].selected is True
    assert by_id["Qsec1"].deferred is False
    assert by_id["Qopt"].deferred is True
    assert by_id["Qopt"].selected is False
    assert "Qsec1" in result.selected_ids
    assert "Qopt" not in result.selected_ids


def test_unknown_values_keep_questions_eligible() -> None:
    questions = [_q("Q2", mandatory=True, text="Who is the user of this change?")]
    result = rank_questions(questions, _unknown_claims())
    assert result.ranked[0].unresolvedness == 1.0
    assert result.ranked[0].selected is True


def test_ranking_is_deterministic() -> None:
    questions = [
        _q("Qb", impact=0.4, risk=0.4, information_value=0.4),
        _q("Qa", impact=0.8, risk=0.2, information_value=0.5),
        _q("Qc", impact=0.8, risk=0.2, information_value=0.5),
    ]
    first = rank_questions(questions, _unknown_claims())
    second = rank_questions(questions, _unknown_claims())
    assert first.selected_ids == second.selected_ids
    assert [row.score for row in first.ranked] == [row.score for row in second.ranked]
    assert first.model_dump() == second.model_dump()


def test_same_score_ties_break_by_id() -> None:
    questions = [
        _q("Qc", impact=0.5, risk=0.5, information_value=0.5),
        _q("Qa", impact=0.5, risk=0.5, information_value=0.5),
    ]
    result = rank_questions(
        questions, _unknown_claims(), config=RankConfig(human_question_budget=1)
    )
    assert result.selected_ids == ["Qa"]


def test_mandatory_keeps_depends_on_order() -> None:
    questions = [
        _q("Qsec2", mandatory=True, depends_on=["Qsec1"], text="How should data be classified?"),
        _q("Qsec1", mandatory=True, text="What compliance requirements apply?"),
        _q("Qopt", impact=1.0, risk=1.0, information_value=1.0),
    ]
    result = rank_questions(
        questions, _unknown_claims(), config=RankConfig(human_question_budget=1)
    )
    assert result.selected_ids[:2] == ["Qsec1", "Qsec2"]
    assert "Qopt" not in result.selected_ids
