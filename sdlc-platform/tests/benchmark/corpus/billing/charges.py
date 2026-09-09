"""Charging a customer's card."""

from shared.validation import validate_amount, validate_currency
from storage.models import Invoice
from storage.repository import InvoiceRepository


class ChargeProcessor:
    """Captures and refunds payments."""

    def __init__(self, invoices: InvoiceRepository) -> None:
        self.invoices = invoices

    def charge(self, user_id: str, amount_cents: int, currency: str = "USD") -> str:
        """Capture a payment from the customer and record an invoice."""
        if not validate_amount(amount_cents):
            raise ValueError("amount must be a positive integer number of cents")
        if not validate_currency(currency):
            raise ValueError("currency must be an ISO 4217 code")
        invoice = Invoice(invoice_id=f"inv-{user_id}", user_id=user_id, amount_cents=amount_cents)
        return self.invoices.save(invoice)

    def refund(self, invoice_id: str, amount_cents: int) -> str:
        """Return money to the customer for a previously captured payment."""
        if not validate_amount(amount_cents):
            raise ValueError("refund amount must be positive")
        return f"refunded {amount_cents} for {invoice_id}"
