"""Group C render: templates only, no LLM."""

from __future__ import annotations

from requirements_engine.claims import EvidenceRecord
from requirements_engine.models import Question
from requirements_engine.render import render_question


def test_render_interpolates_evidence_placeholder() -> None:
    question = Question(
        id="Q1",
        text="What is the primary objective?",
        category="business_objective",
        applies_if={"always": True},
        render="Primary objective. Evidence: {evidence}",
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="lexical",
            query="export",
            refs=["billing/invoices.py::Invoice"],
            accept_as="fact",
            result_count=1,
        )
    ]
    rendered = render_question(question, evidence)
    assert "billing/invoices.py::Invoice" in rendered
    assert "{evidence}" not in rendered


def test_missing_template_appends_refs() -> None:
    question = Question(
        id="Q2",
        text="Who is the user?",
        category="functional",
        applies_if={"always": True},
    )
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="snapshot",
            query="auth",
            refs=["service:auth"],
            accept_as="fact",
            result_count=1,
        )
    ]
    rendered = render_question(question, evidence)
    assert rendered.startswith("Who is the user?")
    assert "- service:auth" in rendered
