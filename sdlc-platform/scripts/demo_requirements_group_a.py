"""Group A checkpoint: hand-built ClaimSets, no Repository Intelligence.

  uv run python scripts/demo_requirements_group_a.py
"""

from __future__ import annotations

import json
from typing import Literal

from common.task import WorkType
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
    is_fact_plus_decision,
)
from requirements_engine.context import WorkflowContext
from requirements_engine.dag import QuestionQueue
from requirements_engine.project import project_spec
from requirements_engine.question_bank import default_bank_path, load_question_bank


def _claim(
    claim_id: str,
    text: str,
    *,
    kind: ClaimKind = ClaimKind.FUNCTIONAL,
    status: EpistemicStatus = EpistemicStatus.DECISION,
    source: Literal["request", "engineer", "repository", "derived", "assumption"] = "request",
) -> Claim:
    return Claim(
        id=claim_id,
        kind=kind,
        text=text,
        status=status,
        provenance=Provenance(source=source, ref=claim_id),
    )


def _print_scenario(title: str, claim_set: ClaimSet, queue: QuestionQueue) -> None:
    print(f"\n=== {title} ===")
    print("claims:")
    for claim in claim_set.claims:
        print(f"  {claim.id}: kind={claim.kind.value} status={claim.status.value} {claim.text!r}")
    print(f"FACT+DECISION (not contradiction): {is_fact_plus_decision(claim_set)}")
    print("predicate Qsec1 / Q4 / Q4b / Qdb1:")
    results = queue.predicate_results()
    for qid in ("Qsec1", "Q4", "Q4b", "Qdb1"):
        print(f"  {qid}: {results[qid]}")
    print(f"activated: {queue.activated_ids()}")
    spec = project_spec(claim_set)
    print("RequirementsSpec:")
    print(json.dumps(spec, indent=2, default=str))


def main() -> None:
    bank = load_question_bank(default_bank_path())

    auth_claims = ClaimSet(
        claims=[
            _claim("c1", "Add authentication using the existing backend"),
            _claim(
                "c2",
                "JWT middleware exists",
                kind=ClaimKind.REPO_DEPENDENT,
                status=EpistemicStatus.FACT,
                source="repository",
            ),
        ],
        raw_request="Add authentication using the existing backend",
    )
    auth_queue = QuestionQueue(bank, WorkflowContext(work_type=WorkType.FEATURE))
    auth_queue.apply_claims(auth_claims)
    auth_queue.answer("Q1", "Add authentication")
    _print_scenario("1. Auth requirement", auth_claims, auth_queue)

    bug_claims = ClaimSet(
        claims=[_claim("c1", "Login returns 500 for expired sessions")],
        raw_request="login 500",
    )
    bug_queue = QuestionQueue(
        bank,
        WorkflowContext(
            work_type=WorkType.BUG,
            touches_auth=True,
            touches_pii=False,
            touches_payments=False,
        ),
    )
    bug_queue.answer("Q1", "Fix login 500")
    bug_queue.answer("Q2", "End user")
    bug_queue.answer("Q3", "Login succeeds for expired session")
    _print_scenario("2. Bug work_type", bug_claims, bug_queue)

    unknown_claims = ClaimSet(
        claims=[_claim("c1", "Improve the billing page copy", status=EpistemicStatus.UNKNOWN)],
        raw_request="improve billing",
    )
    unknown_queue = QuestionQueue(bank, WorkflowContext())
    unknown_queue.answer("Q1", "unclear")
    _print_scenario("3. Unknown touches_auth=None", unknown_claims, unknown_queue)

    db_queue = QuestionQueue(bank, WorkflowContext(work_type=WorkType.FEATURE))
    print("\n=== mid-session has_database_changes ===")
    print(f"before: Qdb1={db_queue.predicate_results()['Qdb1']} activated={db_queue.activated_ids()}")
    db_queue.answer("Q1", "add users table", context_updates={"has_database_changes": True})
    print(f"after:  Qdb1={db_queue.predicate_results()['Qdb1']} activated={db_queue.activated_ids()}")


if __name__ == "__main__":
    main()
