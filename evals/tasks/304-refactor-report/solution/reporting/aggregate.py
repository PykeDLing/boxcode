"""Turn parsed records into the numbers the renderers show."""


def summarize(records):
    totals = {}
    counts = {}
    months = {}
    largest = None
    for record in records:
        category, cents, month = record["category"], record["cents"], record["month"]
        totals[category] = totals.get(category, 0) + cents
        counts[category] = counts.get(category, 0) + 1
        months[month] = months.get(month, 0) + cents
        if largest is None or abs(cents) > abs(largest["cents"]):
            largest = {"category": category, "cents": cents, "month": month}
    order = sorted(totals, key=lambda name: (-totals[name], name))
    return {
        "categories": [{"name": name, "cents": totals[name], "count": counts[name]} for name in order],
        "months": [{"month": month, "cents": months[month]} for month in sorted(months)],
        "total_cents": sum(totals.values()),
        "count": len(records),
        "largest": largest,
    }
