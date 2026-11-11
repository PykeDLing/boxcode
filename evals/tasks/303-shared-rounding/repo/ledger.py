"""Ledger postings.

Interest and fees are rounded half to even, as docs/POLICY.md requires for everything posted to the ledger.
"""

from money import divide, percent


def fee(amount_cents: int, rate_bp: int) -> int:
    """The fee on a posting."""
    return percent(amount_cents, rate_bp)


def monthly_interest(balance_cents: int, annual_rate_bp: int) -> int:
    """One month of interest: a twelfth of the annual interest."""
    return divide(percent(balance_cents, annual_rate_bp), 12)


def split(total_cents: int, parts: int) -> list[int]:
    """Split a total into `parts` shares that add up to the total exactly.

    Every share is the total divided by `parts` (rounded as the ledger rounds), except the last one,
    which takes whatever is left.
    """
    share = divide(total_cents, parts)
    return [share] * (parts - 1) + [total_cents - share * (parts - 1)]
