"""Reports.

low_stock() returns the canonical SKUs whose quantity is below the threshold, sorted. SKUs listed in `ignore`
(in any spelling) are left out of the report.
"""

from sku import normalize
from stock import Stock


def low_stock(stock: Stock, threshold: int, ignore: tuple[str, ...] = ()) -> list[str]:
    ignored = {normalize(code) for code in ignore}
    return [sku for sku in stock.skus() if stock.quantity(sku) < threshold and sku not in ignored]
