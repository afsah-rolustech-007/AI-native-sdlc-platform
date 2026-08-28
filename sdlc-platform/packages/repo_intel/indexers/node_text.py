"""Shared Tree-sitter helpers: text, line ranges, qualified names, signatures."""

from __future__ import annotations

from tree_sitter import Node

from repo_intel.models import Symbol

_CLASS_NODE_TYPES = frozenset(
    {"class_definition", "class_declaration", "abstract_class_declaration"}
)
_FUNCTION_NODE_TYPES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
    }
)


def decode_node(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def node_line_range(node: Node) -> tuple[int, int]:
    """Convert Tree-sitter 0-based points to 1-based inclusive line numbers."""
    start_row, _start_col = _row_col(node.start_point)
    end_row, end_col = _row_col(node.end_point)
    start_line = start_row + 1
    end_line = end_row + 1 if end_col > 0 else max(start_line, end_row)
    return start_line, end_line


def _row_col(point: object) -> tuple[int, int]:
    row = getattr(point, "row", None)
    column = getattr(point, "column", None)
    if row is None or column is None:
        raise TypeError(f"unexpected Tree-sitter point: {point!r}")
    return int(row), int(column)


def dotted_module_name(relative_path: str) -> str:
    posix = relative_path.replace("\\", "/")
    for suffix in (".tsx", ".ts", ".py"):
        if posix.endswith(suffix):
            posix = posix[: -len(suffix)]
            break
    return posix.replace("/", ".")


def enclosing_owner_names(source: bytes, node: Node) -> list[str]:
    """Outermost-first class/function names wrapping `node` (not including `node`)."""
    names: list[str] = []
    parent = node.parent
    while parent is not None:
        if parent.type in _CLASS_NODE_TYPES or parent.type in _FUNCTION_NODE_TYPES:
            name_node = parent.child_by_field_name("name")
            if name_node is not None:
                names.append(decode_node(source, name_node))
        parent = parent.parent
    names.reverse()
    return names


def has_enclosing_class(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in _CLASS_NODE_TYPES:
            return True
        parent = parent.parent
    return False


def header_signature(source: bytes, node: Node) -> str | None:
    """Text from the definition start up to (not including) the body."""
    body = node.child_by_field_name("body")
    if body is None:
        text = decode_node(source, node).strip()
        return text or None
    raw = source[node.start_byte : body.start_byte].decode("utf-8").strip()
    if raw.endswith(":"):
        raw = raw[:-1].strip()
    return raw or None


def unquote_python_string(raw: str) -> str:
    text = raw.strip()
    while text and text[0] in "rRuUfFbB":
        text = text[1:]
    if len(text) >= 6 and (
        (text.startswith('"""') and text.endswith('"""'))
        or (text.startswith("'''") and text.endswith("'''"))
    ):
        return text[3:-3]
    if len(text) >= 2 and (
        (text.startswith('"') and text.endswith('"'))
        or (text.startswith("'") and text.endswith("'"))
    ):
        return text[1:-1]
    return text


def python_docstring(source: bytes, definition_node: Node) -> str | None:
    body = definition_node.child_by_field_name("body")
    if body is None:
        return None
    for child in body.children:
        if not child.is_named:
            continue
        if child.type == "expression_statement" and child.named_child_count > 0:
            inner = child.named_children[0]
            if inner.type == "string":
                return unquote_python_string(decode_node(source, inner))
        return None
    return None


def module_docstring(source: bytes, root: Node) -> str | None:
    for child in root.children:
        if not child.is_named:
            continue
        if child.type == "expression_statement" and child.named_child_count > 0:
            inner = child.named_children[0]
            if inner.type == "string":
                return unquote_python_string(decode_node(source, inner))
        return None
    return None


def make_symbol(
    *,
    file_path: str,
    kind: str,
    name: str,
    qualified_name: str,
    node: Node,
    signature: str | None,
    docstring: str | None,
) -> Symbol:
    start_line, end_line = node_line_range(node)
    return Symbol(
        id=f"{file_path}::{qualified_name}",
        kind=kind,
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        signature=signature,
        docstring=docstring,
    )


def dedupe_symbols(symbols: list[Symbol]) -> list[Symbol]:
    """Keep the first symbol for each id. Duplicate imports must not abort the file."""
    by_id: dict[str, Symbol] = {}
    for symbol in symbols:
        if symbol.id not in by_id:
            by_id[symbol.id] = symbol
    return sorted(by_id.values(), key=lambda item: (item.start_line, item.end_line, item.id))
