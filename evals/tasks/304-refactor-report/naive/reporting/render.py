"""Render a summary as text or CSV."""


def _money(cents):
    return "{:,.2f}".format(cents / 100)


def render_text(summary):
    if summary["count"] == 0:
        return "No data.\n"
    width = max([8] + [len(category["name"]) for category in summary["categories"]])
    lines = ["SALES REPORT", "============", ""]
    for category in summary["categories"]:
        lines.append("%-*s  %12s  (%d)" % (width, category["name"], _money(category["cents"]), category["count"]))
    lines.append("-" * (width + 14))
    lines.append("%-*s  %12s  (%d)" % (width, "TOTAL", _money(summary["total_cents"]), summary["count"]))
    lines.append("")
    lines.append("By month:")
    for month in summary["months"]:
        lines.append("  %s  %12s" % (month["month"], _money(month["cents"])))
    largest = summary["largest"]
    lines.append("")
    lines.append("Largest: %s %s in %s" % (largest["category"], _money(largest["cents"]), largest["month"]))
    return "\n".join(lines) + "\n"


def _quoted(name):
    if "," in name or '"' in name:
        return '"' + name.replace('"', '""') + '"'
    return name


def render_csv(summary):
    out = "category,total,count\n"
    for category in summary["categories"]:
        out += "%s,%.2f,%d\n" % (_quoted(category["name"]), category["cents"] / 100, category["count"])
    return out + "TOTAL,%.2f,%d\n" % (summary["total_cents"] / 100, summary["count"])
