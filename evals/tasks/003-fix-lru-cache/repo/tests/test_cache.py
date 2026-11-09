import pytest

from cache import LRUCache


def test_evicts_least_recent():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert c.get("a") is None and c.get("b") == 2 and c.get("c") == 3


def test_get_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert c.keys() == ["a", "c"]


def test_update_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 9)
    c.put("c", 3)
    assert c.keys() == ["a", "c"] and c.get("a") == 9


def test_len_never_exceeds_capacity():
    c = LRUCache(3)
    for i in range(10):
        c.put(i, i)
    assert len(c) == 3 and c.keys() == [7, 8, 9]


def test_bad_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)
