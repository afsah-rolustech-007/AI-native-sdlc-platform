"""HTTP entry points."""

from auth.service import AuthService
from billing.charges import ChargeProcessor


def login_route(auth: AuthService, body: dict) -> dict:
    """POST /login — exchange email and password for a bearer token."""
    token = auth.login(body["email"], body["password"])
    return {"token": token}


def charge_route(auth: AuthService, charges: ChargeProcessor, body: dict) -> dict:
    """POST /charges — capture a payment for the authenticated caller."""
    user_id = auth.current_user(body["token"])
    invoice_id = charges.charge(user_id, body["amount_cents"])
    return {"invoice_id": invoice_id}
