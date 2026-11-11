"""Sales report: parse the rows, summarise them, render the summary."""

from reporting.aggregate import summarize
from reporting.parsing import parse_rows
from reporting.render import render_csv, render_text

__all__ = ["build_report"]


def build_report(rows, fmt="text"):
    summary = summarize(parse_rows(rows))
    if fmt == "text":
        return render_text(summary)
    if fmt == "csv":
        return render_csv(summary)
    raise ValueError("unknown format: %s" % fmt)
