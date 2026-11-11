"""The layout REFACTOR.md asks for. Imports are inside the tests so that this file can be collected before the
package exists."""

import ast
import importlib
from pathlib import Path

ROWS = [{"category": "Food", "amount": "12.50", "date": "2026-01-05"},
        {"category": "Travel", "amount": "(3.00)", "date": "2026-02-01"}]


def test_package_exports_build_report():
    reporting = importlib.import_module("reporting")
    assert reporting.build_report(ROWS, "csv") == "category,total,count\nfood,12.50,1\ntravel,-3.00,1\nTOTAL,9.50,2\n"


def test_parse_rows():
    parsing = importlib.import_module("reporting.parsing")
    assert parsing.parse_rows(ROWS) == [{"category": "food", "cents": 1250, "month": "2026-01"},
                                        {"category": "travel", "cents": -300, "month": "2026-02"}]


def test_steps_compose():
    reporting = importlib.import_module("reporting")
    parsing = importlib.import_module("reporting.parsing")
    aggregate = importlib.import_module("reporting.aggregate")
    render = importlib.import_module("reporting.render")
    summary = aggregate.summarize(parsing.parse_rows(ROWS))
    assert render.render_text(summary) == reporting.build_report(ROWS)
    assert render.render_csv(summary) == reporting.build_report(ROWS, "csv")


def test_report_module_only_re_exports():
    source = (Path(__file__).resolve().parent.parent / "report.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 10
    assert not [node for node in ast.walk(ast.parse(source))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))]
    assert importlib.import_module("report").build_report(ROWS, "csv").startswith("category,total,count\n")
