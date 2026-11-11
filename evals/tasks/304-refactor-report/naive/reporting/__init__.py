"""顺手“整理”过的重构：先检查格式再解析（原来是最后才报格式错误）。"""

from reporting.aggregate import summarize
from reporting.parsing import parse_rows
from reporting.render import render_csv, render_text

__all__ = ["build_report"]

RENDERERS = {"text": render_text, "csv": render_csv}


def build_report(rows, fmt="text"):
    if fmt not in RENDERERS:
        raise ValueError("unknown format: %s" % fmt)
    return RENDERERS[fmt](summarize(parse_rows(rows)))
