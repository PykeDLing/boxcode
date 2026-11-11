import pytest

from invoice import tax, total
from ledger import fee, monthly_interest, split
from money import divide


@pytest.mark.parametrize(("amount", "rate_bp", "expected"), [
    (250, 500, 13), (270, 500, 14), (50, 100, 1), (150, 100, 2), (10, 500, 1), (30, 500, 2),
    (249, 500, 12), (251, 500, 13), (0, 500, 0), (1000, 1900, 190), (1, 4999, 0), (1, 5000, 1),
])
def test_tax_half_up(amount, rate_bp, expected):
    assert tax(amount, rate_bp) == expected


@pytest.mark.parametrize(("amount", "rate_bp"), [(250, 500), (270, 500), (50, 100), (999, 1900), (1, 5000), (30, 500)])
def test_credit_note_mirrors_invoice(amount, rate_bp):
    assert tax(-amount, rate_bp) == -tax(amount, rate_bp)


def test_credit_note_half_cent():
    assert tax(-250, 500) == -13 and tax(-270, 500) == -14 and tax(-249, 500) == -12


def test_total_per_line():
    assert total([250, 250, 270], 500) == {"net": 770, "tax": 40, "gross": 810}
    assert total([250, -250], 500) == {"net": 0, "tax": 0, "gross": 0}
    assert total([], 500) == {"net": 0, "tax": 0, "gross": 0}


@pytest.mark.parametrize(("amount", "rate_bp", "expected"), [
    (250, 500, 12), (270, 500, 14), (50, 100, 0), (150, 100, 2), (10, 500, 0), (30, 500, 2),
    (-250, 500, -12), (-270, 500, -14), (251, 500, 13), (249, 500, 12),
])
def test_ledger_fee_half_even(amount, rate_bp, expected):
    assert fee(amount, rate_bp) == expected


@pytest.mark.parametrize(("balance", "annual_bp", "expected"), [
    (120_000, 500, 500), (600, 10_000, 50), (6, 10_000, 0), (18, 10_000, 2), (30, 10_000, 2), (42, 10_000, 4),
    (5_000, 500, 21),
])
def test_ledger_monthly_interest_half_even(balance, annual_bp, expected):
    assert monthly_interest(balance, annual_bp) == expected


@pytest.mark.parametrize(("total_cents", "parts", "shares"), [
    (100, 3, [33, 33, 34]), (5, 2, [2, 3]), (7, 2, [4, 3]), (1, 2, [0, 1]), (3, 2, [2, 1]), (10, 4, [2, 2, 2, 4]),
    (14, 4, [4, 4, 4, 2]),
])
def test_ledger_split_half_even(total_cents, parts, shares):
    assert split(total_cents, parts) == shares and sum(split(total_cents, parts)) == total_cents


def test_divide_rejects_bad_divisor():
    with pytest.raises(ValueError):
        divide(1, 0)
