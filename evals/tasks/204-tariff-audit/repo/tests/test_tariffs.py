from tariffs import batch

CATEGORIES = ['general', 'books', 'food', 'electronics']
GOODS = [0, 250, 1000, 1234, 2500, 4750, 5000, 5250, 7777, 9750, 10000, 10250, 12500, 15000, 15250, 19750, 19999, 20000, 20250, 25000, 30000, 30250, 33333, 40000, 40250, 60000]
WEIGHTS = [0, 1, 499, 500, 501, 999, 1000, 1001, 2500, 4999, 5000, 5001, 10000, 10001, 12345]
GRID = [[goods, weight, category, express, zone] for goods in GOODS for weight in WEIGHTS for category in CATEGORIES
        for express in (False, True) for zone in (1, 2, 3)]


def test_grand_total():
    # Every country, every parcel in the grid: 9360 quotes per country.
    assert sum(sum(batch.totals(country, GRID)) for country in batch.COUNTRIES) == 3006070110


def test_quote_has_every_component():
    assert sorted(batch.quotes("germany", GRID[:1])[0]) == sorted(batch.KEYS)
