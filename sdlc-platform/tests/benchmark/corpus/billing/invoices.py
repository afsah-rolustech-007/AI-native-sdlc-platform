"""Invoice rendering."""

from storage.models import Invoice


def format_money(amount_cents: int, currency: str = "USD") -> str:
    """Render an integer cent amount as a human-readable currency string."""
    return f"{amount_cents // 100}.{amount_cents % 100:02d} {currency}"


def render_invoice(invoice: Invoice) -> str:
    """Produce the plain-text invoice document sent to the customer."""
    return "\n".join(
        [
            f"Invoice {invoice.invoice_id}",
            f"Customer {invoice.user_id}",
            f"Total {format_money(invoice.amount_cents)}",
        ]
    )
