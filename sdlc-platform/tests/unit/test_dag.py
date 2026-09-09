"""DAG activation, unknown≠false, mid-session re-evaluation."""

from __future__ import annotations

from common.task import WorkType
from requirements_engine.claims import Claim, ClaimKind, ClaimSet, EpistemicStatus, Provenance
from requirements_engine.context import WorkflowContext
from requirements_engine.dag import QuestionQueue
from requirements_engine.question_bank import default_bank_path, load_question_bank


def _queue(**context_fields: object) -> QuestionQueue:
    questions = load_question_bank(default_bank_path())
    return QuestionQueue(questions, WorkflowContext(**context_fields))  # type: ignore[arg-type]


def test_auth_requirement_activates_qsec_chain() -> None:
    queue = _queue(work_type=WorkType.FEATURE, touches_auth=True)
    assert queue.activated_ids()[0] == "Q1"
    queue.answer("Q1", "Add SSO")
    assert "Qsec1" in queue.activated_ids()
    queue.answer("Qsec1", "SOC2")
    assert "Qsec2" in queue.activated_ids()
    queue.answer("Qsec2", "confidential")
    assert "Qsec3" in queue.activated_ids()


def test_bug_work_type_activates_bug_slots_not_feature_nfrs() -> None:
    queue = _queue(work_type=WorkType.BUG)
    assert queue.predicate_results()["Q4b"] is True
    assert queue.predicate_results()["Q5b"] is True
    assert queue.predicate_results()["Q6b"] is True
    assert queue.predicate_results()["Q4"] is False
    assert queue.predicate_results()["Q5"] is False
    assert queue.predicate_results()["Q6"] is False
    assert "Q4" not in queue.activated_ids()
    queue.answer("Q1", "Fix login 500")
    queue.answer("Q3", "200 instead of 500")
    assert "Q4b" in queue.activated_ids()
    assert "Q4" not in queue.activated_ids()


def test_unknown_touches_auth_keeps_security_eligible() -> None:
    unknown = _queue(touches_auth=None, touches_pii=None, touches_payments=None)
    known_false = _queue(touches_auth=False, touches_pii=False, touches_payments=False)
    assert unknown.predicate_results()["Qsec1"] is True
    assert known_false.predicate_results()["Qsec1"] is False
    unknown.answer("Q1", "unclear change")
    assert "Qsec1" in unknown.activated_ids()
    known_false.answer("Q1", "docs typo")
    assert "Qsec1" not in known_false.activated_ids()


def test_unknown_work_type_does_not_activate_feature_nfrs() -> None:
    queue = _queue(work_type=None)
    assert queue.predicate_results()["Q4"] is False
    assert queue.predicate_results()["Q4b"] is False


def test_database_slots_activate_after_mid_session_answer() -> None:
    queue = _queue(work_type=WorkType.FEATURE, has_database_changes=None)
    assert queue.predicate_results()["Qdb1"] is False
    queue.answer("Q1", "add a users table", context_updates={"has_database_changes": True})
    assert queue.context.has_database_changes is True
    assert "Qdb1" in queue.activated_ids()


def test_claims_can_hint_auth_without_setting_false() -> None:
    queue = _queue()
    assert queue.context.touches_auth is None
    queue.apply_claims(
        ClaimSet(
            claims=[
                Claim(
                    id="c1",
                    kind=ClaimKind.FUNCTIONAL,
                    text="Add authentication using the existing backend",
                    status=EpistemicStatus.DECISION,
                    provenance=Provenance(source="request", ref="c1"),
                )
            ]
        )
    )
    assert queue.context.touches_auth is True
    queue.answer("Q1", "Add authentication")
    assert "Qsec1" in queue.activated_ids()


def test_mandatory_flags_are_present_on_core_and_security() -> None:
    queue = _queue()
    by_id = {question.id: question for question in queue.applicable()}
    assert by_id["Q1"].mandatory is True
    queue = _queue(touches_auth=True)
    queue.answer("Q1", "auth")
    activated = {question.id: question for question in queue.activated()}
    assert activated["Qsec1"].mandatory is True


def test_microservices_chain_needs_both_flags() -> None:
    incomplete = _queue(repo_architecture="microservices", affected_modules=None)
    complete = _queue(repo_architecture="microservices", affected_modules=3)
    assert incomplete.predicate_results()["Qint1"] is False
    complete.answer("Q1", "split billing")
    assert "Qint1" in complete.activated_ids()
