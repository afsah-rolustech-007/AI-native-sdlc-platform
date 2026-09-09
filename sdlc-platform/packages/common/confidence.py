"""§B.4 Confidence Model — exact formula, fail-closed, no imputation.

Weights are v1 pending Phase 15 logistic recalibration. This module is a pure
function. It must not call an LLM, touch a repository, or invent missing
signals (including `precedent_strength`).

Phase 04 implements and unit-tests this function. The Phase 04 requirements
loop does **not** call it to decide exit — that is `RequirementsSufficiency`.
Phase 05's Confidence Scorer is the first honest runtime caller.
"""

from __future__ import annotations

import math

# v1 weights from §B.4. Do not retune here.
WEIGHT_RETRIEVAL_COVERAGE = 0.35
WEIGHT_PRECEDENT_STRENGTH = 0.20
WEIGHT_VALIDATOR_AGREEMENT = 0.30
WEIGHT_STATIC_CHECK_CLEANLINESS = 0.15

_SIGNAL_NAMES = (
    "retrieval_coverage",
    "precedent_strength",
    "validator_agreement",
    "static_check_cleanliness",
)


class ConfidenceError(ValueError):
    """§B.4 fail-closed. Callers must treat this as below the confidence floor."""


class MissingConfidenceSignalError(ConfidenceError):
    """A required §B.4 input was None / omitted. Do not substitute 0.0 or 0.5."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = list(missing)
        super().__init__(f"missing required confidence signals: {self.missing}")


class InvalidConfidenceSignalError(ConfidenceError):
    """A signal was present but not a finite value in [0, 1]."""

    def __init__(self, name: str, value: object) -> None:
        self.name = name
        self.value = value
        super().__init__(f"confidence signal {name!r} must be a float in [0, 1], got {value!r}")


def compute_confidence(
    retrieval_coverage: float | None,
    precedent_strength: float | None,
    validator_agreement: float | None,
    static_check_cleanliness: float | None,
) -> float:
    """Weighted sum of four signals. Raises if any signal is missing or invalid.

    confidence = 0.35*retrieval_coverage
               + 0.20*precedent_strength
               + 0.30*validator_agreement
               + 0.15*static_check_cleanliness
    """
    raw = {
        "retrieval_coverage": retrieval_coverage,
        "precedent_strength": precedent_strength,
        "validator_agreement": validator_agreement,
        "static_check_cleanliness": static_check_cleanliness,
    }
    missing = [name for name in _SIGNAL_NAMES if raw[name] is None]
    if missing:
        raise MissingConfidenceSignalError(missing)
    values: dict[str, float] = {}
    for name in _SIGNAL_NAMES:
        values[name] = _require_unit_interval(name, raw[name])
    score = (
        WEIGHT_RETRIEVAL_COVERAGE * values["retrieval_coverage"]
        + WEIGHT_PRECEDENT_STRENGTH * values["precedent_strength"]
        + WEIGHT_VALIDATOR_AGREEMENT * values["validator_agreement"]
        + WEIGHT_STATIC_CHECK_CLEANLINESS * values["static_check_cleanliness"]
    )
    return round(score, 6)


def _require_unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidConfidenceSignalError(name, value)
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise InvalidConfidenceSignalError(name, value)
    return number
