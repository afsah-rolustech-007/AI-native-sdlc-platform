"""Errors for the requirements engine. Fail closed — never look like a valid spec."""

from __future__ import annotations


class RequirementsEngineError(Exception):
    """Base error. Callers must not catch this to invent requirements."""


class ExtractError(RequirementsEngineError):
    """Structured extraction failed to produce a valid ClaimSet."""


class QuestionBankError(RequirementsEngineError):
    """Malformed or inconsistent question-bank config."""


class PredicateError(QuestionBankError):
    """`applies_if` is not a recognized declarative predicate."""


class CycleError(QuestionBankError):
    """`depends_on` graph contains a cycle — a config bug, not a runtime loop."""


class EvidencePlanError(QuestionBankError):
    """YAML `evidence_plan` is missing fields or names an unknown signal."""


class SnapshotError(RequirementsEngineError):
    """Repository is unindexed, stale, or the snapshot cannot be built safely."""


class RetrievalError(RequirementsEngineError):
    """Targeted retrieval stopped because an evidence source failed closed."""
