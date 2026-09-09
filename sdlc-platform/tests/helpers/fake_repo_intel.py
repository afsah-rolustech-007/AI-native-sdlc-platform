"""In-memory RepositoryIntelligence stand-in for Group B unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from repo_intel.exceptions import (
    EmbeddingsNotIndexedError,
    StaleIndexError,
    SymbolNotFoundError,
    ZoektUnavailableError,
)

DEFAULT_SUMMARY: dict[str, Any] = {
    "repo_root": "/tmp/fake-repo",
    "generated_by": "ast",
    "file_count": 12,
    "symbol_count": 20,
    "services": ["auth", "billing", "storage", "web", "shared"],
    "service_map": {
        "auth": {
            "files": 3,
            "entry_points": [],
            "key_symbols": ["auth/service.py::AuthService", "auth/tokens.py::issue_token"],
            "dependencies": ["shared", "storage"],
            "tech_stack": ["python"],
        },
        "billing": {
            "files": 2,
            "entry_points": [],
            "key_symbols": ["billing/charges.py::ChargeProcessor"],
            "dependencies": ["storage"],
            "tech_stack": ["python"],
        },
        "storage": {
            "files": 3,
            "entry_points": [],
            "key_symbols": ["storage/models.py::User"],
            "dependencies": [],
            "tech_stack": ["python"],
        },
        "web": {
            "files": 2,
            "entry_points": ["web/main.py"],
            "key_symbols": ["web/main.py::main"],
            "dependencies": ["auth", "billing", "shared"],
            "tech_stack": ["python"],
        },
        "shared": {
            "files": 2,
            "entry_points": [],
            "key_symbols": ["shared/config.py::Settings"],
            "dependencies": [],
            "tech_stack": ["python"],
        },
    },
    "shared_modules": ["shared/config.py"],
    "database_entities": ["storage/models.py::User"],
    "api_boundaries": ["web/api/routes.py"],
    "cross_service_dependencies": [{"from": "web/main.py", "to": "auth/service.py"}],
}


class FakeRI:
    """Records every call so tests can assert refresh=True never happened."""

    def __init__(
        self,
        *,
        repo_root: Path | str = "/tmp/fake-repo",
        state: str = "fresh",
        catalog_hash: str = "hash1",
        file_count: int = 12,
        stale_paths: list[str] | None = None,
        summary: dict[str, Any] | None = None,
        repo_map: list[str] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.state = state
        self.catalog_hash = catalog_hash
        self.file_count = file_count
        self.stale_paths = list(stale_paths or [])
        self.summary = summary if summary is not None else dict(DEFAULT_SUMMARY)
        self.repo_map = repo_map or ["shared/config.py", "auth/service.py", "web/main.py"]
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.signatures = {"auth/service.py::AuthService": "class AuthService"}
        self.file_structures: dict[str, list[Any]] = {}
        self.lexical_hits: list[Any] = [
            SimpleNamespace(file_path="auth/service.py", line=9, snippet="class AuthService:", score=1.0)
        ]
        self.semantic_hits: list[Any] = [
            SimpleNamespace(
                symbol_id="auth/tokens.py::verify_token",
                file_path="auth/tokens.py",
                chunk_text="verify bearer token signature",
                score=0.42,
            )
        ]
        self.dependents = {"auth/service.py": ["web/main.py", "web/api/routes.py"]}
        self.dependencies = {"auth/service.py": ["auth/tokens.py", "shared/config.py"]}
        self.callers = {
            "auth/service.py::AuthService.login": [
                SimpleNamespace(id="web/api/routes.py::login_route", file_path="web/api/routes.py")
            ]
        }
        self.callees: dict[str, list[Any]] = {}
        self.impact = SimpleNamespace(
            affected_files=["web/main.py", "web/api/routes.py"],
            affected_symbols=["web/main.py::build_app"],
        )
        self.lexical_error: BaseException | None = None
        self.semantic_error: BaseException | None = None
        self.graph_error: BaseException | None = None
        self.stale_on_read = False

    def call_count(self, name: str) -> int:
        return sum(1 for method, _ in self.calls if method == name)

    def refresh_true_calls(self) -> list[str]:
        return [name for name, kwargs in self.calls if kwargs.get("refresh") is True]

    def _note(self, name: str, **kwargs: Any) -> None:
        if self.stale_on_read and name != "index_status":
            raise StaleIndexError(["touched.py"])
        self.calls.append((name, kwargs))

    async def index_status(self) -> SimpleNamespace:
        self._note("index_status")
        return SimpleNamespace(
            state=self.state,
            catalog_hash=self.catalog_hash,
            file_count=self.file_count,
            stale_paths=self.stale_paths,
            repo_root=str(self.repo_root),
        )

    async def get_architecture_summary(self, *, refresh: bool = False) -> str:
        self._note("get_architecture_summary", refresh=refresh)
        return json.dumps(self.summary)

    async def get_aider_repo_map(self, top_n: int = 20, *, refresh: bool = False) -> list[str]:
        self._note("get_aider_repo_map", top_n=top_n, refresh=refresh)
        return list(self.repo_map)[:top_n]

    async def get_symbol_signature(self, symbol_id: str, *, refresh: bool = False) -> str:
        self._note("get_symbol_signature", symbol_id=symbol_id, refresh=refresh)
        if symbol_id not in self.signatures:
            raise SymbolNotFoundError(symbol_id)
        return self.signatures[symbol_id]

    async def get_file_structure(self, file_path: str, *, refresh: bool = False) -> list[Any]:
        self._note("get_file_structure", file_path=file_path, refresh=refresh)
        return list(self.file_structures.get(file_path, []))

    async def search_codebase(self, query: str, top_k: int = 10, *, refresh: bool = False) -> list[Any]:
        self._note("search_codebase", query=query, top_k=top_k, refresh=refresh)
        if self.lexical_error is not None:
            raise self.lexical_error
        return list(self.lexical_hits)[:top_k]

    async def search_concepts(
        self,
        query: str,
        top_k: int = 5,
        *,
        kinds: list[str] | None = None,
        paths: list[str] | None = None,
        min_score: float | None = None,
        refresh: bool = False,
    ) -> list[Any]:
        self._note(
            "search_concepts",
            query=query,
            top_k=top_k,
            kinds=kinds,
            paths=paths,
            min_score=min_score,
            refresh=refresh,
        )
        if self.semantic_error is not None:
            raise self.semantic_error
        return list(self.semantic_hits)[:top_k]

    async def get_callers(self, symbol_id: str, depth: int = 1, *, refresh: bool = False) -> list[Any]:
        self._note("get_callers", symbol_id=symbol_id, depth=depth, refresh=refresh)
        if self.graph_error is not None:
            raise self.graph_error
        return list(self.callers.get(symbol_id, []))

    async def get_callees(self, symbol_id: str, depth: int = 1, *, refresh: bool = False) -> list[Any]:
        self._note("get_callees", symbol_id=symbol_id, depth=depth, refresh=refresh)
        if self.graph_error is not None:
            raise self.graph_error
        return list(self.callees.get(symbol_id, []))

    async def get_dependencies(self, file_path: str, *, refresh: bool = False) -> list[str]:
        self._note("get_dependencies", file_path=file_path, refresh=refresh)
        if self.graph_error is not None:
            raise self.graph_error
        return list(self.dependencies.get(file_path, []))

    async def get_dependents(self, file_path: str, *, refresh: bool = False) -> list[str]:
        self._note("get_dependents", file_path=file_path, refresh=refresh)
        if self.graph_error is not None:
            raise self.graph_error
        return list(self.dependents.get(file_path, []))

    async def get_impact_set(
        self, changed_files: list[str], *, depth: int | None = None, refresh: bool = False
    ) -> Any:
        self._note("get_impact_set", changed_files=changed_files, depth=depth, refresh=refresh)
        if self.graph_error is not None:
            raise self.graph_error
        return self.impact

    async def find_relevant_context(self, query: str, top_k: int = 10) -> list[Any]:
        self._note("find_relevant_context", query=query, top_k=top_k)
        raise AssertionError("find_relevant_context must never be called")


def zoekt_unavailable() -> ZoektUnavailableError:
    return ZoektUnavailableError("zoekt binaries are not installed")


def embeddings_missing(root: str = "/tmp/fake-repo") -> EmbeddingsNotIndexedError:
    return EmbeddingsNotIndexedError(root)
