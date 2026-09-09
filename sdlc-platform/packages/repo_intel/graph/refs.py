"""Raw import/call facts extracted from one file's Tree-sitter tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ImportRef:
    """One import statement before we know whether the target file exists."""

    origin_file: str
    module: str
    names: tuple[tuple[str, str], ...]  # (local_name, original_name)
    relative_level: int  # 0 = absolute; 1 = from .x; 2 = from ..x


@dataclass(frozen=True)
class CallRef:
    """One call site. `object_name` is set for `UserService().get_user` style calls."""

    origin_file: str
    caller_id: str
    simple_name: str
    object_name: str | None


@dataclass(frozen=True)
class GraphEdge:
    """Directed edge. Import: importer → imported. Call: caller → callee."""

    source: str
    target: str
    edge_type: Literal["import", "call"]
    origin_file: str
