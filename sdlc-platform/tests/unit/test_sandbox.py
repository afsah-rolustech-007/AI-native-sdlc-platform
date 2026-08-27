"""Section 04 sandbox tests that do not need Docker."""

from common.sandbox import _container_name


def test_container_name_is_docker_safe_and_includes_task() -> None:
    name = _container_name("task/with spaces!")
    assert name.startswith("sdlc-sbx-")
    assert " " not in name
    assert "/" not in name
