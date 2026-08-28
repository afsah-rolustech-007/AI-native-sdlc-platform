"""Extract TypeScript/TSX symbols from a Tree-sitter tree via queries."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_typescript as tstypescript
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
)
from repo_intel.models import Symbol

TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

# Arrow-function `const foo = () => {}` is a known v1 gap (additive later).
TYPESCRIPT_SYMBOL_QUERY = """
(class_declaration
  name: (type_identifier) @name
) @def

(abstract_class_declaration
  name: (type_identifier) @name
) @def

(function_declaration
  name: (identifier) @name
) @def

(generator_function_declaration
  name: (identifier) @name
) @def

(method_definition
  name: [(property_identifier) (private_property_identifier)] @name
) @def

(import_statement) @import
"""

_TS_QUERY = Query(TS_LANGUAGE, TYPESCRIPT_SYMBOL_QUERY)
_TSX_QUERY = Query(TSX_LANGUAGE, TYPESCRIPT_SYMBOL_QUERY)


def extract_typescript_symbols(
    relative_path: str, source: bytes, tree: Tree, *, grammar: str
) -> list[Symbol]:
    query = _TSX_QUERY if grammar == "tsx" else _TS_QUERY
    symbols: list[Symbol] = [_module_symbol(relative_path, source, tree.root_node)]
    for _pattern, captures in QueryCursor(query).matches(tree.root_node):
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
    if node.type in {"class_declaration", "abstract_class_declaration"}:
        kind = "class"
    elif node.type == "method_definition" or has_enclosing_class(node):
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
        docstring=_jsdoc_for(source, node),
    )


def _import_symbol(relative_path: str, source: bytes, node: Node) -> Symbol:
    name = _typescript_import_name(source, node)
    return make_symbol(
        file_path=relative_path,
        kind="import",
        name=name,
        qualified_name=f"import:{name}",
        node=node,
        signature=decode_node(source, node).strip(),
        docstring=None,
    )


def _typescript_import_name(source: bytes, node: Node) -> str:
    for child in node.named_children:
        if child.type == "string":
            return decode_node(source, child).strip("\"'")
    return decode_node(source, node).strip()


def _jsdoc_for(source: bytes, node: Node) -> str | None:
    """JSDoc is typically a named sibling of `export_statement`, not of the inner decl."""
    target = node
    parent = node.parent
    if parent is not None and parent.type == "export_statement":
        target = parent
    prev = target.prev_named_sibling
    if prev is None or prev.type != "comment":
        return None
    return _strip_jsdoc(decode_node(source, prev))


def _strip_jsdoc(raw: str) -> str | None:
    text = raw.strip()
    if not text.startswith("/**"):
        return None
    if text.endswith("*/"):
        text = text[3:-2]
    else:
        text = text[3:]
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("*"):
            stripped = stripped[1:].lstrip()
        lines.append(stripped)
    cleaned = "\n".join(lines).strip()
    return cleaned or None
