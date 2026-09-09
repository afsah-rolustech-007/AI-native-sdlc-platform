"""Deterministic ModelAdapter.embed() for tests and the semantic-search demo.

Not a production model. Feature-hashes character n-grams and word prefixes into
the same width as `code_embeddings.embedding` so cosine ranking is stable without
a live GLM key.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator, Sequence

from model_adapters.base import (
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    ToolSpec,
    Vector,
)
from repo_intel.vector.constants import EMBEDDING_DIMENSIONS

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def hashing_embed(texts: list[str], *, dim: int = EMBEDDING_DIMENSIONS) -> list[Vector]:
    return [_embed_one(text, dim) for text in texts]


def _embed_one(text: str, dim: int) -> Vector:
    vec = [0.0] * dim
    lowered = text.lower()
    _accumulate(vec, lowered, char_weight=1.0, word_weight=3.0, prefix_weight=2.0)
    # Signature + docstring sit at the top of the chunk; overweight them so a
    # natural-language query about what a function *does* is not drowned by a
    # large class body that happens to mention the same identifiers.
    head = "\n".join(lowered.split("\n")[:4])
    _accumulate(vec, head, char_weight=2.0, word_weight=6.0, prefix_weight=4.0)
    return _l2_normalize(vec)


def _accumulate(
    vec: list[float],
    text: str,
    *,
    char_weight: float,
    word_weight: float,
    prefix_weight: float,
) -> None:
    for n in (3, 4):
        for index in range(max(0, len(text) - n + 1)):
            _add(vec, f"c{n}:{text[index : index + n]}", weight=char_weight)
    for token in _TOKEN.findall(text):
        _add(vec, f"w:{token}", weight=word_weight)
        for size in range(4, min(len(token), 10) + 1):
            _add(vec, f"p:{token[:size]}", weight=prefix_weight)


def _add(vec: list[float], feature: str, *, weight: float) -> None:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    slot = int.from_bytes(digest[:4], "little") % len(vec)
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    vec[slot] += sign * weight


def _l2_normalize(vec: list[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0.0:
        out = [0.0] * len(vec)
        out[0] = 1.0
        return out
    return [value / norm for value in vec]


class HashingAdapter:
    """Structural ModelAdapter used by RI tests. complete/stream/tools are unused."""

    def __init__(self, *, dim: int = EMBEDDING_DIMENSIONS) -> None:
        self.dim = dim
        self.embed_calls: list[list[str]] = []
        self._pricing = ModelPricing(
            input_price_per_1m=0.0,
            output_price_per_1m=0.0,
            provider="test",
            model_id="hashing-bow",
        )

    def embed(self, texts: list[str]) -> list[Vector]:
        self.embed_calls.append(list(texts))
        return hashing_embed(texts, dim=self.dim)

    def complete(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError("HashingAdapter only implements embed()")

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        raise NotImplementedError("HashingAdapter only implements embed()")

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        raise NotImplementedError("HashingAdapter only implements embed()")

    @property
    def pricing(self) -> ModelPricing:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return 0
