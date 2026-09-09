"""Working-tree indexers. Agents must not import these; use RepositoryIntelligence later."""

from repo_intel.indexers.catalog import diff_snapshots, read_paths, walk_working_tree
from repo_intel.indexers.incremental import IncrementalIndexer
from repo_intel.indexers.treesitter import (
    get_file_structure,
    get_symbol_body,
    get_symbol_signature,
    index_repo,
    parse_file,
)
from repo_intel.indexers.zoekt_client import ZoektClient, search_codebase

__all__ = [
    "IncrementalIndexer",
    "ZoektClient",
    "diff_snapshots",
    "get_file_structure",
    "get_symbol_body",
    "get_symbol_signature",
    "index_repo",
    "parse_file",
    "read_paths",
    "search_codebase",
    "walk_working_tree",
]
