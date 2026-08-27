"""Create LangGraph checkpoint tables (idempotent). Uses DATABASE_URL from Settings."""

from __future__ import annotations

import asyncio
import sys

from orchestration.checkpointers.postgres import setup_checkpoint_tables


async def _main() -> None:
    await setup_checkpoint_tables()
    print("LangGraph checkpoint tables are ready.")


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        sys.exit(130)
