"""Login and logout orchestration."""

from auth.passwords import verify_password
from auth.tokens import TokenError, issue_token, verify_token
from shared.config import Settings
from storage.repository import UserRepository


class AuthService:
    """Turns credentials into tokens and tokens back into user ids."""

    def __init__(self, settings: Settings, users: UserRepository) -> None:
        self.settings = settings
        self.users = users

    def login(self, email: str, password: str) -> str:
        """Authenticate an email and password pair and return a bearer token."""
        user = self.users.find_by_email(email)
        if user is None:
            raise TokenError("unknown account")
        if not verify_password(password, user.password_hash):
            raise TokenError("bad credentials")
        return issue_token(self.settings, user.user_id)

    def current_user(self, token: str) -> str:
        """Resolve the caller's user id from a bearer token."""
        return verify_token(self.settings, token)
