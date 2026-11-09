from invoice import subtotal, total


def test_subtotal():
    assert subtotal([(250, 2), (100, 3)]) == 800


def test_total_with_tax():
    assert total([(1000, 2)], 10) == 2200


def test_empty():
    assert total([], 20) == 0
