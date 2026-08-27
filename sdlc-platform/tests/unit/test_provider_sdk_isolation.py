"""Provider SDKs may only be imported under packages/model_adapters/glm/."""

from pathlib import Path

_FORBIDDEN = (
    "import openai",
    "from openai",
    "import zhipuai",
    "from zhipuai",
    "import zai",
    "from zai",
    "langchain_openai",
    "zai-sdk",
)


def test_provider_sdk_imports_only_in_glm_package() -> None:
    root = Path(__file__).resolve().parents[2]
    allowed = root / "packages" / "model_adapters" / "glm"
    offenders: list[str] = []
    for folder in ("packages", "apps"):
        for path in (root / folder).rglob("*.py"):
            if allowed in path.parents or path.parent == allowed:
                continue
            text = path.read_text(encoding="utf-8")
            for needle in _FORBIDDEN:
                if needle in text:
                    offenders.append(f"{path.relative_to(root)}:{needle}")
    assert offenders == []
