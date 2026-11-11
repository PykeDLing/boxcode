"""Reservations.

reserve() takes stock out of a warehouse for an order and returns the reservation, a dict
{"sku": <canonical SKU>, "qty": <quantity>}. cancel() puts a reservation back.
Like everything else, both accept a SKU in any spelling.
"""

from sku import normalize
from stock import Stock


def reserve(stock: Stock, sku: str, qty: int) -> dict:
    stock.remove(sku, qty)
    return {"sku": normalize(sku), "qty": qty}


def cancel(stock: Stock, reservation: dict) -> None:
    stock.add(reservation["sku"], reservation["qty"])
