import pytest

from orders import cancel, reserve
from reports import low_stock
from sku import normalize
from stock import Stock
from transfer import plan_transfers, transfer

SPELLINGS = ["ab-12", " AB 12 ", "ab_12", "AB--12", "-ab-12-", "Ab  12", "ab_-_12", "_ab 12_", "  ab - 12  ", "AB-12"]


@pytest.mark.parametrize("code", SPELLINGS)
def test_normalize_spellings(code):
    assert normalize(code) == "AB-12"


@pytest.mark.parametrize(("code", "canonical"), [
    ("x", "X"), ("a b c", "A-B-C"), ("a__b--c  d", "A-B-C-D"), ("12", "12"), ("AB12", "AB12"),
])
def test_normalize_other_codes(code, canonical):
    assert normalize(code) == canonical


@pytest.mark.parametrize("code", ["", "   ", "-", "___", " - _ - ", "--"])
def test_normalize_rejects_codes_without_parts(code):
    with pytest.raises(ValueError):
        normalize(code)


@pytest.mark.parametrize("code", SPELLINGS)
def test_stock_treats_spellings_as_one_product(code):
    stock = Stock()
    stock.add("AB-12", 2)
    stock.add(code, 3)
    assert stock.skus() == ["AB-12"] and stock.quantity(code) == 5
    stock.remove(code, 5)
    assert stock.skus() == []


@pytest.mark.parametrize("code", SPELLINGS)
def test_reserve_returns_canonical_sku(code):
    stock = Stock()
    stock.add("AB-12", 5)
    assert reserve(stock, code, 2) == {"sku": "AB-12", "qty": 2}
    assert stock.quantity("AB-12") == 3


def test_reserve_more_than_available_changes_nothing():
    stock = Stock()
    stock.add("AB-12", 1)
    with pytest.raises(ValueError):
        reserve(stock, "ab 12", 2)
    assert stock.quantity("AB-12") == 1


def test_cancel_accepts_any_spelling():
    stock = Stock()
    stock.add("AB-12", 1)
    cancel(stock, {"sku": "ab_12", "qty": 4})
    assert stock.skus() == ["AB-12"] and stock.quantity("AB-12") == 5


def test_transfer_between_warehouses():
    source, target = Stock(), Stock()
    source.add("ab_12", 4)
    target.add("AB 12", 1)
    transfer(source, target, " ab--12", 3)
    assert (source.quantity("AB-12"), target.quantity("AB-12")) == (1, 4)
    assert source.skus() == target.skus() == ["AB-12"]


def test_plan_transfers_merges_spellings():
    requests = [("ab-12", 1), ("AB_12", 2), (" ab 12", 3), ("zz 9", 4), ("ZZ-9", 1)]
    assert plan_transfers(requests) == {"AB-12": 6, "ZZ-9": 5}


def test_plan_transfers_rejects_invalid_sku():
    with pytest.raises(ValueError):
        plan_transfers([("ab-12", 1), ("__", 2)])


def test_low_stock_ignore_accepts_any_spelling():
    stock = Stock()
    stock.add("AB-12", 1)
    stock.add("CD-34", 2)
    stock.add("EF-56", 9)
    assert low_stock(stock, 5) == ["AB-12", "CD-34"]
    assert low_stock(stock, 5, ignore=("ab_12",)) == ["CD-34"]
    assert low_stock(stock, 5, ignore=(" cd 34 ", "ab--12")) == []
