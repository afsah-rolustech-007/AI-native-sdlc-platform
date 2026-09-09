"""Natural-language semantic search vs lexical Zoekt on the fixture tree.

  uv run python scripts/demo_semantic_search.py

Uses a deterministic hashing embedder so the demo runs without GLM_API_KEY.
Pass --live to use GLMAdapter.embed() (skipped internally if the key is missing).
Requires Postgres with migration 0003 (`make up && make migrate`).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from repo_intel.exceptions import EmbeddingIndexError, ZoektNotIndexedError, ZoektUnavailableError
from repo_intel.vector.pgvector_client import PgvectorClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.hashing_adapter import HashingAdapter

FIXTURE = ROOT / "tests" / "fixtures" / "source_tree"
NL_QUERY = "function that validates user input"
SIMILAR = '''
def check_access(token: str) -> bool:
    """Return True when the token has non-whitespace content."""
    return bool(token.strip())
'''


def _adapter(*, live: bool):
    if not live:
        return HashingAdapter(), "hashing-bow (deterministic test embedder)"
    from model_adapters.glm.adapter import GLMAdapter, GLMConfigError

    settings = get_settings()
    if not settings.glm_api_key:
        print("GLM_API_KEY is not set; falling back to the hashing embedder")
        return HashingAdapter(), "hashing-bow (no GLM_API_KEY)"
    try:
        return GLMAdapter(), f"GLMAdapter.embed() model={settings.glm_embed_model}"
    except GLMConfigError as exc:
        print(f"GLM adapter unavailable ({exc}); falling back to the hashing embedder")
        return HashingAdapter(), "hashing-bow"


def _print_hits(label: str, hits) -> None:
    print(f"\n{label}")
    if not hits:
        print("  (no hits)")
        return
    for hit in hits:
        score = f"{hit.score:.3f}" if hit.score is not None else "?"
        print(f"  {hit.symbol_id}  L{hit.start_line}-{hit.end_line}  score={score}")


def _zoekt_contrast(query: str) -> None:
    print(f"\nZoekt lexical search_codebase({query!r}, top_k=5)")
    try:
        from repo_intel.indexers.zoekt_client import ZoektClient

        index_dir = Path.home() / ".cache" / "sdlc-platform" / "zoekt" / "demo-semantic"
        client = ZoektClient(FIXTURE, index_dir)
        client.build_index()
        hits = client.search_codebase(query, 5)
    except (ZoektUnavailableError, ZoektNotIndexedError) as exc:
        print(f"  (Zoekt not used: {exc})")
        return
    if not hits:
        print("  (no hits — the query has no identifier like validate_token)")
        return
    for hit in hits:
        snippet = hit.snippet.strip().replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        print(f"  {hit.file_path}:{hit.line}  {snippet}")


async def _run(*, live: bool) -> None:
    adapter, label = _adapter(live=live)
    print(f"repo_root={FIXTURE}")
    print(f"embedder={label}")
    print("source of truth: working tree on disk (not git)")

    engine = make_async_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            client = PgvectorClient(session, adapter, FIXTURE)
            stats = await client.index_working_tree()
            print(
                f"\nindex_working_tree: files_seen={stats.files_seen} "
                f"chunks_embedded={stats.chunks_embedded}"
            )
            concepts = await client.search_concepts(NL_QUERY, 5)
            _print_hits(f"search_concepts({NL_QUERY!r})", concepts)
            similar = await client.find_similar_implementations(SIMILAR, 3)
            _print_hits("find_similar_implementations(paraphrase of validate_token)", similar)
    except EmbeddingIndexError as exc:
        print(f"\nindexing/search failed: {exc}")
        print("Postgres with migration 0003 is required: make up && make migrate")
    finally:
        await engine.dispose()

    _zoekt_contrast(NL_QUERY)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="use GLMAdapter.embed() instead of the hashing embedder",
    )
    args = parser.parse_args()
    asyncio.run(_run(live=args.live))


if __name__ == "__main__":
    main()
