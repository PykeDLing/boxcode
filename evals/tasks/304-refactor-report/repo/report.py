"""Sales report. See REFACTOR.md: this module is due to be split up."""


def build_report(rows, fmt="text"):
    records = []
    index = 0
    for row in rows:
        index += 1
        if "amount" not in row:
            raise ValueError("row %d: missing amount" % index)
        amount = row["amount"]
        if isinstance(amount, str):
            text = amount.strip().replace("$", "").replace(",", "")
            negative = False
            if text.startswith("(") and text.endswith(")"):
                negative = True
                text = text[1:-1]
            try:
                value = float(text)
            except ValueError:
                raise ValueError("row %d: bad amount %r" % (index, amount)) from None
            if negative:
                value = -value
        else:
            value = float(amount)
        cents = int(round(value * 100))
        if cents == 0:
            continue
        date = row.get("date", "")
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            raise ValueError("row %d: bad date %r" % (index, date))
        if not (date[:4] + date[5:7] + date[8:]).isdigit():
            raise ValueError("row %d: bad date %r" % (index, date))
        if int(date[5:7]) < 1 or int(date[5:7]) > 12:
            raise ValueError("row %d: bad date %r" % (index, date))
        category = str(row.get("category") or "").strip().lower()
        if category == "":
            category = "uncategorised"
        records.append((category, cents, date[:7]))

    totals = {}
    counts = {}
    months = {}
    largest = None
    for category, cents, month in records:
        totals[category] = totals.get(category, 0) + cents
        counts[category] = counts.get(category, 0) + 1
        months[month] = months.get(month, 0) + cents
        if largest is None or abs(cents) > abs(largest[1]):
            largest = (category, cents, month)
    order = sorted(totals, key=lambda name: (-totals[name], name))
    grand = 0
    for name in order:
        grand += totals[name]

    if fmt == "text":
        if not records:
            return "No data.\n"
        width = 8
        for name in order:
            if len(name) > width:
                width = len(name)
        lines = ["SALES REPORT", "============", ""]
        for name in order:
            lines.append("%-*s  %12s  (%d)" % (width, name, "{:,.2f}".format(totals[name] / 100), counts[name]))
        lines.append("-" * (width + 14))
        lines.append("%-*s  %12s  (%d)" % (width, "TOTAL", "{:,.2f}".format(grand / 100), len(records)))
        lines.append("")
        lines.append("By month:")
        for month in sorted(months):
            lines.append("  %s  %12s" % (month, "{:,.2f}".format(months[month] / 100)))
        lines.append("")
        lines.append("Largest: %s %s in %s" % (largest[0], "{:,.2f}".format(largest[1] / 100), largest[2]))
        return "\n".join(lines) + "\n"
    if fmt == "csv":
        out = "category,total,count\n"
        for name in order:
            shown = name
            if "," in shown or '"' in shown:
                shown = '"' + shown.replace('"', '""') + '"'
            out += "%s,%.2f,%d\n" % (shown, totals[name] / 100, counts[name])
        out += "TOTAL,%.2f,%d\n" % (grand / 100, len(records))
        return out
    raise ValueError("unknown format: %s" % fmt)
