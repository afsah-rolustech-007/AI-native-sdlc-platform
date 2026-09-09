"""Bearer token issuing and verification."""

import hashlib
import time

from shared.config import Settings


class TokenError(Exception):
    """Raised when a bearer token is malformed, expired, or has a bad signature."""


def issue_token(settings: Settings, user_id: str, ttl_seconds: int = 3600) -> str:
    """Mint a signed bearer token for a user id."""
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{user_id}.{expires_at}"
    signature = hashlib.sha256((payload + settings.secret_key).encode()).hexdigest()
    return f"{payload}.{signature}"


def verify_token(settings: Settings, token: str) -> str:
    """Check a bearer token's signature and expiry, then return the user id.

    Raises TokenError when the signature does not match or the token has expired.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("token is not user.expiry.signature")
    user_id, raw_expiry, signature = parts
    expected = hashlib.sha256((f"{user_id}.{raw_expiry}" + settings.secret_key).encode()).hexdigest()
    if signature != expected:
        raise TokenError("bad token signature")
    if int(raw_expiry) < int(time.time()):
        raise TokenError("token expired")
    return user_id
