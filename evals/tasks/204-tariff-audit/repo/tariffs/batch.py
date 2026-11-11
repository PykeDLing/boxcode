"""Quote many parcels at once.

An order is a list [goods_cents, weight_g, category, express, zone]; `country` is the name of a module in this
package, for example "germany".
"""

import importlib

COUNTRIES = ['austria', 'belgium', 'denmark', 'finland', 'france', 'germany', 'ireland', 'italy', 'netherlands', 'norway', 'poland', 'portugal', 'spain', 'sweden']
KEYS = ['vat', 'duty', 'shipping', 'express', 'zone', 'handling', 'heavy', 'insurance', 'packaging', 'paperwork', 'signature', 'fuel', 'carbon', 'discount', 'total']


def quotes(country, orders):
    """The quote of every order, in order."""
    module = importlib.import_module("tariffs." + country)
    return [module.quote(*order) for order in orders]


def totals(country, orders):
    """Only the totals."""
    return [quote["total"] for quote in quotes(country, orders)]


def component_sums(country, orders):
    """Each component added up over all orders."""
    sums = dict.fromkeys(KEYS, 0)
    for quote in quotes(country, orders):
        for key in KEYS:
            sums[key] += quote[key]
    return sums
