"""§B.4 compute_confidence: exact formula, fail-closed, no imputation."""

from __future__ import annotations

import pytest

from common.confidence import (
    InvalidConfidenceSignalError,
    MissingConfidenceSignalError,
    compute_confidence,
)


def test_exact_b4_weights() -> None:
    assert compute_confidence(1.0, 1.0, 1.0, 1.0) == 1.0
    # 0.35*0.8 + 0.20*0.5 + 0.30*0.9 + 0.15*1.0 = 0.80
    assert compute_confidence(0.8, 0.5, 0.9, 1.0) == 0.8
    assert compute_confidence(0.0, 0.0, 0.0, 0.0) == 0.0


def test_boundary_values() -> None:
    assert compute_confidence(0.0, 1.0, 0.0, 1.0) == round(0.20 + 0.15, 6)
    assert compute_confidence(1.0, 0.0, 1.0, 0.0) == round(0.35 + 0.30, 6)


def test_deterministic() -> None:
    first = compute_confidence(0.4, 0.6, 0.2, 0.8)
    second = compute_confidence(0.4, 0.6, 0.2, 0.8)
    assert first == second == round(0.35 * 0.4 + 0.20 * 0.6 + 0.30 * 0.2 + 0.15 * 0.8, 6)


def test_missing_precedent_strength_fail_closes() -> None:
    with pytest.raises(MissingConfidenceSignalError) as exc:
        compute_confidence(0.5, None, 0.5, 0.5)
    assert exc.value.missing == ["precedent_strength"]


def test_any_missing_signal_fail_closes() -> None:
    with pytest.raises(MissingConfidenceSignalError) as exc:
        compute_confidence(None, None, None, None)
    assert exc.value.missing == [
        "retrieval_coverage",
        "precedent_strength",
        "validator_agreement",
        "static_check_cleanliness",
    ]


def test_out_of_range_and_non_numeric_fail_closed() -> None:
    with pytest.raises(InvalidConfidenceSignalError):
        compute_confidence(1.1, 0.0, 0.0, 0.0)
    with pytest.raises(InvalidConfidenceSignalError):
        compute_confidence(0.0, -0.01, 0.0, 0.0)
    with pytest.raises(InvalidConfidenceSignalError):
        compute_confidence(0.0, 0.0, float("nan"), 0.0)  # type: ignore[arg-type]
    with pytest.raises(InvalidConfidenceSignalError):
        compute_confidence(True, 0.0, 0.0, 0.0)  # type: ignore[arg-type]


def test_no_hidden_default_raises_rather_than_returning_floor() -> None:
    with pytest.raises(MissingConfidenceSignalError):
        compute_confidence(0.8, None, 1.0, 1.0)
