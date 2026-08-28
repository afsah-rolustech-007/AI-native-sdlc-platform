"""Charges a user after validating a token."""

from src.auth import UserService, validate_token


class ChargeService:
    """Create charges for a user."""

    def charge(self, user_id: str, token: str, amount: int) -> str:
        """Charge amount if the token is valid."""
        if not validate_token(token):
            raise ValueError("invalid token")
        user = UserService().get_user(user_id)
        if user is None:
            raise ValueError("unknown user")
        return f"charged {amount} to {user['id']}"
