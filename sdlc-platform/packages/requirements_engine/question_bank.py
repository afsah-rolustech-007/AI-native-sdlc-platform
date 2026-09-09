"""Load and validate YAML question-bank policy (Phase 04 §02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from requirements_engine.exceptions import CycleError, QuestionBankError
from requirements_engine.models import E4_CATEGORIES, Question, category_defaults
from requirements_engine.plans import parse_evidence_plan
from requirements_engine.predicates import validate_predicate

_SCORE_FIELDS = ("impact", "risk", "information_value")


def load_question_bank(path: str | Path) -> list[Question]:
    """Parse a file or a directory of YAML files. Fail loudly on config bugs."""
    root = Path(path)
    if not root.exists():
        raise QuestionBankError(f"question bank not found: {root}")
    documents = _read_documents(root)
    questions = [_question_from_raw(item, source) for source, item in documents]
    _validate_collection(questions)
    return questions


def default_bank_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "question_bank"


def _read_documents(root: Path) -> list[tuple[str, dict[str, Any]]]:
    files = [root] if root.is_file() else sorted(root.glob("*.yaml"))
    if not files:
        raise QuestionBankError(f"no YAML files in {root}")
    rows: list[tuple[str, dict[str, Any]]] = []
    for file in files:
        loaded = yaml.safe_load(file.read_text(encoding="utf-8"))
        if loaded is None:
            raise QuestionBankError(f"{file} is empty")
        items = loaded if isinstance(loaded, list) else loaded.get("questions")
        if not isinstance(items, list):
            raise QuestionBankError(f"{file} must be a list or {{questions: [...]}}")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise QuestionBankError(f"{file} item {index} is not a mapping")
            rows.append((f"{file.name}[{index}]", item))
    return rows


def _question_from_raw(raw: dict[str, Any], source: str) -> Question:
    required = ("id", "text", "category", "applies_if")
    missing = [key for key in required if key not in raw]
    if missing:
        raise QuestionBankError(f"{source} missing {missing}")
    category = raw["category"]
    if category not in E4_CATEGORIES:
        raise QuestionBankError(f"{source} category {category!r} is not an §E.4 category")
    validate_predicate(raw["applies_if"], path=f"{source}.applies_if")
    plan = raw.get("evidence_plan")
    if plan is not None:
        if not isinstance(plan, dict):
            raise QuestionBankError(f"{source}.evidence_plan must be a mapping or null")
        parse_evidence_plan(plan)
    impact, risk, value = category_defaults(category)
    defaults = (impact, risk, value)
    scores = {
        field: float(raw.get(field, default))
        for field, default in zip(_SCORE_FIELDS, defaults, strict=True)
    }
    for field, score in scores.items():
        if not 0.0 <= score <= 1.0:
            raise QuestionBankError(f"{source}.{field} must be in [0, 1]")
    depends_on = raw.get("depends_on") or []
    if not isinstance(depends_on, list) or not all(isinstance(item, str) for item in depends_on):
        raise QuestionBankError(f"{source}.depends_on must be a list of ids")
    asking_cost = float(raw.get("asking_cost", 0.0))
    if asking_cost < 0:
        raise QuestionBankError(f"{source}.asking_cost must be >= 0")
    return Question(
        id=str(raw["id"]),
        text=str(raw["text"]),
        category=category,
        applies_if=raw["applies_if"],
        depends_on=list(depends_on),
        mandatory=bool(raw.get("mandatory", False)),
        evidence_plan=plan,
        impact=scores["impact"],
        risk=scores["risk"],
        information_value=scores["information_value"],
        asking_cost=asking_cost,
        render=raw.get("render"),
    )


def _validate_collection(questions: list[Question]) -> None:
    ids = [question.id for question in questions]
    dupes = sorted({item for item in ids if ids.count(item) > 1})
    if dupes:
        raise QuestionBankError(f"duplicate question ids: {dupes}")
    known = set(ids)
    for question in questions:
        missing = [ref for ref in question.depends_on if ref not in known]
        if missing:
            raise QuestionBankError(f"{question.id} depends_on unknown ids: {missing}")
        if question.id in question.depends_on:
            raise QuestionBankError(f"{question.id} depends on itself")
    _assert_acyclic(questions)
    present = {question.category for question in questions}
    missing_cats = sorted(E4_CATEGORIES - present)
    if missing_cats:
        raise QuestionBankError(f"question bank missing §E.4 categories: {missing_cats}")


def _assert_acyclic(questions: list[Question]) -> None:
    pending = {question.id: set(question.depends_on) for question in questions}
    ready = [qid for qid, deps in pending.items() if not deps]
    seen = 0
    while ready:
        current = ready.pop()
        seen += 1
        for qid, deps in pending.items():
            if current in deps:
                deps.remove(current)
                if not deps:
                    ready.append(qid)
    if seen != len(questions):
        cyclic = sorted(qid for qid, deps in pending.items() if deps)
        raise CycleError(f"cyclic depends_on among: {cyclic}")
