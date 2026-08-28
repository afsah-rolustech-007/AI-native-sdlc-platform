"""L1 symbol index and L0/L1 lexical search over the local working tree."""

from repo_intel.exceptions import (
    FileNotIndexedError,
    FileParseError,
    FileTooLargeError,
    RepoIntelError,
    StaleIndexError,
    SymbolNotFoundError,
    UnsupportedLanguageError,
    ZoektIndexError,
    ZoektNotIndexedError,
    ZoektSearchError,
    ZoektUnavailableError,
)
from repo_intel.indexers.catalog import (
    MAX_FILE_SIZE_BYTES,
    FileSnapshot,
    resolve_repo_root,
    walk_working_tree,
)
from repo_intel.indexers.treesitter import (
    get_file_structure,
    get_symbol_body,
    get_symbol_signature,
    index_repo,
    parse_file,
    parse_source,
)
from repo_intel.indexers.zoekt_client import ZoektClient, search_codebase
from repo_intel.models import ExtensionParseStats, IndexStats, SearchHit, Symbol

__all__ = [
    "MAX_FILE_SIZE_BYTES",
    "ExtensionParseStats",
    "FileNotIndexedError",
    "FileParseError",
    "FileSnapshot",
    "FileTooLargeError",
    "IndexStats",
    "RepoIntelError",
    "SearchHit",
    "StaleIndexError",
    "Symbol",
    "SymbolNotFoundError",
    "UnsupportedLanguageError",
    "ZoektClient",
    "ZoektIndexError",
    "ZoektNotIndexedError",
    "ZoektSearchError",
    "ZoektUnavailableError",
    "get_file_structure",
    "get_symbol_body",
    "get_symbol_signature",
    "index_repo",
    "parse_file",
    "parse_source",
    "resolve_repo_root",
    "search_codebase",
    "walk_working_tree",
]
