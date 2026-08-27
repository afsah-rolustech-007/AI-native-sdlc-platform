"""Load `configs/pricing/registry.yaml`. Cost math lives here, not on the provider."""

from __future__ import annotations

from pathlib import Path

import yaml

from common.config import get_settings
from model_adapters.base import ModelPricing, TokenUsage


class UnknownModelError(KeyError):
    """Fail-closed: never invent a price for an unregistered model_id."""


class PricingRegistry:
    def __init__(
        self,
        prices: dict[str, ModelPricing],
        *,
        scores: dict[str, int] | None = None,
        version: int = 1,
        effective_date: str = "",
        provenance: dict | None = None,
    ) -> None:
        self.prices = prices
        self.scores = scores or {}
        self.version = version
        self.effective_date = effective_date
        self.provenance = provenance or {}

    def get(self, model_id: str) -> ModelPricing:
        try:
            return self.prices[model_id]
        except KeyError as exc:
            raise UnknownModelError(model_id) from exc

    def capability_score(self, model_id: str) -> int:
        if model_id in self.scores:
            return self.scores[model_id]
        raise UnknownModelError(model_id)


def compute_cost(usage: TokenUsage, pricing: ModelPricing) -> float:
    """USD from internal prices. Ignore any provider-reported cost field.

    If usage.source is `unavailable`, cost is 0 — we never invent tokens.
    """
    if not usage.is_available:
        return 0.0
    input_cost = (usage.input_tokens / 1_000_000) * pricing.input_price_per_1m
    output_cost = (usage.output_tokens / 1_000_000) * pricing.output_price_per_1m
    return round(input_cost + output_cost, 6)


def registry_path(explicit: str | Path | None = None) -> Path:
    raw = Path(explicit) if explicit is not None else Path(get_settings().pricing_registry_path)
    if raw.is_absolute():
        return raw
    return Path(__file__).resolve().parents[2] / raw


def load_pricing_registry(path: str | Path | None = None) -> PricingRegistry:
    data = yaml.safe_load(registry_path(path).read_text(encoding="utf-8")) or {}
    prices: dict[str, ModelPricing] = {}
    scores: dict[str, int] = {}
    for model_id, row in (data.get("models") or {}).items():
        prices[model_id] = ModelPricing(
            input_price_per_1m=float(row["input_price_per_1m"]),
            output_price_per_1m=float(row["output_price_per_1m"]),
            provider=str(row["provider"]),
            model_id=str(row.get("model_id") or model_id),
        )
        if "capability_score" in row:
            scores[model_id] = int(row["capability_score"])
    return PricingRegistry(
        prices,
        scores=scores,
        version=int(data.get("version") or 1),
        effective_date=str(data.get("effective_date") or ""),
        provenance=dict(data.get("provenance") or {}),
    )
