"""Question-bank YAML loading and config validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from requirements_engine.exceptions import CycleError, PredicateError, QuestionBankError
from requirements_engine.models import E4_CATEGORIES
from requirements_engine.question_bank import default_bank_path, load_question_bank


def test_default_bank_loads_and_covers_e4_categories() -> None:
    questions = load_question_bank(default_bank_path())
    cats = {question.category for question in questions}
    assert cats == set(E4_CATEGORIES)
    ids = [question.id for question in questions]
    assert "Q1" in ids
    assert "Qsec1" in ids
    assert "Q4b" in ids
    assert "Qdb1" in ids
    qsec1 = next(question for question in questions if question.id == "Qsec1")
    assert qsec1.mandatory is True
    assert qsec1.evidence_plan is not None
    assert qsec1.evidence_plan["need"] == "existing_auth_module"


def test_broken_depends_on_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "Q1",
                    "text": "obj",
                    "category": "business_objective",
                    "applies_if": {"always": True},
                    "depends_on": ["Qmissing"],
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionBankError, match="unknown ids"):
        load_question_bank(path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    item = {
        "id": "Q1",
        "text": "obj",
        "category": "business_objective",
        "applies_if": {"always": True},
    }
    path.write_text(yaml.safe_dump([item, item]), encoding="utf-8")
    with pytest.raises(QuestionBankError, match="duplicate"):
        load_question_bank(path)


def test_cycle_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "A",
                    "text": "a",
                    "category": "functional",
                    "applies_if": {"always": True},
                    "depends_on": ["B"],
                },
                {
                    "id": "B",
                    "text": "b",
                    "category": "functional",
                    "applies_if": {"always": True},
                    "depends_on": ["A"],
                },
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(CycleError, match="cyclic"):
        load_question_bank(path)


def test_malformed_predicate_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "Q1",
                    "text": "obj",
                    "category": "business_objective",
                    "applies_if": {"unknown_op": True},
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(PredicateError):
        load_question_bank(path)


def test_unknown_category_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bank.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "Q1",
                    "text": "obj",
                    "category": "vibes",
                    "applies_if": {"always": True},
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionBankError, match="category"):
        load_question_bank(path)
