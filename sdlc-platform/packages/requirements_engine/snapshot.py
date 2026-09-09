"""Session-level repository snapshot. Not an LLM call. Not a second summary.

Built once from Phase 03 RI: index_status + architecture summary + repo map,
plus a bounded manifest read. Cached by (repo_root, catalog_hash). Stale or
unindexed trees fail closed. We never pass refresh=True (that re-embeds).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from requirements_engine.exceptions import SnapshotError
from requirements_engine.manifests import ManifestFact, read_manifest_facts
from requirements_engine.ri_client import RepoIntelClient

# Stay near the ~2k-token architecture-summary budget.
MAX_SERVICES = 40
MAX_ENTRY_POINTS = 5
MAX_KEY_SYMBOLS = 5
MAX_PATH_LIST = 20
REPO_MAP_TOP_N = 20

# Drop filler words so "existing_auth_module" can match the `auth` service.
_STOPWORDS = frozenset(
    {
        "existing",
        "module",
        "modules",
        "the",
        "a",
        "an",
        "of",
        "for",
        "is",
        "does",
        "what",
        "which",
        "code",
        "about",
        "related",
        "present",
        "entities",
        "database",
        "need",
    }
)
_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

CapabilityState = Literal["unknown", "available", "unavailable"]


class Capabilities(BaseModel):
    """Known-available flags. `unavailable` is not the same as "no matches"."""

    zoekt: CapabilityState = "unknown"
    embeddings: CapabilityState = "unknown"
    graph: CapabilityState = "unknown"


class ServiceSlice(BaseModel):
    """Capped view of one Phase 03 `service_map` entry."""

    name: str
    files: int = 0
    entry_points: list[str] = Field(default_factory=list)
    key_symbols: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class SessionRepoSnapshot(BaseModel):
    """Compact repository situation for one requirements session."""

    repo_root: str
    catalog_hash: str
    file_count: int
    index_state: Literal["fresh"]
    languages: list[str] = Field(default_factory=list)
    services: list[ServiceSlice] = Field(default_factory=list)
    other_service_count: int = 0
    api_boundaries: list[str] = Field(default_factory=list)
    database_entities: list[str] = Field(default_factory=list)
    shared_modules: list[str] = Field(default_factory=list)
    top_files: list[str] = Field(default_factory=list)
    manifest_facts: list[ManifestFact] = Field(default_factory=list)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    truncated: bool = False
    token_estimate: int = 0


class SnapshotCache:
    """In-process cache. One snapshot per (repo_root, catalog_hash)."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], SessionRepoSnapshot] = {}
        self.hits: int = 0
        self.misses: int = 0

    def get(self, repo_root: str, catalog_hash: str) -> SessionRepoSnapshot | None:
        found = self._items.get((repo_root, catalog_hash))
        if found is None:
            self.misses += 1
            return None
        self.hits += 1
        return found

    def put(self, snapshot: SessionRepoSnapshot) -> None:
        # Drop older hashes for this repo so a stale snapshot cannot be reused.
        stale = [
            key
            for key in self._items
            if key[0] == snapshot.repo_root and key[1] != snapshot.catalog_hash
        ]
        for key in stale:
            del self._items[key]
        self._items[(snapshot.repo_root, snapshot.catalog_hash)] = snapshot


_DEFAULT_CACHE = SnapshotCache()


async def build_snapshot(
    ri: RepoIntelClient,
    *,
    cache: SnapshotCache | None = None,
) -> SessionRepoSnapshot:
    """Fail closed unless the catalog is fresh. Reuse a matching cache entry."""
    status = await ri.index_status()
    state = getattr(status, "state", None)
    if state == "unindexed":
        raise SnapshotError("repository is unindexed; index before requirements")
    if state == "stale":
        stale_paths = list(getattr(status, "stale_paths", []) or [])
        raise SnapshotError(f"repository is stale: {stale_paths}")
    if state != "fresh":
        raise SnapshotError(f"repository is not fresh: {state!r}")
    catalog_hash = getattr(status, "catalog_hash", None)
    if not catalog_hash:
        raise SnapshotError("fresh index is missing catalog_hash")

    repo_root = _repo_root_str(ri)
    store = cache if cache is not None else _DEFAULT_CACHE
    cached = store.get(repo_root, catalog_hash)
    if cached is not None:
        return cached

    # Do not pass refresh=True — that re-embeds. Defaults stay False.
    summary_json = await ri.get_architecture_summary()
    top_files = await ri.get_aider_repo_map(top_n=REPO_MAP_TOP_N)
    snapshot = _project_snapshot(
        repo_root=repo_root,
        catalog_hash=catalog_hash,
        file_count=int(getattr(status, "file_count", 0) or 0),
        summary_json=summary_json,
        top_files=list(top_files or []),
        manifest_facts=read_manifest_facts(Path(ri.repo_root)),
    )
    store.put(snapshot)
    return snapshot


def query_tokens(query: str) -> list[str]:
    """Lowercase tokens with filler words removed, for snapshot lookups."""
    tokens = [match.group(0).lower() for match in _TOKEN.finditer(query)]
    kept = [token for token in tokens if token not in _STOPWORDS and len(token) >= 2]
    return kept or tokens


def refs_from_snapshot(snapshot: SessionRepoSnapshot, query: str) -> list[str]:
    """Cheap lookup against the capped snapshot. Does not read source files."""
    tokens = query_tokens(query)
    if not tokens:
        return []
    refs: list[str] = []
    for service in snapshot.services:
        haystack = " ".join(
            [
                service.name,
                *service.entry_points,
                *service.key_symbols,
                *service.dependencies,
            ]
        ).lower()
        if any(token in haystack for token in tokens):
            refs.append(f"service:{service.name}")
            refs.extend(service.entry_points)
            refs.extend(service.key_symbols)
    for path in (
        *snapshot.top_files,
        *snapshot.api_boundaries,
        *snapshot.shared_modules,
        *snapshot.database_entities,
    ):
        lowered = path.lower()
        if any(token in lowered for token in tokens):
            refs.append(path)
    return _dedupe(refs)


def refs_from_manifests(snapshot: SessionRepoSnapshot, query: str) -> list[str]:
    """Match query tokens against declared dependency names."""
    tokens = query_tokens(query)
    if not tokens:
        return []
    refs: list[str] = []
    for fact in snapshot.manifest_facts:
        for name in fact.names:
            lowered = name.lower()
            if any(token in lowered or lowered in token for token in tokens):
                refs.append(f"manifest:{fact.path}:{name}")
    return _dedupe(refs)


def snapshot_paths_for_query(snapshot: SessionRepoSnapshot, query: str) -> list[str]:
    """File paths from the snapshot that look related. Used as a semantic filter."""
    tokens = query_tokens(query)
    paths: list[str] = []
    for service in snapshot.services:
        if any(token in service.name.lower() for token in tokens):
            paths.extend(service.entry_points)
            for symbol_id in service.key_symbols:
                paths.append(symbol_id.split("::", 1)[0])
    for path in (*snapshot.top_files, *snapshot.api_boundaries, *snapshot.shared_modules):
        if any(token in path.lower() for token in tokens):
            paths.append(path)
    return _dedupe(paths)[:MAX_PATH_LIST]


def _project_snapshot(
    *,
    repo_root: str,
    catalog_hash: str,
    file_count: int,
    summary_json: str,
    top_files: list[str],
    manifest_facts: list[ManifestFact],
) -> SessionRepoSnapshot:
    try:
        summary = json.loads(summary_json)
    except json.JSONDecodeError as exc:
        raise SnapshotError("architecture summary is not valid JSON") from exc
    if not isinstance(summary, dict):
        raise SnapshotError("architecture summary must be a JSON object")

    service_map = summary.get("service_map") or {}
    if not isinstance(service_map, dict):
        service_map = {}
    service_names = sorted(str(name) for name in service_map)
    kept_names = service_names[:MAX_SERVICES]
    other_service_count = max(0, len(service_names) - len(kept_names))
    services = [_slice_service(name, service_map[name]) for name in kept_names]

    languages = _dedupe(
        [lang for service in services for lang in service.languages]
        + [str(item) for item in (summary.get("tech_stack") or []) if item]
    )
    api_boundaries = _cap_paths(summary.get("api_boundaries"))
    database_entities = _cap_paths(summary.get("database_entities"))
    shared_modules = _cap_paths(summary.get("shared_modules"))
    truncated = bool(
        other_service_count
        or any(
            len((service_map[name] or {}).get("entry_points") or []) > MAX_ENTRY_POINTS
            or len((service_map[name] or {}).get("key_symbols") or []) > MAX_KEY_SYMBOLS
            for name in kept_names
            if isinstance(service_map.get(name), dict)
        )
        or len(summary.get("api_boundaries") or []) > MAX_PATH_LIST
        or len(summary.get("database_entities") or []) > MAX_PATH_LIST
        or len(summary.get("shared_modules") or []) > MAX_PATH_LIST
        or any(fact.truncated for fact in manifest_facts)
    )
    snapshot = SessionRepoSnapshot(
        repo_root=repo_root,
        catalog_hash=catalog_hash,
        file_count=file_count or int(summary.get("file_count") or 0),
        index_state="fresh",
        languages=languages,
        services=services,
        other_service_count=other_service_count,
        api_boundaries=api_boundaries,
        database_entities=database_entities,
        shared_modules=shared_modules,
        top_files=list(top_files)[:REPO_MAP_TOP_N],
        manifest_facts=manifest_facts,
        # Summary + repo map both need the graph, so it is available after a hit.
        capabilities=Capabilities(graph="available"),
        truncated=truncated,
    )
    payload = snapshot.model_dump(mode="json")
    snapshot.token_estimate = max(1, len(json.dumps(payload, sort_keys=True)) // 4)
    return snapshot


def _slice_service(name: str, raw: object) -> ServiceSlice:
    data = raw if isinstance(raw, dict) else {}
    return ServiceSlice(
        name=name,
        files=int(data.get("files") or 0),
        entry_points=_cap_paths(data.get("entry_points"), MAX_ENTRY_POINTS),
        key_symbols=_cap_paths(data.get("key_symbols"), MAX_KEY_SYMBOLS),
        dependencies=_cap_paths(data.get("dependencies"), MAX_PATH_LIST),
        languages=_cap_paths(data.get("tech_stack"), MAX_PATH_LIST),
    )


def _cap_paths(value: object, limit: int = MAX_PATH_LIST) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None][:limit]


def _repo_root_str(ri: RepoIntelClient) -> str:
    root = Path(ri.repo_root)
    try:
        if root.exists():
            return str(root.resolve())
    except OSError:
        pass
    return str(root)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
