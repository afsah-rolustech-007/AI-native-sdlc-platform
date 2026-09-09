"""Turn source files into embeddable text chunks (Phase 03 Section 04).

Chunking rule:
  - One Tree-sitter symbol → one chunk.
  - Embed: class (header only), function, method (full body).
  - Skip: module, import, broken files.

`content_hash` fingerprints the exact string sent to ModelAdapter.embed()
so incremental updates can skip unchanged symbols (Section 05).
"""

from __future__ import annotations

from repo_intel.exceptions import FileParseError
from repo_intel.indexers.catalog import FileSnapshot, sha256_bytes
from repo_intel.indexers.treesitter import parse_source, slice_source_lines
from repo_intel.models import CodeChunk, Symbol
from repo_intel.vector.constants import (
    CHARS_PER_TOKEN,
    CHUNK_KINDS,
    MAX_CHUNK_CHARS,
)


def chunk_content_hash(chunk_text: str) -> str:
    """SHA-256 of the exact string we send to ModelAdapter.embed()."""
    return sha256_bytes(chunk_text.encode("utf-8"))


def estimate_chunk_tokens(chunk_text: str) -> int:
    """Cheap length hint for Section 06 packing. Not provider billed tokens."""
    if not chunk_text:
        return 0
    return (len(chunk_text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def compose_header(signature: str | None, docstring: str | None) -> str:
    parts: list[str] = []
    signature_text = (signature or "").strip()
    docstring_text = (docstring or "").strip()
    if signature_text:
        parts.append(signature_text)
    if docstring_text:
        parts.append(docstring_text)
    return "\n\n".join(parts)


def compose_chunk_text(signature: str | None, docstring: str | None, body: str) -> str:
    """Build the string that gets embedded for one function/method.

    Order: signature, then docstring, then body — skip parts already inside the body.
    Python: def/class line and docstring are usually already in `body`.
    TypeScript: JSDoc often sits *above* the node, so we prepend it when missing.
    """
    body_stripped = body.strip()
    parts: list[str] = []
    signature_text = (signature or "").strip()
    docstring_text = (docstring or "").strip()
    first_body_line = body_stripped.split("\n", 1)[0] if body_stripped else ""
    if signature_text and signature_text not in first_body_line:
        parts.append(signature_text)
    if docstring_text and docstring_text not in body_stripped:
        parts.append(docstring_text)
    if body_stripped:
        parts.append(body_stripped)
    return "\n\n".join(parts)


def apply_chunk_budget(
    kind: str, signature: str | None, docstring: str | None, body: str
) -> tuple[str, bool]:
    """Return (embed_text, truncated) that never exceeds MAX_CHUNK_CHARS."""
    if kind == "class":
        text = compose_header(signature, docstring)
        if len(text) <= MAX_CHUNK_CHARS:
            return text, False
        return text[:MAX_CHUNK_CHARS], True

    full = compose_chunk_text(signature, docstring, body)
    if len(full) <= MAX_CHUNK_CHARS:
        return full, False
    header = compose_header(signature, docstring)
    if header and len(header) <= MAX_CHUNK_CHARS:
        return header, True
    if header:
        return header[:MAX_CHUNK_CHARS], True
    return full[:MAX_CHUNK_CHARS], True


def ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a <= end_b and start_b <= end_a


def _subsumes(kept: CodeChunk, candidate: CodeChunk) -> bool:
    """True when `kept` already showed the caller the text `candidate` would add.

    A class row spans the whole class but its vector is header-only (signature +
    docstring), so it does NOT contain any method body. Returning the class header
    and a matching method together is complementary, not duplicated — only
    function/method nesting is genuinely redundant.
    """
    if kept.file_path != candidate.file_path:
        return False
    if kept.kind == "class" or candidate.kind == "class":
        return False
    return ranges_overlap(
        candidate.start_line, candidate.end_line, kept.start_line, kept.end_line
    )


def dedupe_overlapping_spans(chunks: list[CodeChunk], top_k: int) -> list[CodeChunk]:
    """Keep higher-score hits; drop later hits whose text a kept hit already covered.

    Collapses nested function/method duplicates (an inner def matching alongside its
    enclosing def). Class headers are exempt — see `_subsumes`.
    Input must already be score-descending (or score=None treated as lowest).
    """
    kept: list[CodeChunk] = []
    for chunk in chunks:
        if any(_subsumes(other, chunk) for other in kept):
            continue
        kept.append(chunk)
        if len(kept) >= top_k:
            break
    return kept


def chunks_from_symbols(symbols: list[Symbol], source_text: str) -> list[CodeChunk]:
    """Convert already-parsed symbols into CodeChunk rows (no DB, no embed yet)."""
    chunks: list[CodeChunk] = []
    for symbol in symbols:
        if symbol.kind not in CHUNK_KINDS:
            continue
        body = slice_source_lines(
            source_text, symbol.start_line, symbol.end_line, file_path=symbol.file_path
        )
        chunk_text, truncated = apply_chunk_budget(
            symbol.kind, symbol.signature, symbol.docstring, body
        )
        if not chunk_text:
            continue
        chunks.append(
            CodeChunk(
                symbol_id=symbol.id,
                file_path=symbol.file_path,
                kind=symbol.kind,
                chunk_text=chunk_text,
                content_hash=chunk_content_hash(chunk_text),
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                chunk_tokens=estimate_chunk_tokens(chunk_text),
                truncated=truncated,
            )
        )
    return chunks


def chunks_from_snapshot(snapshot: FileSnapshot) -> list[CodeChunk]:
    """Parse one file from a catalog walk and return its chunks.

    Returns [] when the file cannot be parsed (syntax error) or is not UTF-8.
    Caller decides whether to log; we do not raise for a single bad file.
    """
    try:
        source_text = snapshot.content.decode("utf-8")
    except UnicodeDecodeError:
        return []
    try:
        symbols = parse_source(snapshot.relative_path, snapshot.content, snapshot.language)
    except FileParseError:
        return []
    return chunks_from_symbols(symbols, source_text)
