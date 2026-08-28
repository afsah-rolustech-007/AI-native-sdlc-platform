"""Lexical search over a working-tree fixture via Zoekt.

  uv run python scripts/demo_lexical_search.py
"""

from __future__ import annotations

from pathlib import Path

from repo_intel.exceptions import ZoektUnavailableError
from repo_intel.indexers.zoekt_client import ZoektClient

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "source_tree"
QUERIES = (
    "validate_token",
    "indexed-without-git",
    "ChargeService",
    "formatCents",
    "should_not_be_indexed",
)


def main() -> None:
    index_dir = Path.home() / ".cache" / "sdlc-platform" / "zoekt" / "demo-source-tree"
    print(f"repo_root={FIXTURE}")
    print(f"index_dir={index_dir}")
    print("source of truth: working tree on disk (not git)\n")
    try:
        client = ZoektClient(FIXTURE, index_dir)
        stats = client.build_index()
    except ZoektUnavailableError as exc:
        print(f"Zoekt is not available: {exc}")
        return
    print(
        f"build_index: files_indexed={stats.files_indexed} runner={stats.runner}\n"
    )
    for query in QUERIES:
        print(f"search_codebase({query!r}, top_k=5)")
        hits = client.search_codebase(query, 5)
        if not hits:
            print("  (no hits)")
            continue
        for hit in hits:
            snippet = hit.snippet.strip()
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            print(
                f"  {hit.file_path}:{hit.line}  score={hit.score:.3f}  {snippet}"
            )
        print()


if __name__ == "__main__":
    main()
