"""Group C evaluate_slots: AUTO vs ASK, no LLM, no hidden RI."""

from __future__ import annotations

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
)
from requirements_engine.decide import evaluate_slots
from requirements_engine.manifests import ManifestFact
from requirements_engine.models import Question
from requirements_engine.question_bank import default_bank_path, load_question_bank
from requirements_engine.rank import RankConfig
from requirements_engine.snapshot import SessionRepoSnapshot


def _snapshot() -> SessionRepoSnapshot:
    return SessionRepoSnapshot(
        repo_root="/tmp/repo",
        catalog_hash="hash1",
        file_count=10,
        index_state="fresh",
        languages=["python"],
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg"])],
    )


def test_evaluate_auto_and_ask_split() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    claims = ClaimSet(
        claims=[
            Claim(
                id="c1",
                kind=ClaimKind.OBJECTIVE,
                text="Add billing export",
                status=EpistemicStatus.UNKNOWN,
                provenance=Provenance(source="request", ref="c1"),
            )
        ]
    )
    report = evaluate_slots(
        [bank["Qstack1"], bank["Q1"], bank["Qsec1"]],
        claims,
        snapshot=_snapshot(),
        config=RankConfig(human_question_budget=12),
    )
    auto_ids = {item.question_id for item in report.auto}
    assert "Qstack1" in auto_ids
    assert report.auto[0].action == "AUTO"
    assert report.auto[0].status == "fact"
    ask_ids = {item.question_id for item in report.ask if item.selected}
    assert "Q1" in ask_ids
    assert "Qsec1" in ask_ids
    assert all(item.action == "ASK" for item in report.ask)


def test_semantic_inference_cannot_auto_answer() -> None:
    slot = Question(
        id="Qrel",
        text="Which code in the repository currently implements login?",
        category="functional",
        applies_if={"always": True},
        evidence_plan={
            "need": "existing_auth_module",
            "methods": [{"signal": "semantic", "query": "login", "extractor": "service_exists"}],
            "accept_as": "inference",
        },
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="semantic",
            query="login",
            refs=["auth/service.py::AuthService.login"],
            accept_as="inference",
            result_count=1,
        )
    ]
    report = evaluate_slots([slot], ClaimSet(), evidence=evidence)
    assert report.auto == []
    assert report.ask[0].action == "ASK"
    assert report.ask[0].selected is True
