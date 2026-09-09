"""TypeScript/TSX import and call facts from a Tree-sitter tree."""

from __future__ import annotations

from tree_sitter import Node, Query, QueryCursor, Tree

from repo_intel.graph.refs import CallRef, ImportRef
from repo_intel.indexers.node_text import decode_node, node_line_range
from repo_intel.indexers.typescript_symbols import TS_LANGUAGE, TSX_LANGUAGE
from repo_intel.models import Symbol

_CALL_QUERY_TEXT = """
(call_expression
  function: (identifier) @callee)

(call_expression
  function: (member_expression
    object: (_) @obj
    property: (property_identifier) @attr))
"""

_TS_CALL = Query(TS_LANGUAGE, _CALL_QUERY_TEXT)
_TSX_CALL = Query(TSX_LANGUAGE, _CALL_QUERY_TEXT)

_CALLABLE_KINDS = frozenset({"function", "method"})
_DEF_TYPES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
        "class_declaration",
        "abstract_class_declaration",
    }
)


def extract_typescript_refs(
    relative_path: str,
    source: bytes,
    tree: Tree,
    symbols: list[Symbol],
    *,
    grammar: str,
) -> tuple[list[ImportRef], list[CallRef]]:
    query = _TSX_CALL if grammar == "tsx" else _TS_CALL
    imports = _imports(relative_path, source, tree.root_node)
    calls = _calls(relative_path, source, tree, symbols, query)
    return imports, calls


def _imports(relative_path: str, source: bytes, root: Node) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for node in _walk(root):
        if node.type != "import_statement":
            continue
        specifier = _ts_specifier(source, node)
        names = _ts_imported_names(source, node)
        refs.append(ImportRef(relative_path, specifier, tuple(names), relative_level=0))
    return refs


def _ts_specifier(source: bytes, node: Node) -> str:
    for child in node.named_children:
        if child.type == "string":
            return decode_node(source, child).strip("\"'")
    return ""


def _ts_imported_names(source: bytes, node: Node) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    for child in _walk(node):
        if child.type == "import_specifier":
            name_node = child.child_by_field_name("name")
            alias = child.child_by_field_name("alias")
            original = decode_node(source, name_node) if name_node is not None else ""
            local = decode_node(source, alias) if alias is not None else original
            if original:
                names.append((local, original))
        elif child.type == "namespace_import":
            ident = next((c for c in child.named_children if c.type == "identifier"), None)
            if ident is not None:
                text = decode_node(source, ident)
                names.append((text, text))
    return names


def _calls(
    relative_path: str,
    source: bytes,
    tree: Tree,
    symbols: list[Symbol],
    query: Query,
) -> list[CallRef]:
    refs: list[CallRef] = []
    for _pattern, captures in QueryCursor(query).matches(tree.root_node):
        if "callee" in captures:
            name_node = captures["callee"][0]
            refs.append(
                CallRef(
                    origin_file=relative_path,
                    caller_id=_caller_id(relative_path, name_node, symbols),
                    simple_name=decode_node(source, name_node),
                    object_name=None,
                )
            )
            continue
        if "attr" not in captures:
            continue
        attr = captures["attr"][0]
        obj = captures.get("obj", [None])[0]
        refs.append(
            CallRef(
                origin_file=relative_path,
                caller_id=_caller_id(relative_path, attr, symbols),
                simple_name=decode_node(source, attr),
                object_name=_object_name(source, obj) if obj is not None else None,
            )
        )
    return refs


def _object_name(source: bytes, node: Node) -> str | None:
    if node.type == "identifier":
        return decode_node(source, node)
    if node.type == "call_expression":
        fn = node.child_by_field_name("function")
        if fn is not None and fn.type == "identifier":
            return decode_node(source, fn)
    return None


def _caller_id(relative_path: str, node: Node, symbols: list[Symbol]) -> str:
    parent = node.parent
    while parent is not None:
        if parent.type in _DEF_TYPES:
            start, _end = node_line_range(parent)
            for symbol in symbols:
                if symbol.kind in _CALLABLE_KINDS and symbol.start_line == start:
                    return symbol.id
            if parent.type in {
                "function_declaration",
                "generator_function_declaration",
                "method_definition",
            }:
                break
        parent = parent.parent
    for symbol in symbols:
        if symbol.kind == "module":
            return symbol.id
    return f"{relative_path}::module:{relative_path.replace('/', '.').rsplit('.', 1)[0]}"


def _walk(node: Node) -> list[Node]:
    out = [node]
    for child in node.children:
        out.extend(_walk(child))
    return out
