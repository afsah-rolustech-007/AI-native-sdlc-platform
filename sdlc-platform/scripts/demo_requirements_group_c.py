"""Phase 04 Group C checkpoint: classify / auto-answer / rank. No engine.py, no RI.

  uv run python scripts/demo_requirements_group_c.py
"""

from __future__ import annotations

from typing import Literal

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
    has_contradiction,
    is_fact_plus_decision,
)
from requirements_engine.context import WorkflowContext
from requirements_engine.dag import QuestionQueue
from requirements_engine.decide import DecisionReport, evaluate_slots
from requirements_engine.manifests import ManifestFact
from requirements_engine.question_bank import default_bank_path, load_question_bank
from requirements_engine.rank import RankConfig
from requirements_engine.snapshot import ServiceSlice, SessionRepoSnapshot


def _claim(
    claim_id: str,
    text: str,
    *,
    kind: ClaimKind = ClaimKind.FUNCTIONAL,
    status: EpistemicStatus = EpistemicStatus.UNKNOWN,
    source: Literal["request", "engineer", "repository", "derived", "assumption"] = "request",
) -> Claim:
    return Claim(
        id=claim_id,
        kind=kind,
        text=text,
        status=status,
        provenance=Provenance(source=source, ref=claim_id),
    )


def _snapshot() -> SessionRepoSnapshot:
    return SessionRepoSnapshot(
        repo_root="/tmp/demo-repo",
        catalog_hash="demo-hash",
        file_count=14,
        index_state="fresh",
        languages=["python"],
        services=[
            ServiceSlice(name="auth", files=3, key_symbols=["auth/service.py::AuthService"]),
            ServiceSlice(name="billing", files=2),
        ],
        database_entities=["storage/models.py::User"],
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg", "fastapi"])],
    )


def _print_report(title: str, report: DecisionReport) -> None:
    print(f"\n=== {title} ===")
    print("classification:")
    for claim in report.classified.claims:
        print(
            f"  {claim.id}: {claim.status.value} source={claim.provenance.source} "
            f"via={claim.provenance.retrieved_via} {claim.text!r}"
        )
    for note in report.notes:
        print(f"  note {note.claim_id}: {note.reason}")
    print(f"FACT+DECISION (not contradiction): {is_fact_plus_decision(report.classified)}")
    print(f"has CONTRADICTION: {has_contradiction(report.classified)}")
    print("AUTO:")
    if not report.auto:
        print("  (none)")
    for item in report.auto:
        print(
            f"  {item.question_id} status={item.status} confidence={item.confidence} "
            f"answer={None if item.auto_answer is None else item.auto_answer.answer!r}"
        )
        print(f"    evidence={item.evidence_refs} reason={item.reason}")
    print("ASK (selected):")
    selected = [item for item in report.ask if item.selected]
    if not selected:
        print("  (none)")
    for item in selected:
        print(
            f"  {item.question_id} mandatory={item.mandatory} score={item.ranking_score} "
            f"required={item.required}"
        )
        print(f"    reason={item.reason}")
    if report.ranking is not None:
        print("ranking:")
        for row in report.ranking.ranked:
            print(
                f"  {row.question_id} score={row.score} selected={row.selected} "
                f"mandatory={row.mandatory} deferred={row.deferred} :: {row.reason}"
            )


def main() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    snapshot = _snapshot()

    # A. Known repo fact → AUTO languages + declared PostgreSQL
    repo_claims = ClaimSet(
        claims=[
            _claim(
                "c-pg",
                "PostgreSQL is configured",
                kind=ClaimKind.REPO_DEPENDENT,
                source="repository",
            ),
            _claim("c-obj", "Add an export job", kind=ClaimKind.OBJECTIVE),
        ]
    )
    report_a = evaluate_slots(
        [bank["Qstack1"], bank["Qdb_tech"], bank["Q1"]],
        repo_claims,
        snapshot=snapshot,
    )
    _print_report("A. Known repo fact → AUTO", report_a)

    # B. User MongoDB DECISION preserved next to PostgreSQL FACT
    mixed = ClaimSet(
        claims=[
            _claim(
                "c-pg",
                "PostgreSQL is configured",
                kind=ClaimKind.REPO_DEPENDENT,
                source="repository",
            ),
            _claim("c-mongo", "Use MongoDB instead", status=EpistemicStatus.DECISION),
        ]
    )
    report_b = evaluate_slots(
        [bank["Qdb_tech"], bank["Q1"]],
        mixed,
        snapshot=snapshot,
    )
    _print_report("B. User MongoDB DECISION + repo PostgreSQL FACT", report_b)

    # C. Semantic evidence → INFERENCE, cannot AUTO
    semantic_claims = ClaimSet(
        claims=[
            _claim(
                "c-sem",
                "code about session expiry",
                kind=ClaimKind.REPO_DEPENDENT,
                source="repository",
            )
        ]
    )
    semantic_evidence = [
        EvidenceRecord(
            id="e-sem",
            signal="semantic",
            query="session expiry",
            refs=["auth/tokens.py::verify_token"],
            excerpt="verify bearer token",
            accept_as="inference",
            result_count=1,
        )
    ]
    report_c = evaluate_slots(
        [bank["Q1"]],
        semantic_claims,
        snapshot=snapshot,
        evidence=semantic_evidence,
    )
    _print_report("C. Semantic evidence → INFERENCE, question remains", report_c)

    # D. Security: unknown auth/PII/payments → Qsec1 eligible
    queue = QuestionQueue(list(bank.values()), WorkflowContext())
    queue.apply_claims(ClaimSet(claims=[_claim("c1", "touch something sensitive")]))
    queue.answer("Q1", "unclear change")
    report_d = evaluate_slots(
        [bank["Qsec1"], bank["Qsec2"]],
        ClaimSet(claims=[_claim("c1", "touch something sensitive")]),
        snapshot=snapshot,
        evidence=[
            EvidenceRecord(
                id="e-jwt",
                signal="lexical",
                query="JWT",
                refs=["auth/tokens.py:3"],
                excerpt="JWT middleware",
                accept_as="fact",
                result_count=1,
            )
        ],
    )
    _print_report("D. Security (JWT in repo does not answer compliance)", report_d)
    print(f"DAG activated after Q1 with unknown flags: {queue.activated_ids()}")

    # E. Ranking several unresolved questions
    unresolved = ClaimSet(claims=[_claim("c1", "vague one-liner")])
    report_e = evaluate_slots(
        [bank["Q1"], bank["Q2"], bank["Qsec1"], bank["Q4"], bank["Qstack1"], bank["Qdep1"]],
        unresolved,
        snapshot=snapshot,
        config=RankConfig(human_question_budget=3, asking_cost_limit=1.0),
    )
    _print_report("E. Ranking (mandatory kept, optional by additive score)", report_e)


if __name__ == "__main__":
    main()
