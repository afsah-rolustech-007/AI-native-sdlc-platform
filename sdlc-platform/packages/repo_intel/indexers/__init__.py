"""Working-tree indexers. Agents must not import these; use RepositoryIntelligence later."""

from repo_intel.indexers.catalog import walk_working_tree
from repo_intel.indexers.treesitter import (
    get_file_structure,
    get_symbol_body,
    get_symbol_signature,
    index_repo,
    parse_file,
)
from repo_intel.indexers.zoekt_client import ZoektClient, search_codebase

__all__ = [
    "ZoektClient",
    "get_file_structure",
    "get_symbol_body",
    "get_symbol_signature",
    "index_repo",
    "parse_file",
    "search_codebase",
    "walk_working_tree",
]
