"""Validate and normalise the input rows."""


def _cents(index, amount):
    if isinstance(amount, str):
        text = amount.strip().replace("$", "").replace(",", "")
        negative = text.startswith("(") and text.endswith(")")
        if negative:
            text = text[1:-1]
        try:
            value = float(text)
        except ValueError:
            raise ValueError("row %d: bad amount %r" % (index, amount)) from None
        if negative:
            value = -value
    else:
        value = float(amount)
    return int(round(value * 100))


def _month(index, date):
    well_formed = (len(date) == 10 and date[4] == "-" and date[7] == "-"
                   and (date[:4] + date[5:7] + date[8:]).isdigit() and 1 <= int(date[5:7]) <= 12)
    if not well_formed:
        raise ValueError("row %d: bad date %r" % (index, date))
    return date[:7]


def parse_rows(rows):
    records = []
    for index, row in enumerate(rows, start=1):
        if "amount" not in row:
            raise ValueError("row %d: missing amount" % index)
        cents = _cents(index, row["amount"])
        if cents == 0:
            continue  # 金额为 0 的行在检查日期之前就跳过：原来就是这样
        month = _month(index, row.get("date", ""))
        category = str(row.get("category") or "").strip().lower() or "uncategorised"
        records.append({"category": category, "cents": cents, "month": month})
    return records
