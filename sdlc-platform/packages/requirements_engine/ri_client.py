"""Duck-typed view of Phase 03 `RepositoryIntelligence`.

Group B talks to RI through this Protocol so unit tests can use a fake client.
It is not a new RI API — every method already exists on the Phase 03 class.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol


class RepoIntelClient(Protocol):
    """The RI methods the requirements engine is allowed to call."""

    repo_root: Path

    async def index_status(self) -> Any: ...

    async def get_architecture_summary(self) -> str: ...

    async def get_aider_repo_map(self, top_n: int = 20) -> list[str]: ...

    async def get_symbol_signature(self, symbol_id: str) -> str: ...

    async def get_file_structure(self, file_path: str) -> list[Any]: ...

    async def search_codebase(self, query: str, top_k: int = 10) -> list[Any]: ...

    async def search_concepts(
        self,
        query: str,
        top_k: int = 5,
        *,
        kinds: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        min_score: float | None = None,
    ) -> list[Any]: ...

    async def get_callers(self, symbol_id: str, depth: int = 1) -> list[Any]: ...

    async def get_callees(self, symbol_id: str, depth: int = 1) -> list[Any]: ...

    async def get_dependencies(self, file_path: str) -> list[str]: ...

    async def get_dependents(self, file_path: str) -> list[str]: ...

    async def get_impact_set(
        self, changed_files: list[str], *, depth: int | None = None
    ) -> Any: ...
