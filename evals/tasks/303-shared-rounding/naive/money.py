"""Money helpers. All amounts are integer cents; rates are in basis points (1 bp = 0.01 %)."""


def divide(amount_cents: int, divisor: int) -> int:
    """amount_cents / divisor, rounded to the nearest cent. divisor must be positive."""
    if divisor <= 0:
        raise ValueError("divisor must be positive")
    quotient, remainder = divmod(amount_cents, divisor)
    if 2 * remainder >= divisor:
        quotient += 1
    return quotient


def percent(amount_cents: int, rate_bp: int) -> int:
    """rate_bp basis points of amount_cents, rounded to the nearest cent."""
    return divide(amount_cents * rate_bp, 10_000)
