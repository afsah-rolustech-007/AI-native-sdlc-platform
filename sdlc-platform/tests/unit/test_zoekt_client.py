"""Zoekt JSONL/text parsing and eligible-tree staging. No Zoekt binary required."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from repo_intel.exceptions import ZoektIndexError, ZoektNotIndexedError
from repo_intel.indexers.zoekt_client import (
    ZoektClient,
    is_zoekt_indexed,
    write_eligible_tree,
)
from repo_intel.indexers.zoekt_parse import (
    decode_zoekt_bytes,
    parse_search_output,
    rank_and_clip,
)
from repo_intel.indexers.zoekt_runner import ZoektProcessResult, _docker_argv
from repo_intel.models import SearchHit

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def test_write_eligible_tree_matches_catalog_ignore_rules(tmp_path: Path) -> None:
    dest = tmp_path / "mirror"
    snapshots = write_eligible_tree(FIXTURE, dest)
    paths = {item.relative_path for item in snapshots}
    assert "src/auth.py" in paths
    assert "src/uncommitted.py" in paths
    assert "src/broken.py" in paths
    assert "ignored/secret.py" not in paths
    assert "README.md" not in paths
    assert (dest / "src" / "auth.py").is_file()
    assert not (dest / "ignored" / "secret.py").exists()
    assert not (dest / "README.md").exists()
    assert (dest / "src" / "auth.py").read_bytes() == (FIXTURE / "src" / "auth.py").read_bytes()


def test_jsonl_line_match_decodes_go_bytes_and_keeps_score() -> None:
    snippet = "def validate_token(token: str) -> bool:"
    payload = {
        "FileName": "src/auth.py",
        "Score": 42.0,
        "LineMatches": [
            {"Line": _b64(snippet), "LineNumber": 19, "Score": 9.5},
        ],
    }
    stdout = json.dumps(payload) + "\n"
    hits = parse_search_output(stdout, jsonl=True)
    assert len(hits) == 1
    assert hits[0].file_path == "src/auth.py"
    assert hits[0].line == 19
    assert hits[0].snippet == snippet
    assert hits[0].score == 9.5


def test_text_mode_parses_path_line_snippet() -> None:
    stdout = "src/auth.py:19:def validate_token(token: str) -> bool:\n"
    hits = parse_search_output(stdout, jsonl=False)
    assert hits[0].file_path == "src/auth.py"
    assert hits[0].line == 19
    assert "validate_token" in hits[0].snippet


def test_rank_and_clip_orders_by_score_then_path() -> None:
    hits = [
        SearchHit(file_path="b.py", line=1, snippet="x", score=1.0),
        SearchHit(file_path="a.py", line=2, snippet="y", score=5.0),
        SearchHit(file_path="a.py", line=1, snippet="z", score=5.0),
    ]
    clipped = rank_and_clip(hits, 2)
    assert [hit.file_path for hit in clipped] == ["a.py", "a.py"]
    assert clipped[0].line == 1
    assert clipped[1].line == 2


def test_decode_zoekt_bytes_falls_back_when_not_base64() -> None:
    assert decode_zoekt_bytes("plain snippet") == "plain snippet"
    assert decode_zoekt_bytes(_b64("hello")) == "hello"


def test_search_without_index_fails_closed(tmp_path: Path) -> None:
    client = ZoektClient(FIXTURE, tmp_path / "empty-index")
    with pytest.raises(ZoektNotIndexedError):
        client.search("validate_token", 5)
    assert is_zoekt_indexed(tmp_path / "empty-index") is False


def test_empty_query_and_nonpositive_topk_are_caller_errors(tmp_path: Path) -> None:
    client = ZoektClient(FIXTURE, tmp_path / "idx")
    with pytest.raises(ValueError):
        client.search("   ", 5)
    with pytest.raises(ValueError):
        client.search("validate_token", 0)


class _FakeRunner:
    mode = "fake"

    def __init__(self) -> None:
        self.index_calls = 0
        self.index_returncode = 0
        self.search_returncode = 0
        self.search_stdout = ""

    def run_index(self, source_dir: Path, index_dir: Path, timeout_s: float) -> ZoektProcessResult:
        self.index_calls += 1
        assert source_dir.is_dir()
        assert (source_dir / "src" / "auth.py").is_file()
        assert not (source_dir / "ignored" / "secret.py").exists()
        return ZoektProcessResult("", "", self.index_returncode, False)

    def run_search(self, index_dir: Path, query: str, timeout_s: float) -> ZoektProcessResult:
        return ZoektProcessResult(self.search_stdout, "", self.search_returncode, False)


def test_failed_rebuild_does_not_clobber_previous_index(tmp_path: Path) -> None:
    index_dir = tmp_path / "zoekt"
    fake = _FakeRunner()
    fake.search_stdout = json.dumps(
        {
            "FileName": "src/auth.py",
            "Score": 10.0,
            "LineMatches": [{"Line": _b64("validate_token"), "LineNumber": 19, "Score": 10.0}],
        }
    )
    client = ZoektClient(FIXTURE, index_dir, runner=fake)
    stats = client.build_index()
    assert stats.files_indexed >= 6
    assert is_zoekt_indexed(index_dir)
    fake.index_returncode = 1
    with pytest.raises(ZoektIndexError):
        client.build_index()
    assert is_zoekt_indexed(index_dir)
    hits = client.search_codebase("validate_token", 5)
    assert hits[0].file_path == "src/auth.py"
    assert fake.index_calls == 2


def test_docker_argv_is_one_shot_and_network_none(tmp_path: Path) -> None:
    argv = _docker_argv(
        image="ghcr.io/sourcegraph/zoekt",
        entrypoint="zoekt-index",
        extra_mounts=[(tmp_path / "src", "/data/src", True)],
        index_dir=tmp_path / "idx",
        args=["-index", "/data/index", "/data/src"],
    )
    assert argv[0:3] == ["docker", "run", "--rm"]
    assert "--network" in argv and "none" in argv
    assert "zoekt-index" in argv
    assert "ghcr.io/sourcegraph/zoekt" in argv
    assert not any(item == "-d" for item in argv)
