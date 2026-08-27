"""ModelRouter capability lookup. No escalate_model_tier (Phase 10)."""

import pytest
from tests.contract.fakes import FakeAdapter

from model_adapters.router import ModelRouter, NoCapableModelError


def _router() -> ModelRouter:
    return ModelRouter(
        [
            FakeAdapter(
                model_id="glm-4.7-flash",
                capability_score=6,
                input_price_per_1m=0.07,
                output_price_per_1m=0.40,
            ),
            FakeAdapter(
                model_id="glm-4.7",
                capability_score=9,
                input_price_per_1m=0.60,
                output_price_per_1m=2.20,
            ),
        ]
    )


def test_select_code_generation_returns_flash_tier() -> None:
    chosen = _router().select("implementation", "code_generation", {})
    assert chosen.pricing.model_id == "glm-4.7-flash"


def test_select_architecture_returns_higher_tier() -> None:
    chosen = _router().select("design", "architecture", {})
    assert chosen.pricing.model_id == "glm-4.7"
    assert chosen.capability_score >= 9


def test_select_fails_closed_when_nothing_meets_score() -> None:
    router = ModelRouter([FakeAdapter(capability_score=3)])
    with pytest.raises(NoCapableModelError):
        router.select("design", "architecture", {})


def test_high_risk_bumps_requirement() -> None:
    # code_generation is 6; high-risk becomes 7, flash (6) must not be chosen.
    router = ModelRouter(
        [
            FakeAdapter(model_id="flash", capability_score=6, input_price_per_1m=0.01),
            FakeAdapter(model_id="full", capability_score=8, input_price_per_1m=1.0),
        ]
    )
    chosen = router.select("implementation", "code_generation", {"risk_tier": "high"})
    assert chosen.pricing.model_id == "full"
