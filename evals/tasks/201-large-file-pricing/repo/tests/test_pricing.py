import pytest

from pricing import price_order

CASES = [
    ({'category': 'stationery', 'units': 30, 'line_total': 240.0, 'region': 'north', 'tier': 'silver', 'month': 2}, 207.6),
    ({'category': 'garden', 'units': 40, 'line_total': 800.0, 'region': 'south', 'tier': 'bronze', 'month': 6}, 450.0),
    ({'category': 'garden', 'units': 39, 'line_total': 780.0, 'region': 'south', 'tier': 'bronze', 'month': 6}, 485.6),
    ({'category': 'toys', 'units': 3, 'line_total': 90.0, 'region': 'east', 'tier': 'gold', 'month': 3}, 65.3),
    ({'category': 'toys', 'units': 3, 'line_total': 90.0, 'region': 'east', 'tier': 'gold', 'month': 4}, 89.6),
    ({'category': 'electronics', 'units': 80, 'line_total': 4000.0, 'region': 'coastal', 'tier': 'platinum', 'month': 11}, 1000.5),
    ({'category': 'books', 'units': 12, 'line_total': 120.0, 'region': 'central', 'tier': 'gold', 'month': 9}, 113.85),
    ({'category': 'kitchen', 'units': 1, 'line_total': 30.0, 'region': 'west', 'tier': 'bronze', 'month': 4}, 33.1),
    ({'category': 'pet', 'units': 26, 'line_total': 510.0, 'region': 'north', 'tier': 'platinum', 'month': 12}, 316.7),
    ({'category': 'lighting', 'units': 90, 'line_total': 1250.0, 'region': 'east', 'tier': 'silver', 'month': 1}, 514.0),
]


@pytest.mark.parametrize(("order", "expected"), CASES)
def test_price(order, expected):
    assert price_order(order) == pytest.approx(expected)
