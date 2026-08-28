"""Extract Python symbols from a Tree-sitter tree via queries."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Query, QueryCursor, Tree

from repo_intel.indexers.node_text import (
    decode_node,
    dedupe_symbols,
    dotted_module_name,
    enclosing_owner_names,
    has_enclosing_class,
    header_signature,
    make_symbol,
    module_docstring,
    python_docstring,
)
from repo_intel.models import Symbol

PY_LANGUAGE = Language(tspython.language())

# Queries find definitions; ancestor walks fill qualified names (Class.method).
PYTHON_SYMBOL_QUERY = """
(class_definition
  name: (identifier) @name
) @def

(function_definition
  name: (identifier) @name
) @def

(import_statement) @import

(import_from_statement) @import
"""

_QUERY = Query(PY_LANGUAGE, PYTHON_SYMBOL_QUERY)


def extract_python_symbols(relative_path: str, source: bytes, tree: Tree) -> list[Symbol]:
    symbols: list[Symbol] = [_module_symbol(relative_path, source, tree.root_node)]
    for _pattern, captures in QueryCursor(_QUERY).matches(tree.root_node):
        if "import" in captures:
            symbols.append(_import_symbol(relative_path, source, captures["import"][0]))
            continue
        if "def" not in captures or "name" not in captures:
            continue
        node = captures["def"][0]
        name = decode_node(source, captures["name"][0])
        symbols.append(_definition_symbol(relative_path, source, node, name))
    return dedupe_symbols(symbols)


def _module_symbol(relative_path: str, source: bytes, root: Node) -> Symbol:
    dotted = dotted_module_name(relative_path)
    return make_symbol(
        file_path=relative_path,
        kind="module",
        name=Path(relative_path).name,
        qualified_name=f"module:{dotted}",
        node=root,
        signature=None,
        docstring=module_docstring(source, root),
    )


def _definition_symbol(relative_path: str, source: bytes, node: Node, name: str) -> Symbol:
    owners = enclosing_owner_names(source, node)
    qualified = ".".join([*owners, name])
    if node.type == "class_definition":
        kind = "class"
    elif has_enclosing_class(node):
        kind = "method"
    else:
        kind = "function"
    return make_symbol(
        file_path=relative_path,
        kind=kind,
        name=name,
        qualified_name=qualified,
        node=node,
        signature=header_signature(source, node),
        docstring=python_docstring(source, node),
    )


def _import_symbol(relative_path: str, source: bytes, node: Node) -> Symbol:
    name = _python_import_name(source, node)
    return make_symbol(
        file_path=relative_path,
        kind="import",
        name=name,
        qualified_name=f"import:{name}",
        node=node,
        signature=decode_node(source, node).strip(),
        docstring=None,
    )


def _python_import_name(source: bytes, node: Node) -> str:
    if node.type == "import_from_statement":
        module = node.child_by_field_name("module_name")
        if module is None:
            return "."
        return decode_node(source, module)
    names: list[str] = []
    for index, child in enumerate(node.children):
        if node.field_name_for_child(index) != "name":
            continue
        if child.type == "aliased_import":
            inner = child.child_by_field_name("name")
            names.append(
                decode_node(source, inner) if inner is not None else decode_node(source, child)
            )
        else:
            names.append(decode_node(source, child))
    return ",".join(names) if names else decode_node(source, node).strip()
