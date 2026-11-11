# Refactoring report.py

`report.build_report` grew into one long function. Split it into a package without changing what it does.

## Target layout

```
reporting/
    __init__.py     exports build_report
    parsing.py      parse_rows(rows)
    aggregate.py    summarize(records)
    render.py       render_text(summary), render_csv(summary)
report.py           kept for old callers
```

- `reporting.parsing.parse_rows(rows)` validates and normalises the input rows. It returns a list with one dict per
  row that takes part in the report, in input order: `{"category": str, "cents": int, "month": "YYYY-MM"}`.
- `reporting.aggregate.summarize(records)` takes the result of `parse_rows` and returns a dict with everything the
  renderers need. It must be plain data (it has to survive `json.dumps`) and must not depend on the output format.
- `reporting.render.render_text(summary)` and `render_csv(summary)` turn a summary into the final string.
- `reporting.build_report(rows, fmt="text")` only glues the three steps together.
- `report.py` keeps working for old callers (`from report import build_report`) but contains no logic of its own:
  no `def`, no `class`, at most 10 lines; it re-exports `build_report` from `reporting`.

## What must not change

Everything `build_report` returns or raises today, for every input: the exact text and layout of both formats,
rounding, ordering, which rows are skipped, the exact error messages, and which error is raised when an input has
more than one problem. Old callers depend on all of it, including the parts that look odd.
