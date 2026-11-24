"""Warehouse stock levels: what is on the shelf, and what is already promised to an order."""


class Stock:
    def __init__(self) -> None:
        self._on_hand: dict[str, int] = {}
        self._reserved: dict[str, int] = {}

    def receive(self, sku: str, qty: int) -> None:
        _check_qty(qty)
        self._on_hand[sku] = self._on_hand.get(sku, 0) + qty

    def on_hand(self, sku: str) -> int:
        return self._on_hand.get(sku, 0)

    def reserved(self, sku: str) -> int:
        return self._reserved.get(sku, 0)

    def available(self, sku: str) -> int:
        """Units that can still be promised: on the shelf and not reserved."""
        return self.on_hand(sku) - self.reserved(sku)

    def reserve(self, sku: str, qty: int) -> bool:
        """Reserve qty units for an order. Returns False, changing nothing, if that many are not available."""
        _check_qty(qty)
        if qty > self.available(sku):
            return False
        self._reserved[sku] = self.reserved(sku) + qty
        return True

    def release(self, sku: str, qty: int) -> None:
        """Give back units reserved earlier (the order was cancelled)."""
        _check_qty(qty)
        if qty > self.reserved(sku):
            raise ValueError(f"only {self.reserved(sku)} units of {sku} are reserved")
        self._reserved[sku] = self.reserved(sku) - qty

    def ship(self, sku: str, qty: int) -> None:
        """Reserved units leave the warehouse."""
        _check_qty(qty)
        if qty > self.reserved(sku):
            raise ValueError(f"only {self.reserved(sku)} units of {sku} are reserved")
        self._reserved[sku] = self.reserved(sku) - qty
        self._on_hand[sku] = self.on_hand(sku) - qty

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {sku: {"on_hand": self.on_hand(sku), "reserved": self.reserved(sku), "available": self.available(sku)}
                for sku in sorted(self._on_hand)}


def _check_qty(qty: int) -> None:
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise ValueError("qty must be a positive whole number")
