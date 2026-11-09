import pytest

from ratelimit import TokenBucket


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def bucket(rate=2, capacity=4):
    clock = Clock()
    return TokenBucket(rate, capacity, clock), clock


def test_starts_full():
    b, _ = bucket()
    assert b.available() == pytest.approx(4.0)


def test_drains_then_refuses():
    b, _ = bucket()
    assert [b.allow() for _ in range(5)] == [True, True, True, True, False]


def test_refills_over_time():
    b, clock = bucket()
    assert b.allow(4) is True
    clock.now += 0.5
    assert b.available() == pytest.approx(1.0)
    assert b.allow() is True and b.allow() is False


def test_refill_is_capped():
    b, clock = bucket()
    clock.now += 1000
    assert b.available() == pytest.approx(4.0)


def test_refused_cost_removes_nothing():
    b, _ = bucket()
    assert b.allow(5) is False
    assert b.available() == pytest.approx(4.0)


@pytest.mark.parametrize(("rate", "capacity"), [(0, 1), (1, 0), (-1, 1)])
def test_bad_config(rate, capacity):
    with pytest.raises(ValueError):
        TokenBucket(rate, capacity, Clock())


def test_negative_cost():
    b, _ = bucket()
    with pytest.raises(ValueError):
        b.allow(-1)
