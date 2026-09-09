"""Repository Intelligence errors. Retrieval must fail closed — never look like success."""

from __future__ import annotations


class RepoIntelError(Exception):
    """Base error for the symbol index. Callers should not catch this to return empty results."""


class StaleIndexError(RepoIntelError):
    """Working-tree bytes no longer match the SHA-256 catalog for one or more paths.

    Section 05 will use this for whole-tree retrieval. Section 01 raises it when a
    queried file's disk hash does not match `indexed_files.content_hash`.
    """

    def __init__(self, stale_paths: list[str], message: str | None = None) -> None:
        self.stale_paths = list(stale_paths)
        detail = message or (
            "working tree does not match the indexed catalog for: " + ", ".join(self.stale_paths)
        )
        super().__init__(detail)


class FileParseError(RepoIntelError):
    """One source file has syntax errors. `index_repo` logs this and continues."""

    def __init__(self, relative_path: str, detail: str) -> None:
        self.relative_path = relative_path
        self.detail = detail
        super().__init__(f"parse failed for {relative_path}: {detail}")


class FileNotIndexedError(RepoIntelError):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        super().__init__(f"file is not in the catalog: {relative_path}")


class SymbolNotFoundError(RepoIntelError):
    def __init__(self, symbol_id: str) -> None:
        self.symbol_id = symbol_id
        super().__init__(f"symbol not found: {symbol_id}")


class UnsupportedLanguageError(RepoIntelError):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        super().__init__(f"no Tree-sitter grammar registered for {relative_path}")


class FileTooLargeError(RepoIntelError):
    def __init__(self, relative_path: str, size_bytes: int, max_bytes: int) -> None:
        self.relative_path = relative_path
        super().__init__(
            f"{relative_path} is {size_bytes} bytes; max indexable size is {max_bytes}"
        )


class ZoektUnavailableError(RepoIntelError):
    """Zoekt binaries (or the packaged image) are not available on this machine."""


class ZoektNotIndexedError(RepoIntelError):
    """No Zoekt index has been built for this working tree.

    Search must not return an empty hit list for this case — that would look
    like "no matches" instead of "we have not indexed yet."
    """

    def __init__(self, index_dir: str) -> None:
        self.index_dir = index_dir
        super().__init__(
            f"no Zoekt index at {index_dir}; call ZoektClient.build_index before search"
        )


class ZoektIndexError(RepoIntelError):
    """zoekt-index failed. A previous good index, if any, is left in place."""


class ZoektSearchError(RepoIntelError):
    """The Zoekt search process failed. Results must not be treated as complete."""


class GraphNotBuiltError(RepoIntelError):
    """Graph queries ran before NetworkXClient.build. Empty is not a valid answer."""


class EmbeddingsNotIndexedError(RepoIntelError):
    """No embedding rows for this working tree. Empty is not a valid search answer."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        super().__init__(
            f"no code embeddings for {repo_root}; "
            "call PgvectorClient.index_working_tree before search"
        )


class EmbeddingIndexError(RepoIntelError):
    """Embedding or pgvector write failed. Search must not treat this as zero hits."""


class EmbeddingDimensionError(EmbeddingIndexError):
    """Adapter returned a vector whose length does not match the pgvector column."""

    def __init__(self, got: int, expected: int) -> None:
        self.got = got
        self.expected = expected
        super().__init__(
            f"embedding length is {got}, expected {expected}. "
            "The code_embeddings column is fixed-width; do not store a mismatched vector."
        )
