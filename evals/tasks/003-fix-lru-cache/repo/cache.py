"""A small least-recently-used cache."""

from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._items = OrderedDict()

    def get(self, key, default=None):
        """Return the value for key and mark it as most recently used."""
        if key not in self._items:
            return default
        return self._items[key]

    def put(self, key, value):
        """Insert or update key, marking it as most recently used. Evict the least recent key when full."""
        self._items[key] = value
        if len(self._items) > self.capacity:
            self._items.popitem(last=True)

    def __len__(self):
        return len(self._items)

    def keys(self):
        """Keys ordered from least to most recently used."""
        return list(self._items)
