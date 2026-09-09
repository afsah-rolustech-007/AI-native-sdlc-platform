"""Password hashing and comparison."""

import hashlib
import hmac
import os


def hash_password(plaintext: str) -> str:
    """Derive a salted PBKDF2 hash for storage."""
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), salt, 100_000)
    return f"{salt.hex()}${derived.hex()}"


def verify_password(plaintext: str, stored: str) -> bool:
    """Constant-time compare a plaintext password against a stored hash."""
    salt_hex, _, expected_hex = stored.partition("$")
    if not expected_hex:
        return False
    derived = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(derived.hex(), expected_hex)
