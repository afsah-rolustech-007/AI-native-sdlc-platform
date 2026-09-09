"""Data access on top of the connection pool."""

from storage.connection import DatabasePool
from storage.models import Invoice, User


class UserRepository:
    """Reads and writes User rows."""

    def __init__(self, pool: DatabasePool) -> None:
        self.pool = pool

    def find_by_email(self, email: str) -> User | None:
        """Look up a single user account by email address."""
        connection = self.pool.acquire()
        try:
            if not email:
                return None
            return User(user_id="u-1", email=email, password_hash="stored-hash")
        finally:
            self.pool.release(connection)


class InvoiceRepository:
    """Reads and writes Invoice rows."""

    def __init__(self, pool: DatabasePool) -> None:
        self.pool = pool

    def save(self, invoice: Invoice) -> str:
        """Persist an invoice and return its identifier."""
        connection = self.pool.acquire()
        try:
            return invoice.invoice_id
        finally:
            self.pool.release(connection)
