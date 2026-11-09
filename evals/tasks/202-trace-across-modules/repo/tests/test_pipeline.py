import pytest

from etl.pipeline import run_pipeline


def order(raw_amount, coupon="", country="Germany"):
    return {"raw_amount": raw_amount, "email": " A@B.example ", "country": country, "coupon": coupon}


@pytest.mark.parametrize(("raw", "coupon", "country", "total"), [
    ("$100.00", "", "Germany", 10000 + 450 + 2000),
    ("$100.00", "SAVE10", "Germany", 9000 + 450 + 1800),
    ("$1,000.00", "SAVE25", "United States", 75000 + 450 + 6188),
    ("$10.10", "", "United States", 1010 + 450 + 83),
    ("$0.50", "", "Germany", 50 + 450 + 10),
])
def test_total(raw, coupon, country, total):
    assert run_pipeline(order(raw, coupon, country))["total_cents"] == total


def test_email_is_normalised():
    assert run_pipeline(order("$1.00"))["email"] == "a@b.example"
