"""Authentication helpers used by payments."""

from typing import Optional


class UserService:
    """Looks up users by id."""

    def get_user(self, user_id: str) -> Optional[dict]:
        """Return a user dict or None if missing."""
        if not user_id:
            return None
        return {"id": user_id}

    async def ping(self) -> str:
        return "ok"


def validate_token(token: str) -> bool:
    """Return True when the token has non-whitespace content."""
    return bool(token.strip())
