"""Parse and query symbols from a working-tree fixture.

  uv run python scripts/demo_symbol_index.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from repo_intel.indexers.treesitter import (
    get_file_structure,
    get_symbol_body,
    get_symbol_signature,
    index_repo,
    parse_file,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "source_tree"
SAMPLE_FILE = "src/auth.py"
SAMPLE_SYMBOL = "src/auth.py::validate_token"


async def _run() -> None:
    file_path = FIXTURE / "src" / "auth.py"
    print(f"repo_root={FIXTURE}")
    print(f"parse_file {SAMPLE_FILE} (no git involved):\n")
    for symbol in parse_file(file_path, relative_path=SAMPLE_FILE):
        print(
            f"  {symbol.kind:8} {symbol.id:42} "
            f"L{symbol.start_line}-{symbol.end_line} {symbol.signature or ''}"
        )

    engine = make_async_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        stats = await index_repo(FIXTURE, session)
        print("\nindex_repo IndexStats:")
        print(
            f"  files_seen={stats.files_seen} parsed_ok={stats.files_parsed_ok} "
            f"parse_error={stats.files_parse_error} skipped={stats.files_skipped}"
        )
        print(f"  symbols_indexed={stats.symbols_indexed}")
        print(f"  per_extension={ {k: v.model_dump() for k, v in stats.per_extension.items()} }")

        structure = await get_file_structure(session, FIXTURE, SAMPLE_FILE)
        print(f"\nget_file_structure({SAMPLE_FILE}):")
        for symbol in structure:
            print(f"  {symbol.kind:8} {symbol.id}")

        signature = await get_symbol_signature(session, FIXTURE, SAMPLE_SYMBOL)
        body = await get_symbol_body(session, FIXTURE, SAMPLE_SYMBOL)
        print(f"\nget_symbol_signature({SAMPLE_SYMBOL}):\n  {signature}")
        print(f"\nget_symbol_body({SAMPLE_SYMBOL}):\n{body}")
    await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
