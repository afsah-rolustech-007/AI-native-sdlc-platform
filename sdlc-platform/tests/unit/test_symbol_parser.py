"""Tree-sitter parse_file tests against the fixture working tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_intel.exceptions import FileParseError
from repo_intel.indexers.treesitter import parse_file, parse_source, slice_source_lines
from repo_intel.models import Symbol

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


def _by_id(symbols: list[Symbol]) -> dict[str, Symbol]:
    return {symbol.id: symbol for symbol in symbols}


def test_python_symbols_include_class_methods_functions_imports_and_docstrings() -> None:
    symbols = parse_file(FIXTURE / "src" / "auth.py", relative_path="src/auth.py")
    by_id = _by_id(symbols)

    user_service = by_id["src/auth.py::UserService"]
    assert user_service.kind == "class"
    assert user_service.name == "UserService"
    assert user_service.signature == "class UserService"
    assert user_service.docstring == "Looks up users by id."
    assert user_service.start_line < user_service.end_line

    get_user = by_id["src/auth.py::UserService.get_user"]
    assert get_user.kind == "method"
    assert get_user.signature is not None
    assert "def get_user" in get_user.signature
    assert get_user.docstring == "Return a user dict or None if missing."

    ping = by_id["src/auth.py::UserService.ping"]
    assert ping.kind == "method"
    assert ping.signature is not None
    assert ping.signature.startswith("async def ping")

    validate = by_id["src/auth.py::validate_token"]
    assert validate.kind == "function"
    assert validate.docstring is not None
    assert "non-whitespace" in validate.docstring

    typing_import = by_id["src/auth.py::import:typing"]
    assert typing_import.kind == "import"
    assert typing_import.signature == "from typing import Optional"

    module = by_id["src/auth.py::module:src.auth"]
    assert module.kind == "module"
    assert module.docstring == "Authentication helpers used by payments."


def test_nested_class_qualified_name(tmp_path: Path) -> None:
    source = tmp_path / "nested.py"
    source.write_text(
        "class Outer:\n    class Inner:\n        def m(self):\n            return 1\n",
        encoding="utf-8",
    )
    by_id = _by_id(parse_file(source, relative_path="nested.py"))
    assert by_id["nested.py::Outer"].kind == "class"
    assert by_id["nested.py::Outer.Inner"].kind == "class"
    assert by_id["nested.py::Outer.Inner.m"].kind == "method"


def test_syntax_error_raises_file_parse_error() -> None:
    with pytest.raises(FileParseError) as exc:
        parse_file(FIXTURE / "src" / "broken.py", relative_path="src/broken.py")
    assert exc.value.relative_path == "src/broken.py"


def test_typescript_class_function_method_and_jsdoc() -> None:
    symbols = parse_file(FIXTURE / "src" / "models.ts", relative_path="src/models.ts")
    by_id = _by_id(symbols)
    ledger = by_id["src/models.ts::Ledger"]
    assert ledger.kind == "class"
    assert ledger.docstring == "In-memory ledger."
    constructor = by_id["src/models.ts::Ledger.constructor"]
    assert constructor.kind == "method"
    total = by_id["src/models.ts::Ledger.total"]
    assert total.kind == "method"
    fmt = by_id["src/models.ts::formatCents"]
    assert fmt.kind == "function"
    assert fmt.docstring == "Format cents as a dollar string."
    imported = by_id["src/models.ts::import:./auth"]
    assert imported.kind == "import"


def test_tsx_function_is_extracted() -> None:
    symbols = parse_file(FIXTURE / "src" / "ui.tsx", relative_path="src/ui.tsx")
    by_id = _by_id(symbols)
    button = by_id["src/ui.tsx::Button"]
    assert button.kind == "function"
    assert button.signature is not None
    assert "Button" in button.signature


def test_payments_import_targets_auth_module() -> None:
    symbols = parse_file(FIXTURE / "src" / "payments.py", relative_path="src/payments.py")
    by_id = _by_id(symbols)
    imported = by_id["src/payments.py::import:src.auth"]
    assert imported.kind == "import"
    assert by_id["src/payments.py::ChargeService.charge"].kind == "method"


def test_slice_source_lines_rejects_out_of_range_ranges() -> None:
    with pytest.raises(Exception, match="does not fit"):
        slice_source_lines("a\nb\n", 1, 9, file_path="x.py")


def test_parse_source_uses_provided_relative_path() -> None:
    content = b"def hello() -> int:\n    return 1\n"
    symbols = parse_source("pkg/mod.py", content, "python")
    assert "pkg/mod.py::hello" in {item.id for item in symbols}
