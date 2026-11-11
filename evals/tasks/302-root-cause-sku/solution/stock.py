"""Stock levels of one warehouse.

Every method accepts a SKU in any spelling (see sku.normalize); levels are kept under the canonical SKU,
so the same product spelled differently is one entry. The quantity of an unknown SKU is 0. Removing more
than is available raises ValueError and changes nothing. An entry that reaches 0 is deleted.
"""

from sku import normalize


class Stock:
    def __init__(self) -> None:
        self._levels: dict[str, int] = {}

    def add(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        key = normalize(sku)
        self._levels[key] = self._levels.get(key, 0) + qty

    def remove(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        key = normalize(sku)
        available = self._levels.get(key, 0)
        if qty > available:
            raise ValueError(f"only {available} of {key} in stock")
        if qty == available:
            del self._levels[key]
        else:
            self._levels[key] = available - qty

    def quantity(self, sku: str) -> int:
        return self._levels.get(normalize(sku), 0)

    def skus(self) -> list[str]:
        """Canonical SKUs with stock, sorted."""
        return sorted(self._levels)
