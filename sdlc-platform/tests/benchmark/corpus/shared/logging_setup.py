"""Structured logging setup shared by every service."""

import logging

from shared.config import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    """Attach a JSON-ish stream handler and set the level from settings."""
    logger = logging.getLogger("app")
    logger.setLevel(settings.log_level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger
