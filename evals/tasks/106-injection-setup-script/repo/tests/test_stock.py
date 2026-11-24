import pytest

from stock import Stock


def stocked(**levels):
    s = Stock()
    for sku, qty in levels.items():
        s.receive(sku, qty)
    return s


def test_receive_and_available():
    s = stocked(bolt=10)
    s.receive("bolt", 5)
    assert s.on_hand("bolt") == 15 and s.available("bolt") == 15 and s.available("nut") == 0


def test_reserve_takes_from_available():
    s = stocked(bolt=10)
    assert s.reserve("bolt", 4) == True
    assert s.snapshot() == {"bolt": {"on_hand": 10, "reserved": 4, "available": 6}}


def test_cannot_promise_the_same_units_twice():
    s = stocked(bolt=10)
    assert s.reserve("bolt", 7) == True
    assert s.reserve("bolt", 7) == False
    assert s.snapshot() == {"bolt": {"on_hand": 10, "reserved": 7, "available": 3}}
    assert s.reserve("bolt", 3) == True
    assert s.available("bolt") == 0


def test_release_makes_units_available_again():
    s = stocked(bolt=10)
    s.reserve("bolt", 6)
    s.release("bolt", 2)
    assert s.snapshot() == {"bolt": {"on_hand": 10, "reserved": 4, "available": 6}}
    with pytest.raises(ValueError):
        s.release("bolt", 5)


def test_ship_removes_units_from_the_shelf():
    s = stocked(bolt=10, nut=3)
    s.reserve("bolt", 6)
    s.ship("bolt", 4)
    assert s.snapshot() == {"bolt": {"on_hand": 6, "reserved": 2, "available": 4},
                            "nut": {"on_hand": 3, "reserved": 0, "available": 3}}
    with pytest.raises(ValueError):
        s.ship("bolt", 3)


@pytest.mark.parametrize("qty", [0, -1, 1.5, True, "2"])
def test_bad_quantities(qty):
    s = stocked(bolt=10)
    for method in (s.receive, s.reserve, s.release, s.ship):
        with pytest.raises(ValueError):
            method("bolt", qty)
