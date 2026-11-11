"""Moving stock between warehouses.

transfer() moves qty of one SKU. plan_transfers() takes a list of (sku, qty) requests and returns the total
quantity per product as a dict keyed by canonical SKU; requests for the same product are added up, whatever
spelling each request uses.
"""

from sku import normalize
from stock import Stock


def transfer(source: Stock, target: Stock, sku: str, qty: int) -> None:
    source.remove(sku, qty)
    target.add(sku, qty)


def plan_transfers(requests: list[tuple[str, int]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for sku, qty in requests:
        key = normalize(sku)
        totals[key] = totals.get(key, 0) + qty
    return totals
