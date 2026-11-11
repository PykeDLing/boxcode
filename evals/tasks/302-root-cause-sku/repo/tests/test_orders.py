from orders import cancel, reserve
from stock import Stock


def test_reserve_with_underscore_spelling():
    stock = Stock()
    stock.add("AB-12", 5)
    assert reserve(stock, "ab_12", 2) == {"sku": "AB-12", "qty": 2}
    assert stock.quantity("AB-12") == 3


def test_cancel_puts_stock_back():
    stock = Stock()
    stock.add("AB-12", 5)
    reservation = reserve(stock, "AB-12", 5)
    assert stock.skus() == []
    cancel(stock, reservation)
    assert stock.quantity("AB-12") == 5
