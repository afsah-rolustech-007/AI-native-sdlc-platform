"""Symbol-bounded chunking and content_hash (Phase 03 Section 04)."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.hashing_adapter import hashing_embed

from repo_intel.indexers.catalog import FileSnapshot, sha256_bytes
from repo_intel.indexers.treesitter import parse_file, parse_source
from repo_intel.models import CodeChunk
from repo_intel.tables import EMBEDDING_DIMENSIONS as TABLE_DIM
from repo_intel.vector.chunks import (
    apply_chunk_budget,
    chunk_content_hash,
    chunks_from_snapshot,
    chunks_from_symbols,
    compose_chunk_text,
    dedupe_overlapping_spans,
    estimate_chunk_tokens,
)
from repo_intel.vector.constants import CHUNK_KINDS, EMBEDDING_DIMENSIONS, MAX_CHUNK_CHARS

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


def _by_id(chunks: list) -> dict:
    return {chunk.symbol_id: chunk for chunk in chunks}


def test_pgvector_width_matches_sqlalchemy_column() -> None:
    assert EMBEDDING_DIMENSIONS == TABLE_DIM == 2048


def test_fixture_chunks_are_symbol_bounded_not_line_windows() -> None:
    symbols = parse_file(FIXTURE / "src" / "auth.py", relative_path="src/auth.py")
    source = (FIXTURE / "src" / "auth.py").read_text(encoding="utf-8")
    chunks = chunks_from_symbols(symbols, source)
    by_id = _by_id(chunks)

    assert "src/auth.py::validate_token" in by_id
    assert "src/auth.py::UserService" in by_id
    assert "src/auth.py::UserService.get_user" in by_id
    assert "src/auth.py::module:src.auth" not in by_id
    assert "src/auth.py::import:typing" not in by_id
    assert all(symbol.kind in CHUNK_KINDS for symbol in symbols if symbol.id in by_id)

    validate = by_id["src/auth.py::validate_token"]
    assert validate.kind == "function"
    assert "def validate_token" in validate.chunk_text
    assert "non-whitespace" in validate.chunk_text
    assert "token.strip()" in validate.chunk_text
    assert validate.chunk_tokens == estimate_chunk_tokens(validate.chunk_text)
    assert validate.truncated is False
    expected = next(item for item in symbols if item.id == validate.symbol_id)
    assert validate.start_line == expected.start_line
    assert validate.end_line == expected.end_line

    klass = by_id["src/auth.py::UserService"]
    assert klass.kind == "class"
    assert "Looks up users by id." in klass.chunk_text
    assert "def get_user" not in klass.chunk_text
    assert "def ping" not in klass.chunk_text
    method = by_id["src/auth.py::UserService.get_user"]
    assert "def get_user" in method.chunk_text
    assert method.kind == "method"


def test_typescript_jsdoc_is_prepended_when_outside_the_node() -> None:
    symbols = parse_file(FIXTURE / "src" / "models.ts", relative_path="src/models.ts")
    source = (FIXTURE / "src" / "models.ts").read_text(encoding="utf-8")
    chunks = chunks_from_symbols(symbols, source)
    fmt = _by_id(chunks)["src/models.ts::formatCents"]
    assert "Format cents as a dollar string." in fmt.chunk_text
    assert "function formatCents" in fmt.chunk_text


def test_broken_file_yields_no_chunks() -> None:
    snapshot = FileSnapshot(
        relative_path="src/broken.py",
        content_hash="0" * 64,
        size_bytes=1,
        mtime_ns=0,
        language="python",
        content=(FIXTURE / "src" / "broken.py").read_bytes(),
    )
    assert chunks_from_snapshot(snapshot) == []


def test_content_hash_is_sha256_of_chunk_text_not_the_file() -> None:
    symbols = parse_file(FIXTURE / "src" / "auth.py", relative_path="src/auth.py")
    source = (FIXTURE / "src" / "auth.py").read_text(encoding="utf-8")
    file_hash = sha256_bytes((FIXTURE / "src" / "auth.py").read_bytes())
    validate = _by_id(chunks_from_symbols(symbols, source))["src/auth.py::validate_token"]
    assert validate.content_hash == chunk_content_hash(validate.chunk_text)
    assert validate.content_hash != file_hash
    assert len(validate.content_hash) == 64


def test_editing_another_function_does_not_change_this_chunk_hash() -> None:
    original = (FIXTURE / "src" / "auth.py").read_text(encoding="utf-8")
    edited = original.replace('return "ok"', 'return "pong"')
    assert edited != original
    original_chunks = _by_id(
        chunks_from_symbols(
            parse_file(FIXTURE / "src" / "auth.py", relative_path="src/auth.py"), original
        )
    )
    edited_symbols = parse_source("src/auth.py", edited.encode("utf-8"), "python")
    edited_chunks = _by_id(chunks_from_symbols(edited_symbols, edited))
    assert (
        original_chunks["src/auth.py::validate_token"].content_hash
        == edited_chunks["src/auth.py::validate_token"].content_hash
    )
    assert (
        original_chunks["src/auth.py::UserService.ping"].content_hash
        != edited_chunks["src/auth.py::UserService.ping"].content_hash
    )


def test_compose_skips_signature_already_in_the_body() -> None:
    body = "def foo() -> None:\n    return\n"
    assert compose_chunk_text("def foo() -> None", None, body) == body.strip()


def test_hashing_embedder_ranks_validate_token_in_top_fixture_chunks() -> None:
    query = hashing_embed(["function that validates user input"])[0]
    scored: list[tuple[float, str]] = []
    for relative, language in (
        ("src/auth.py", "python"),
        ("src/payments.py", "python"),
        ("src/uncommitted.py", "python"),
        ("src/models.ts", "typescript"),
        ("src/ui.tsx", "tsx"),
    ):
        source = (FIXTURE / relative).read_text(encoding="utf-8")
        symbols = parse_source(relative, source.encode("utf-8"), language)
        for chunk in chunks_from_symbols(symbols, source):
            vector = hashing_embed([chunk.chunk_text])[0]
            score = sum(a * b for a, b in zip(query, vector, strict=True))
            scored.append((score, chunk.symbol_id or ""))
    scored.sort(reverse=True)
    top_ids = [symbol_id for _score, symbol_id in scored[:5]]
    assert "src/auth.py::validate_token" in top_ids, top_ids


def test_hashing_embedder_ranks_validate_token_above_format_cents() -> None:
    auth = (FIXTURE / "src" / "auth.py").read_text(encoding="utf-8")
    models = (FIXTURE / "src" / "models.ts").read_text(encoding="utf-8")
    validate = _by_id(
        chunks_from_symbols(
            parse_file(FIXTURE / "src" / "auth.py", relative_path="src/auth.py"), auth
        )
    )["src/auth.py::validate_token"]
    fmt = _by_id(
        chunks_from_symbols(
            parse_file(FIXTURE / "src" / "models.ts", relative_path="src/models.ts"), models
        )
    )["src/models.ts::formatCents"]
    query = hashing_embed(["function that validates user input"])[0]
    sim_validate = sum(
        a * b for a, b in zip(query, hashing_embed([validate.chunk_text])[0], strict=True)
    )
    sim_format = sum(a * b for a, b in zip(query, hashing_embed([fmt.chunk_text])[0], strict=True))
    assert sim_validate > sim_format


def test_nested_class_chunks_are_headers_methods_keep_bodies() -> None:
    source = (
        "class Outer:\n"
        '    """Outer docs."""\n'
        "    class Inner:\n"
        '        """Inner docs."""\n'
        "        def meth(self) -> int:\n"
        "            return 1\n"
    )
    symbols = parse_source("nested.py", source.encode("utf-8"), "python")
    chunks = _by_id(chunks_from_symbols(symbols, source))
    assert "return 1" not in chunks["nested.py::Outer"].chunk_text
    assert "return 1" not in chunks["nested.py::Outer.Inner"].chunk_text
    assert "return 1" in chunks["nested.py::Outer.Inner.meth"].chunk_text
    assert chunks["nested.py::Outer"].end_line >= chunks["nested.py::Outer.Inner.meth"].end_line


def test_oversized_function_falls_back_to_header_and_sets_truncated() -> None:
    signature = "def huge() -> str:"
    docstring = "A large function."
    body = (
        signature
        + '\n    """A large function."""\n    return "'
        + ("x" * (MAX_CHUNK_CHARS + 50))
        + '"\n'
    )
    text, truncated = apply_chunk_budget("function", signature, docstring, body)
    assert truncated is True
    assert len(text) <= MAX_CHUNK_CHARS
    assert "A large function." in text
    assert "x" * 50 not in text


def _hit(
    symbol_id: str,
    *,
    start: int,
    end: int,
    score: float,
    kind: str = "method",
) -> CodeChunk:
    return CodeChunk(
        symbol_id=symbol_id,
        file_path="src/auth.py",
        kind=kind,
        chunk_text=symbol_id,
        content_hash="a" * 64,
        start_line=start,
        end_line=end,
        chunk_tokens=1,
        score=score,
    )


def test_dedupe_collapses_nested_function_duplicates() -> None:
    """An inner def and its enclosing def embed overlapping source — keep the best one."""
    outer = _hit("src/auth.py::outer", start=1, end=20, score=0.91, kind="function")
    inner = _hit("src/auth.py::outer.inner", start=5, end=9, score=0.88, kind="function")
    other = _hit("src/auth.py::validate_token", start=30, end=32, score=0.85, kind="function")

    kept = dedupe_overlapping_spans([outer, inner, other], top_k=5)

    assert [item.symbol_id for item in kept] == ["src/auth.py::outer", "src/auth.py::validate_token"]


def test_dedupe_keeps_a_class_header_and_its_method_together() -> None:
    """A class vector is signature + docstring only, so it does not contain the method."""
    method_hit = _hit("src/auth.py::UserService.get_user", start=9, end=13, score=0.91)
    class_hit = _hit("src/auth.py::UserService", start=6, end=16, score=0.80, kind="class")

    kept = dedupe_overlapping_spans([method_hit, class_hit], top_k=5)

    assert [item.symbol_id for item in kept] == [
        "src/auth.py::UserService.get_user",
        "src/auth.py::UserService",
    ]


def test_dedupe_overlapping_spans_keeps_higher_score() -> None:
    def make(
        symbol_id: str,
        *,
        start: int,
        end: int,
        score: float,
        kind: str = "method",
    ) -> CodeChunk:
        return CodeChunk(
            symbol_id=symbol_id,
            file_path="src/auth.py",
            kind=kind,
            chunk_text=symbol_id,
            content_hash="a" * 64,
            start_line=start,
            end_line=end,
            chunk_tokens=1,
            score=score,
        )

    winner = make("src/auth.py::UserService.get_user", start=9, end=13, score=0.91)
    loser = make("src/auth.py::UserService.get_user_inner", start=10, end=12, score=0.70)
    other = make("src/auth.py::validate_token", start=19, end=21, score=0.85, kind="function")
    kept = dedupe_overlapping_spans([winner, other, loser], top_k=5)
    ids = [item.symbol_id for item in kept]
    assert ids == ["src/auth.py::UserService.get_user", "src/auth.py::validate_token"]


def test_dedupe_overlapping_spans_caps_at_top_k() -> None:
    hits = [
        CodeChunk(
            symbol_id=f"a.py::f{i}",
            file_path="b.py" if i else "a.py",
            kind="function",
            chunk_text="x",
            content_hash="b" * 64,
            start_line=i * 10,
            end_line=i * 10 + 1,
            chunk_tokens=1,
            score=1.0 - i * 0.01,
        )
        for i in range(4)
    ]
    kept = dedupe_overlapping_spans(hits, top_k=2)
    assert len(kept) == 2
