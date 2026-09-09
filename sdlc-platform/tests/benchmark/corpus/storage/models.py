"""Persistence entities."""


class User:
    """A registered account row."""

    def __init__(self, user_id: str, email: str, password_hash: str) -> None:
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash


class Session:
    """A server-side login session row."""

    def __init__(self, session_id: str, user_id: str, expires_at: int) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.expires_at = expires_at


class Invoice:
    """A billing document row for one customer."""

    def __init__(self, invoice_id: str, user_id: str, amount_cents: int) -> None:
        self.invoice_id = invoice_id
        self.user_id = user_id
        self.amount_cents = amount_cents
