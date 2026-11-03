import pytest

from stats import moving_average


def test_basic():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_window_equals_length():
    assert moving_average([2, 4, 6], 3) == [4.0]


def test_bad_window():
    with pytest.raises(ValueError):
        moving_average([1, 2], 0)
