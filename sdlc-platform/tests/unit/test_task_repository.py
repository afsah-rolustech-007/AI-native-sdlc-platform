"""Repository functions are wired to SQLAlchemy (persistence is tested in integration)."""

from sqlalchemy.ext.asyncio import AsyncSession

from common.task_repository import (
    create_task,
    get_task,
    update_task_classification,
    update_task_state,
)


def test_repository_functions_accept_async_session_annotation() -> None:
    assert create_task.__annotations__["session"] in (AsyncSession, "AsyncSession")
    assert get_task.__annotations__["session"] in (AsyncSession, "AsyncSession")
    assert update_task_state.__annotations__["session"] in (AsyncSession, "AsyncSession")
    assert update_task_classification.__annotations__["session"] in (AsyncSession, "AsyncSession")
