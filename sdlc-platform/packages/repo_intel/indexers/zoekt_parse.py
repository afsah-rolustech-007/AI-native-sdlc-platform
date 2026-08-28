"""Normalize Zoekt CLI output into `SearchHit` rows.

Zoekt's `-jsonl` encoder writes Go `FileMatch` structs. `[]byte` fields
(`Line`, `Content`) are standard encoding/json base64 strings.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from repo_intel.models import SearchHit

# Text mode: `path:line:snippet` (snippet may contain colons).
_TEXT_HIT = re.compile(r"^(?P<path>.+):(?P<line>\d+):(?P<snippet>.*)$")


def decode_zoekt_bytes(value: object) -> str:
    """Turn a Go `[]byte` JSON field into text. Invalid bytes are replaced, not raised."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        return bytes(value).decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return str(value)
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return value
    return raw.decode("utf-8", errors="replace")


def parse_jsonl_file_match(payload: dict[str, Any], *, rank: int) -> list[SearchHit]:
    file_path = str(payload.get("FileName") or payload.get("fileName") or "")
    if not file_path:
        return []
    file_score = _as_float(payload.get("Score"), fallback=1.0 / (rank + 1))
    hits: list[SearchHit] = []
    line_matches = payload.get("LineMatches") or payload.get("lineMatches") or []
    if isinstance(line_matches, list) and line_matches:
        for index, match in enumerate(line_matches):
            if not isinstance(match, dict):
                continue
            line_no = int(match.get("LineNumber") or match.get("lineNumber") or 0)
            snippet = decode_zoekt_bytes(match.get("Line") or match.get("line")).rstrip("\n\r")
            score = _as_float(match.get("Score"), fallback=file_score - (index * 0.001))
            hits.append(
                SearchHit(file_path=file_path, line=line_no, snippet=snippet, score=score)
            )
        return hits
    chunk_matches = payload.get("ChunkMatches") or payload.get("chunkMatches") or []
    if isinstance(chunk_matches, list) and chunk_matches:
        for index, chunk in enumerate(chunk_matches):
            if not isinstance(chunk, dict):
                continue
            content_start = chunk.get("ContentStart") or chunk.get("contentStart") or {}
            line_no = 0
            if isinstance(content_start, dict):
                line_no = int(content_start.get("Line") or content_start.get("line") or 0)
            snippet = decode_zoekt_bytes(chunk.get("Content") or chunk.get("content"))
            snippet = snippet.splitlines()[0] if snippet else ""
            score = _as_float(chunk.get("Score"), fallback=file_score - (index * 0.001))
            hits.append(
                SearchHit(file_path=file_path, line=line_no, snippet=snippet, score=score)
            )
        return hits
    return [SearchHit(file_path=file_path, line=0, snippet="", score=file_score)]


def parse_search_output(stdout: str, *, jsonl: bool = True) -> list[SearchHit]:
    """Parse `zoekt` stdout. Unknown/partial lines are skipped, not turned into fake hits."""
    hits: list[SearchHit] = []
    rank = 0
    for raw_line in stdout.splitlines():
        line = raw_line.strip("\n")
        if not line.strip():
            continue
        if jsonl:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            parsed = parse_jsonl_file_match(payload, rank=rank)
            if parsed:
                hits.extend(parsed)
                rank += 1
            continue
        match = _TEXT_HIT.match(line)
        if match is None:
            continue
        hits.append(
            SearchHit(
                file_path=match.group("path"),
                line=int(match.group("line")),
                snippet=match.group("snippet"),
                score=1.0 / (rank + 1),
            )
        )
        rank += 1
    return hits


def rank_and_clip(hits: list[SearchHit], top_k: int) -> list[SearchHit]:
    ordered = sorted(hits, key=lambda hit: (-hit.score, hit.file_path, hit.line))
    return ordered[:top_k]


def _as_float(value: object, *, fallback: float) -> float:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return fallback
    return fallback
