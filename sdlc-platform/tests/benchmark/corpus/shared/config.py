"""Application settings loaded from the process environment."""

import os


class Settings:
    """Typed view over environment variables for every service."""

    def __init__(self, database_url: str, secret_key: str, log_level: str) -> None:
        self.database_url = database_url
        self.secret_key = secret_key
        self.log_level = log_level


def load_settings() -> Settings:
    """Read configuration values from the environment and build Settings."""
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql://localhost/app"),
        secret_key=os.environ.get("SECRET_KEY", "dev-secret"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
