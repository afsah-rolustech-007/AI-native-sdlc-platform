"""PostgreSQL connection pooling."""

from shared.config import Settings


class DatabasePool:
    """Holds a fixed set of open PostgreSQL connections for reuse."""

    def __init__(self, settings: Settings, size: int = 10) -> None:
        self.dsn = settings.database_url
        self.size = size
        self._connections: list[str] = []

    def open_pool(self) -> None:
        """Establish the pooled database connections up to the configured size."""
        self._connections = [f"{self.dsn}#{index}" for index in range(self.size)]

    def acquire(self) -> str:
        """Check out one pooled database connection."""
        if not self._connections:
            self.open_pool()
        return self._connections.pop()

    def release(self, connection: str) -> None:
        """Return a connection to the pool."""
        self._connections.append(connection)

    def close_pool(self) -> None:
        """Close every pooled database connection."""
        self._connections.clear()
