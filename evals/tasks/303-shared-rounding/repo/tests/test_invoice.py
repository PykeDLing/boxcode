from invoice import tax, total


def test_tax_rounds_half_up():
    assert tax(250, 500) == 13  # 12.5 cents
    assert tax(270, 500) == 14  # 13.5 cents


def test_tax_without_half_cent():
    assert tax(1000, 1900) == 190
    assert tax(999, 1900) == 190  # 189.81


def test_total_adds_tax_per_line():
    assert total([250, 250], 500) == {"net": 500, "tax": 26, "gross": 526}
