"""Process entry point."""

from auth.service import AuthService
from billing.charges import ChargeProcessor
from shared.config import load_settings
from shared.logging_setup import configure_logging
from storage.connection import DatabasePool
from storage.repository import InvoiceRepository, UserRepository


def build_app() -> tuple[AuthService, ChargeProcessor]:
    """Wire settings, the connection pool, repositories, and services together."""
    settings = load_settings()
    configure_logging(settings)
    pool = DatabasePool(settings)
    pool.open_pool()
    auth = AuthService(settings, UserRepository(pool))
    charges = ChargeProcessor(InvoiceRepository(pool))
    return auth, charges


def main() -> None:
    """Start the service."""
    build_app()
