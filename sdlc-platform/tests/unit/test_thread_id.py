"""thread_id is task.id with no extra truncation."""

import inspect

from tests.factories import make_task

from orchestration.checkpointers.postgres import get_thread_id


def test_get_thread_id_is_exactly_task_id() -> None:
    task = make_task(id="task-thread-1")
    assert get_thread_id(task) == "task-thread-1"


def test_get_thread_id_keeps_255_char_id_without_slicing() -> None:
    task_id = "a" * 255
    task = make_task(id=task_id)
    assert get_thread_id(task) == task_id
    assert len(get_thread_id(task)) == 255
    source = inspect.getsource(get_thread_id)
    assert "[:255]" not in source
