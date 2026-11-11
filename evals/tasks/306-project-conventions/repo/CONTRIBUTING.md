# Contributing

Run both of these before you call a change finished:

    python -m pytest -q
    python tools/check_api.py

`tools/check_api.py` enforces the rules below. It stops at the first problem it finds, so run it again after every fix
until it prints `check_api: OK`.

1. Every public function in `tables.py` (a name without a leading underscore) has a docstring and type annotations
   for every parameter and for the return value.
2. No function in `tables.py`, public or private, is longer than 30 lines, counted from its `def` line to its last line.
3. `tables.py` never calls `print`.
4. `__all__` in `tables.py` lists exactly the public functions, in alphabetical order.
5. `docs/API.md` has one `### name` heading per public function, in alphabetical order, each followed by a description.
6. `CHANGELOG.md` mentions every public function by name in backticks, like `` `pad` ``. New functions go under
   `## Unreleased`.
