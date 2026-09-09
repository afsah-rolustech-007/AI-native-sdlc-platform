"""Question DAG: applicability, dependency order, re-evaluation after answers."""

from __future__ import annotations

from typing import Any, Literal

from requirements_engine.claims import ClaimSet
from requirements_engine.context import WorkflowContext, apply_claim_hints, apply_context_updates
from requirements_engine.exceptions import QuestionBankError
from requirements_engine.models import Question, SlotAnswer
from requirements_engine.predicates import evaluate_predicate


class QuestionQueue:
    """Activated unanswered slots. Does not call RI or decide what to ask a human."""

    def __init__(self, questions: list[Question], context: WorkflowContext | None = None) -> None:
        self._questions = {question.id: question for question in questions}
        if len(self._questions) != len(questions):
            raise QuestionBankError("duplicate ids passed to QuestionQueue")
        self.context = context or WorkflowContext()
        self.answers: dict[str, SlotAnswer] = {}

    def apply_claims(self, claim_set: ClaimSet) -> None:
        self.context = apply_claim_hints(self.context, claim_set)

    def get(self, question_id: str) -> Question:
        if question_id not in self._questions:
            raise KeyError(f"unknown question id: {question_id}")
        return self._questions[question_id]

    def answer(
        self,
        question_id: str,
        text: str,
        *,
        context_updates: dict[str, Any] | None = None,
        source: Literal["human", "auto"] = "human",
    ) -> None:
        if question_id not in self._questions:
            raise KeyError(f"unknown question id: {question_id}")
        self.answers[question_id] = SlotAnswer(
            question_id=question_id, text=text, source=source
        )
        if context_updates:
            self.context = apply_context_updates(self.context, context_updates)

    def applicable(self) -> list[Question]:
        return [
            question
            for question in self._ordered()
            if evaluate_predicate(question.applies_if, self.context)
        ]

    def activated(self) -> list[Question]:
        """Applicable, dependency-satisfied, not yet answered — topological order."""
        answered = set(self.answers)
        applicable_ids = {question.id for question in self.applicable()}
        activated: list[Question] = []
        for question in self._ordered():
            if question.id not in applicable_ids or question.id in answered:
                continue
            blocking = [dep for dep in question.depends_on if dep in applicable_ids]
            if all(dep in answered for dep in blocking):
                activated.append(question)
        return activated

    def activated_ids(self) -> list[str]:
        return [question.id for question in self.activated()]

    def predicate_results(self) -> dict[str, bool]:
        return {
            question.id: evaluate_predicate(question.applies_if, self.context)
            for question in self._ordered()
        }

    def _ordered(self) -> list[Question]:
        pending = {qid: set(question.depends_on) for qid, question in self._questions.items()}
        ready = sorted(qid for qid, deps in pending.items() if not deps)
        ordered: list[str] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            newly = []
            for qid, deps in pending.items():
                if current in deps:
                    deps.remove(current)
                    if not deps:
                        newly.append(qid)
            ready.extend(sorted(newly))
        return [self._questions[qid] for qid in ordered]
