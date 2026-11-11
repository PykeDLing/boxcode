"""Invoices.

Tax is rounded half up, and the tax on a negative amount (a credit note) is the negative of the tax on the same
positive amount; see docs/POLICY.md. Tax is computed per line and then added up, never on the invoice total.
"""

from money import percent


def tax(amount_cents: int, rate_bp: int) -> int:
    """The tax on one line."""
    return percent(amount_cents, rate_bp)


def total(lines: list[int], rate_bp: int) -> dict:
    """Net, tax and gross of an invoice whose lines are net amounts in cents."""
    net = sum(lines)
    tax_cents = sum(tax(line, rate_bp) for line in lines)
    return {"net": net, "tax": tax_cents, "gross": net + tax_cents}
