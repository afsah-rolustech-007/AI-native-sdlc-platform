"""Python import and call facts from a Tree-sitter tree (Section 01 grammar)."""

from __future__ import annotations

from tree_sitter import Node, Query, QueryCursor, Tree

from repo_intel.graph.refs import CallRef, ImportRef
from repo_intel.indexers.node_text import decode_node, node_line_range
from repo_intel.indexers.python_symbols import PY_LANGUAGE
from repo_intel.models import Symbol

_CALL_QUERY = Query(
    PY_LANGUAGE,
    """
(call
  function: (identifier) @callee)

(call
  function: (attribute
    object: (_) @obj
    attribute: (identifier) @attr))
""",
)

_CALLABLE_KINDS = frozenset({"function", "method"})
_DEF_TYPES = frozenset({"function_definition", "class_definition"})


def extract_python_refs(
    relative_path: str, source: bytes, tree: Tree, symbols: list[Symbol]
) -> tuple[list[ImportRef], list[CallRef]]:
    imports = _imports(relative_path, source, tree.root_node)
    calls = _calls(relative_path, source, tree, symbols)
    return imports, calls


def _imports(relative_path: str, source: bytes, root: Node) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for node in _walk(root):
        if node.type == "import_statement":
            refs.append(_import_statement(relative_path, source, node))
        elif node.type == "import_from_statement":
            refs.append(_import_from(relative_path, source, node))
    return refs


def _import_statement(relative_path: str, source: bytes, node: Node) -> ImportRef:
    names: list[tuple[str, str]] = []
    modules: list[str] = []
    for index, child in enumerate(node.children):
        if node.field_name_for_child(index) != "name":
            continue
        original, local = _alias_pair(source, child)
        modules.append(original)
        names.append((local, original.split(".")[-1]))
    module = modules[0] if len(modules) == 1 else ",".join(modules)
    return ImportRef(relative_path, module, tuple(names), relative_level=0)


def _import_from(relative_path: str, source: bytes, node: Node) -> ImportRef:
    level, module = _from_module(source, node)
    names: list[tuple[str, str]] = []
    for index, child in enumerate(node.children):
        if node.field_name_for_child(index) != "name":
            continue
        if child.type == "wildcard_import":
            names.append(("*", "*"))
            continue
        original, local = _alias_pair(source, child)
        names.append((local, original))
    return ImportRef(relative_path, module, tuple(names), relative_level=level)


def _from_module(source: bytes, node: Node) -> tuple[int, str]:
    level = 0
    module = ""
    for child in node.children:
        if child.type == "relative_import":
            text = decode_node(source, child)
            level = text.count(".")
            module = text.lstrip(".")
    named = node.child_by_field_name("module_name")
    if named is not None:
        module = decode_node(source, named)
    return level, module


def _alias_pair(source: bytes, node: Node) -> tuple[str, str]:
    if node.type == "aliased_import":
        inner = node.child_by_field_name("name")
        alias = node.child_by_field_name("alias")
        original = decode_node(source, inner) if inner is not None else decode_node(source, node)
        local = decode_node(source, alias) if alias is not None else original
        return original, local
    text = decode_node(source, node)
    return text, text


def _calls(relative_path: str, source: bytes, tree: Tree, symbols: list[Symbol]) -> list[CallRef]:
    refs: list[CallRef] = []
    for _pattern, captures in QueryCursor(_CALL_QUERY).matches(tree.root_node):
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
    if node.type == "call":
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
            if parent.type == "function_definition":
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
