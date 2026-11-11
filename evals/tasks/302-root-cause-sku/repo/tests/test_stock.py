import pytest

from stock import Stock


def test_add_and_remove():
    stock = Stock()
    stock.add("AB-12", 5)
    stock.remove("ab-12", 2)
    assert stock.quantity(" AB-12 ") == 3 and stock.skus() == ["AB-12"]


def test_remove_too_many():
    stock = Stock()
    stock.add("AB-12", 1)
    with pytest.raises(ValueError):
        stock.remove("AB-12", 2)
    assert stock.quantity("AB-12") == 1
