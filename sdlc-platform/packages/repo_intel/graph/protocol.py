"""Internal graph contract. Phase 11's Neo4j client must match these methods."""

from __future__ import annotations

from typing import Protocol

from repo_intel.models import ImpactSet, Symbol


class CodeGraph(Protocol):
    """Query API shared by NetworkX (MVP) and Neo4j (Phase 11)."""

    def get_callers(self, symbol_id: str, depth: int = 1) -> list[Symbol]: ...

    def get_callees(self, symbol_id: str, depth: int = 1) -> list[Symbol]: ...

    def get_dependencies(self, file_path: str) -> list[str]: ...

    def get_dependents(self, file_path: str) -> list[str]: ...

    def get_impact_set(
        self, changed_files: list[str], *, depth: int | None = None
    ) -> ImpactSet: ...
