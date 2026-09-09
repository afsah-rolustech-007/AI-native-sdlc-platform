"""CLI for Section 05 indexing.

  uv run python scripts/ri_index.py status  --repo-root .
  uv run python scripts/ri_index.py index   --repo-root .  [--rebuild]
  uv run python scripts/ri_index.py reindex --repo-root .  [PATH ...]

Uses the deterministic hashing embedder unless --live is passed. `--repo-root`
defaults to RI_REPO_ROOT; it is never inferred from git.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.hashing_adapter import HashingAdapter

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from model_adapters.base import ModelAdapter
from repo_intel.api import RepositoryIntelligence
from repo_intel.exceptions import RepoIntelError

logger = logging.getLogger("sdlc.repo_intel")


def _adapter(live: bool) -> ModelAdapter:
    if not live:
        return HashingAdapter()
    from model_adapters.glm.adapter import GLMAdapter

    return GLMAdapter()


async def _run(args: argparse.Namespace) -> int:
    engine = make_async_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            ri = RepositoryIntelligence(session, _adapter(args.live), args.repo_root)
            if args.command == "status":
                status = await ri.index_status()
                print(f"{status.state}  files={status.file_count}  hash={status.catalog_hash}")
                for path in status.stale_paths[:20]:
                    print(f"  stale: {path}")
                return 0 if status.state == "fresh" else 1
            if args.command == "index":
                stats = await ri.index(rebuild=args.rebuild)
            else:
                stats = await ri.reindex_paths(args.paths) if args.paths else await ri.reindex()
            print(
                f"created={stats.created} modified={stats.modified} deleted={stats.deleted} "
                f"unchanged={stats.unchanged} parsed={stats.files_parsed} "
                f"symbols={stats.symbols_indexed} embedded={stats.chunks_embedded} "
                f"reused={stats.chunks_skipped_unchanged} zoekt={stats.zoekt_rebuilt} "
                f"in {stats.elapsed_s:.2f}s"
            )
            return 0
    except RepoIntelError as exc:
        logger.error("%s failed: %s", args.command, exc)
        return 2
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Repository Intelligence indexing CLI")
    parser.add_argument("command", choices=["status", "index", "reindex"])
    parser.add_argument("paths", nargs="*", help="relative paths (reindex only)")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--rebuild", action="store_true", help="wipe and rebuild (index only)")
    parser.add_argument("--live", action="store_true", help="use GLMAdapter.embed()")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
