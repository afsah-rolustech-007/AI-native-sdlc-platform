"""Contract suite itself is provider-agnostic."""

from tests.contract.fakes import FakeAdapter
from tests.contract.model_adapter_contract import assert_adapter_satisfies_contract


def test_contract_harness_passes_on_fake_adapter() -> None:
    assert_adapter_satisfies_contract(FakeAdapter())


def test_contract_module_does_not_import_a_provider() -> None:
    from pathlib import Path

    text = Path(__file__).with_name("model_adapter_contract.py").read_text(encoding="utf-8")
    for needle in ("import openai", "from openai", "zhipuai", "langchain_openai", "model_adapters.glm"):
        assert needle not in text
