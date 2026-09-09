"""Input validation helpers.

Deliberately adjacent to auth/tokens.py in wording: both talk about "valid".
A concept query for token validation must not settle for these.
"""


def validate_email(value: str) -> bool:
    """Return True when the string looks like an email address."""
    return "@" in value and "." in value.split("@")[-1]


def validate_amount(value: int) -> bool:
    """Return True when the amount is a positive whole number of cents."""
    return isinstance(value, int) and value > 0


def validate_currency(code: str) -> bool:
    """Return True for a three-letter ISO currency code."""
    return len(code) == 3 and code.isalpha() and code.isupper()
