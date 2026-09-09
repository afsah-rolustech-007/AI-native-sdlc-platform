"""Bounded read of a few named dependency files. Not a repository walk.

Phase 03 indexes `.py` / `.ts` / `.tsx` only, so `pyproject.toml` is invisible
to RI. We read these filenames at the repo root (max 32 KiB each) and keep
dependency *names* only. A missing file is an omission, not an error.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Exact names at the repository root. Nested copies are ignored on purpose.
ALLOWLIST: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
    }
)
MAX_MANIFEST_BYTES = 32 * 1024

_PEP508_CUT = re.compile(r"[\[ <>=~!;]")
_REQUIREMENTS_SKIP = re.compile(r"^\s*(#|$|-e\s|--|-r\s)")
_GO_REQUIRE = re.compile(r"^\s*([^\s]+)\s+v")
_XML_ARTIFACT = re.compile(r"<artifactId>([^<]+)</artifactId>")
_GRADLE_DEP = re.compile(
    r"""(?:implementation|api|compileOnly|runtimeOnly|compile)\s*[\(]?\s*['"]([^'"]+)['"]"""
)


class ManifestFact(BaseModel):
    """One allowlisted file we actually opened."""

    path: str
    kind: Literal["dependency"] = "dependency"
    names: list[str] = Field(default_factory=list)
    truncated: bool = False


def read_manifest_facts(repo_root: Path | str) -> list[ManifestFact]:
    """Read allowlisted files under `repo_root`. Unsafe or huge files are skipped."""
    root = Path(repo_root)
    if not root.is_dir():
        return []
    facts: list[ManifestFact] = []
    for name in sorted(ALLOWLIST):
        path = _safe_manifest_path(root, name)
        if path is None or not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_MANIFEST_BYTES:
            facts.append(ManifestFact(path=name, truncated=True))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        names = _parse_dependency_names(name, text)
        facts.append(ManifestFact(path=name, names=names))
    return facts


def _safe_manifest_path(repo_root: Path, name: str) -> Path | None:
    """Only `repo_root / filename`. Reject slashes, `..`, and absolute paths."""
    if name not in ALLOWLIST:
        return None
    if name != Path(name).name or "/" in name or "\\" in name:
        return None
    try:
        root = repo_root.resolve()
    except OSError:
        return None
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.name != name:
        return None
    return candidate


def _parse_dependency_names(filename: str, text: str) -> list[str]:
    if filename in {"pyproject.toml", "Pipfile", "Cargo.toml"}:
        names = _from_toml(filename, text)
    elif filename == "package.json":
        names = _from_package_json(text)
    elif filename == "requirements.txt":
        names = _from_requirements(text)
    elif filename == "go.mod":
        names = _from_go_mod(text)
    elif filename == "pom.xml":
        names = [item.strip() for item in _XML_ARTIFACT.findall(text) if item.strip()]
    elif filename == "build.gradle":
        names = [item.strip() for item in _GRADLE_DEP.findall(text) if item.strip()]
    else:
        names = []
    # Stable unique list. Never include blank names.
    return sorted({name for name in names if name})


def _from_toml(filename: str, text: str) -> list[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    names: list[str] = []
    if filename == "pyproject.toml":
        project = data.get("project") or {}
        names.extend(_pep508_names(project.get("dependencies") or []))
        optional = project.get("optional-dependencies") or {}
        if isinstance(optional, dict):
            for group in optional.values():
                names.extend(_pep508_names(group or []))
        poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        if isinstance(poetry, dict):
            names.extend(str(key) for key in poetry if str(key) != "python")
    elif filename == "Pipfile":
        for section in ("packages", "dev-packages"):
            block = data.get(section) or {}
            if isinstance(block, dict):
                names.extend(str(key) for key in block)
    elif filename == "Cargo.toml":
        block = data.get("dependencies") or {}
        if isinstance(block, dict):
            names.extend(str(key) for key in block)
    return names


def _from_package_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = data.get(key) or {}
        if isinstance(block, dict):
            names.extend(str(name) for name in block)
    return names


def _from_requirements(text: str) -> list[str]:
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _REQUIREMENTS_SKIP.match(line):
            continue
        names.append(_pep508_name(line))
    return names


def _from_go_mod(text: str) -> list[str]:
    names: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            match = _GO_REQUIRE.match(line)
            if match:
                names.append(match.group(1))
            continue
        if line.startswith("require "):
            parts = line.split()
            if len(parts) >= 2:
                names.append(parts[1])
    return names


def _pep508_names(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [_pep508_name(str(item)) for item in items]


def _pep508_name(spec: str) -> str:
    """`fastapi[std]>=0.111` → `fastapi`."""
    token = spec.strip().split(";")[0].strip()
    cut = _PEP508_CUT.search(token)
    if cut:
        token = token[: cut.start()]
    return token.strip()
