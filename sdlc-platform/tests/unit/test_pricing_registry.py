"""Pricing registry and compute_cost."""

from pathlib import Path

from model_adapters.base import ModelPricing, TokenUsage
from model_adapters.registry import UnknownModelError, compute_cost, load_pricing_registry


def test_compute_cost_matches_hand_calculation() -> None:
    pricing = ModelPricing(
        input_price_per_1m=1.0,
        output_price_per_1m=2.0,
        provider="test",
        model_id="test",
    )
    usage = TokenUsage(input_tokens=500_000, output_tokens=250_000)
    assert compute_cost(usage, pricing) == 1.0


def test_load_bundled_registry_has_both_glm_tiers() -> None:
    registry = load_pricing_registry()
    flash = registry.get("glm-4.7-flash")
    full = registry.get("glm-4.7")
    assert flash.provider == "glm"
    assert registry.capability_score("glm-4.7-flash") == 6
    assert registry.capability_score("glm-4.7") == 9
    assert flash.input_price_per_1m < full.input_price_per_1m
    assert registry.version >= 1
    assert registry.provenance.get("provider_authoritative") is False
    assert registry.provenance.get("kind") == "application-maintained"


def test_unavailable_usage_costs_zero() -> None:
    pricing = ModelPricing(
        input_price_per_1m=100.0,
        output_price_per_1m=100.0,
        provider="test",
        model_id="test",
    )
    usage = TokenUsage(input_tokens=999_999, output_tokens=999_999, source="unavailable")
    assert compute_cost(usage, pricing) == 0.0


def test_unknown_model_is_fail_closed() -> None:
    registry = load_pricing_registry()
    try:
        registry.get("not-a-model")
        raise AssertionError("expected UnknownModelError")
    except UnknownModelError:
        pass


def test_edited_registry_file_changes_cost(tmp_path: Path) -> None:
    path = tmp_path / "prices.yaml"
    path.write_text(
        """
version: 9
effective_date: "2099-01-01"
models:
  glm-4.7-flash:
    provider: glm
    model_id: glm-4.7-flash
    capability_score: 6
    input_price_per_1m: 10.0
    output_price_per_1m: 0.0
""",
        encoding="utf-8",
    )
    registry = load_pricing_registry(path)
    assert registry.version == 9
    cost = compute_cost(TokenUsage(input_tokens=1_000_000, output_tokens=0), registry.get("glm-4.7-flash"))
    assert cost == 10.0
