"""Retry helper.

Adversarial on purpose: the docstrings mention "connection" and "database", but
nothing here opens a connection. A query for database connection pooling that
ranks this first is a semantic false positive.
"""

import time
from collections.abc import Callable


def retry_with_backoff(operation: Callable[[], object], attempts: int = 3) -> object:
    """Retry a flaky operation, for example a dropped database connection."""
    delay = 0.1
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - retry wrapper is intentionally broad
            last_error = exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"operation failed after {attempts} attempts: {last_error}")
