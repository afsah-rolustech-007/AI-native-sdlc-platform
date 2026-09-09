"""Group C: auto-answer policy. Repo facts are not user decisions."""

from __future__ import annotations

from requirements_engine.auto_answer import try_answer
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
)
from requirements_engine.manifests import ManifestFact
from requirements_engine.models import Question
from requirements_engine.question_bank import default_bank_path, load_question_bank
from requirements_engine.snapshot import ServiceSlice, SessionRepoSnapshot


def _snapshot(**kwargs: object) -> SessionRepoSnapshot:
    return SessionRepoSnapshot(
        repo_root="/tmp/repo",
        catalog_hash="hash1",
        file_count=10,
        index_state="fresh",
        **kwargs,  # type: ignore[arg-type]
    )


def _slot(
    slot_id: str,
    text: str,
    *,
    category: str = "functional",
    need: str = "repo_languages",
    extractor: str = "languages_from_snapshot",
    query: str | None = None,
    mandatory: bool = False,
) -> Question:
    method: dict[str, object] = {"signal": "snapshot", "extractor": extractor}
    if query:
        method["query"] = query
    return Question(
        id=slot_id,
        text=text,
        category=category,
        applies_if={"always": True},
        mandatory=mandatory,
        evidence_plan={
            "need": need,
            "methods": [method],
            "accept_as": "fact",
        },
    )


def test_deterministic_repo_fact_is_auto_answered() -> None:
    snapshot = _snapshot(languages=["python"])
    slot = _slot(
        "Qstack1",
        "Which programming languages does the repository currently use?",
        need="repo_languages",
        extractor="languages_from_snapshot",
    )
    answer = try_answer(slot, ClaimSet(), snapshot, [])
    assert answer is not None
    assert answer.status == "fact"
    assert answer.confidence == "high"
    assert "python" in answer.answer
    assert answer.evidence_refs


def test_postgres_declaration_is_auto_answered() -> None:
    snapshot = _snapshot(
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg", "fastapi"])]
    )
    slot = _slot(
        "Qdb_tech",
        "Which database technology does the repository currently declare?",
        category="data_integrity",
        need="declared_database",
        extractor="declared_database",
    )
    answer = try_answer(slot, ClaimSet(), snapshot, [])
    assert answer is not None
    assert "postgresql" in answer.answer.lower()
    assert answer.status == "fact"


def test_business_objective_is_never_auto_answered() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    snapshot = _snapshot(languages=["python"])
    assert try_answer(bank["Q1"], ClaimSet(), snapshot, []) is None


def test_sla_is_never_auto_answered() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    snapshot = _snapshot(languages=["python"])
    assert try_answer(bank["Q6"], ClaimSet(), snapshot, []) is None
    assert try_answer(bank["Q4"], ClaimSet(), snapshot, []) is None


def test_compliance_requires_engineer_decision() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    snapshot = _snapshot(
        services=[ServiceSlice(name="auth", files=2, key_symbols=["auth/service.py::AuthService"])]
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="lexical",
            query="JWT",
            refs=["auth/tokens.py:3"],
            excerpt="issue JWT",
            accept_as="fact",
            result_count=1,
        )
    ]
    assert try_answer(bank["Qsec1"], ClaimSet(), snapshot, evidence) is None
    assert try_answer(bank["Qsec3"], ClaimSet(), snapshot, evidence) is None


def test_jwt_in_repo_does_not_decide_auth_method() -> None:
    slot = _slot(
        "Qauth_method",
        "Which authentication method should we use?",
        category="functional",
        need="existing_auth_module",
        extractor="identifier_in_snippet",
        query="JWT",
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="lexical",
            query="JWT",
            refs=["auth/tokens.py:3"],
            excerpt="JWT middleware",
            accept_as="fact",
            result_count=1,
        )
    ]
    assert try_answer(slot, ClaimSet(), _snapshot(), evidence) is None


def test_fastapi_dependency_is_not_a_user_decision() -> None:
    snapshot = _snapshot(
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["fastapi"])]
    )
    choice = _slot(
        "Qfw",
        "Which framework should we use?",
        need="declared_dependency",
        extractor="dependency_declared",
        query="fastapi",
    )
    assert try_answer(choice, ClaimSet(), snapshot, []) is None
    declared = _slot(
        "Qfw_repo",
        "Which web framework does the repository currently declare?",
        need="declared_dependency",
        extractor="dependency_declared",
        query="fastapi",
    )
    answer = try_answer(declared, ClaimSet(), snapshot, [])
    assert answer is not None
    assert "fastapi" in answer.answer.lower()
    assert answer.status == "fact"


def test_semantic_cannot_auto_answer() -> None:
    slot = _slot(
        "Qrel",
        "Which code in the repository currently implements login?",
        need="existing_auth_module",
        extractor="service_exists",
        query="auth",
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
    # Snapshot has no auth service, only semantic hits.
    assert try_answer(slot, ClaimSet(), _snapshot(), evidence) is None


def test_user_decision_is_not_overwritten_by_auto_answer() -> None:
    snapshot = _snapshot(
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg"])]
    )
    claims = ClaimSet(
        claims=[
            Claim(
                id="c-mongo",
                kind=ClaimKind.FUNCTIONAL,
                text="Use MongoDB instead",
                status=EpistemicStatus.DECISION,
                provenance=Provenance(source="request", ref="c-mongo"),
            )
        ]
    )
    requirement = _slot(
        "Qdb_choice",
        "Which database should we use?",
        category="data_integrity",
        need="declared_database",
        extractor="declared_database",
    )
    assert try_answer(requirement, claims, snapshot, []) is None
    situation = _slot(
        "Qdb_tech",
        "Which database technology does the repository currently declare?",
        category="data_integrity",
        need="declared_database",
        extractor="declared_database",
    )
    answer = try_answer(situation, claims, snapshot, [])
    assert answer is not None
    assert "postgresql" in answer.answer.lower()


def test_auth_service_existence_can_be_auto_answered() -> None:
    snapshot = _snapshot(
        services=[ServiceSlice(name="auth", files=2, key_symbols=["auth/service.py::AuthService"])]
    )
    slot = _slot(
        "Qauth_mod",
        "Which services already exist in the repository that this change may reuse?",
        need="existing_auth_module",
        extractor="service_exists",
        query="auth",
    )
    answer = try_answer(slot, ClaimSet(), snapshot, [])
    assert answer is not None
    assert "auth" in answer.answer.lower()
    assert any("service:auth" in ref for ref in answer.evidence_refs)


def test_migration_policy_slot_is_never_auto_answered() -> None:
    bank = {question.id: question for question in load_question_bank(default_bank_path())}
    snapshot = _snapshot(database_entities=["storage/models.py::User"])
    assert try_answer(bank["Qdb1"], ClaimSet(), snapshot, []) is None
