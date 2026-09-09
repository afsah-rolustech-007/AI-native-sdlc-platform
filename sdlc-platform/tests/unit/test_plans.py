"""EvidencePlan YAML validation — unknown signals fail at load."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from requirements_engine.exceptions import EvidencePlanError, QuestionBankError
from requirements_engine.plans import parse_evidence_plan
from requirements_engine.question_bank import load_question_bank


def test_evidence_plan_validation_accepts_need_driven_methods() -> None:
    plan = parse_evidence_plan(
        {
            "need": "existing_auth_module",
            "methods": [
                {"signal": "snapshot", "query": "auth", "extractor": "service_exists"},
                {
                    "signal": "symbol",
                    "symbol_id": "auth/service.py::AuthService",
                    "extractor": "symbol_exists",
                },
                {"signal": "lexical", "query": "AuthService", "budget": 1},
            ],
            "accept_as": "fact",
            "on_insufficient": "unknown",
            "max_ri_calls": 4,
        }
    )
    assert plan.need == "existing_auth_module"
    assert [method.signal for method in plan.methods] == ["snapshot", "symbol", "lexical"]
    assert plan.accept_as == "fact"


def test_unknown_signal_is_rejected() -> None:
    with pytest.raises(EvidencePlanError, match="unknown signal"):
        parse_evidence_plan(
            {
                "need": "anything",
                "methods": [{"signal": "rrf"}],
            }
        )


def test_semantic_only_plan_cannot_accept_as_fact() -> None:
    with pytest.raises(EvidencePlanError, match="semantic-only"):
        parse_evidence_plan(
            {
                "need": "related_code",
                "methods": [{"signal": "semantic", "query": "session expiry"}],
                "accept_as": "fact",
            }
        )


def test_unknown_extractor_is_rejected() -> None:
    with pytest.raises(EvidencePlanError, match="unknown extractor"):
        parse_evidence_plan(
            {
                "need": "x",
                "methods": [{"signal": "snapshot", "extractor": "llm_judge"}],
            }
        )


def test_question_bank_rejects_unknown_signal(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "Q1",
                    "text": "obj",
                    "category": "business_objective",
                    "applies_if": {"always": True},
                    "evidence_plan": {
                        "need": "x",
                        "methods": [{"signal": "fusion"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionBankError, match="unknown signal"):
        load_question_bank(path)
