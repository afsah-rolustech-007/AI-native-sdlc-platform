"""Bounded allowlist manifest reads — no tree walk, no huge files."""

from __future__ import annotations

from pathlib import Path

from requirements_engine.manifests import ALLOWLIST, MAX_MANIFEST_BYTES, read_manifest_facts


def test_manifest_allowlist_extracts_dependency_names(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"
dependencies = ["fastapi>=0.111", "sqlalchemy[asyncio]>=2.0"]
""",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "18.2.0"}, "devDependencies": {"typescript": "5.4.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("not a manifest", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pyproject.toml").write_text(
        '[project]\ndependencies=["django"]\n', encoding="utf-8"
    )

    facts = {fact.path: fact.names for fact in read_manifest_facts(tmp_path)}

    assert "fastapi" in facts["pyproject.toml"]
    assert "sqlalchemy" in facts["pyproject.toml"]
    assert "react" in facts["package.json"]
    assert "typescript" in facts["package.json"]
    assert "django" not in {name for names in facts.values() for name in names}
    assert "README.md" not in facts
    assert set(facts) <= ALLOWLIST


def test_manifest_size_and_path_limits(tmp_path: Path) -> None:
    huge = tmp_path / "requirements.txt"
    huge.write_text("x" * (MAX_MANIFEST_BYTES + 50), encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example.com/app\nrequire github.com/foo/bar v1.2.3\n")
    nested = tmp_path / "vendor" / "package.json"
    nested.parent.mkdir()
    nested.write_text('{"dependencies": {"left-pad": "1.0.0"}}', encoding="utf-8")

    facts = {fact.path: fact for fact in read_manifest_facts(tmp_path)}

    assert facts["requirements.txt"].truncated is True
    assert facts["requirements.txt"].names == []
    assert "github.com/foo/bar" in facts["go.mod"].names
    # Nested allowlist names are not walked.
    assert "package.json" not in facts
    assert "left-pad" not in {name for fact in facts.values() for name in fact.names}


def test_missing_manifests_are_omissions_not_errors(tmp_path: Path) -> None:
    assert read_manifest_facts(tmp_path) == []
