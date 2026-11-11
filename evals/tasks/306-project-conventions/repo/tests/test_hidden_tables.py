from pathlib import Path

import pytest

import tables
from tools.check_api import problems

ROOT = Path(__file__).resolve().parent.parent


def test_project_rules():
    assert problems(ROOT) == []


def test_all_lists_the_new_functions():
    assert sorted(tables.__all__) == ["column_widths", "pad", "parse_table", "render_table"]


def test_api_docs_describe_the_new_functions():
    api = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    for name in ("parse_table", "render_table"):
        section = api.split(f"### {name}", 1)[1].split("###", 1)[0] if f"### {name}" in api else ""
        assert len(section.split()) >= 5, name


def test_changelog_entry_is_under_unreleased():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## Unreleased", 1)[1].split("## 0.1.0", 1)[0]
    assert "`render_table`" in unreleased and "`parse_table`" in unreleased
    assert "- Added `column_widths` and `pad`." in changelog.split("## 0.1.0", 1)[1]


# rules 1-3
@pytest.mark.parametrize(("align", "lines"), [
    ("", ["| name   | qty  | unit |", "| ------ | ---- | ---- |", "| apple  | 3    | kg   |", "| banana | 1200 | g    |"]),
    ("lrc", ["| name   |  qty | unit |", "| ------ | ---- | ---- |", "| apple  |    3 |  kg  |", "| banana | 1200 |  g   |"]),
    ("r", ["|   name | qty  | unit |", "| ------ | ---- | ---- |", "|  apple | 3    | kg   |", "| banana | 1200 | g    |"]),
    ("cc", ["|  name  | qty  | unit |", "| ------ | ---- | ---- |", "| apple  |  3   | kg   |", "| banana | 1200 | g    |"]),
    ("ccc", ["|  name  | qty  | unit |", "| ------ | ---- | ---- |", "| apple  |  3   |  kg  |", "| banana | 1200 |  g   |"]),
])
def test_render_alignment(align, lines):
    rows = [["apple", "3", "kg"], ["banana", "1200", "g"]]
    assert tables.render_table(rows, headers=["name", "qty", "unit"], align=align).split("\n") == lines


def test_header_can_be_the_widest_cell():
    assert tables.render_table([["a", "b"]], headers=["first", "second"], align="rc").split("\n") == [
        "| first | second |", "| ----- | ------ |", "|     a |   b    |"]


def test_render_without_headers_has_no_separator():
    assert tables.render_table([["x", "yy"], ["zzz", ""]], align="rl") == "|   x | yy |\n| zzz |    |"


def test_render_has_no_trailing_newline():
    assert not tables.render_table([["a"]], headers=["h"]).endswith("\n")
    assert tables.render_table([["a"]]) == "| a |"


def test_empty_cells_and_columns():
    assert tables.render_table([["", ""], ["", ""]]) == "|  |  |\n|  |  |"
    assert tables.render_table([["", ""]], headers=["", ""]).split("\n") == ["|  |  |", "|  |  |", "|  |  |"]


# rule 4
@pytest.mark.parametrize(("rows", "headers", "align"), [
    ([["a", "b"], ["c"]], None, ""),
    ([["a", "b"], ["c", "d", "e"]], None, ""),
    ([["a", "b"]], ["h"], ""),
    ([["a", "b"]], ["h", "i", "j"], ""),
    ([["a", "b"]], None, "lrc"),
    ([["a", "b"]], ["h", "i"], "lll"),
    ([["a", "b"]], None, "x"),
    ([["a", "b"]], None, "L"),
    ([["a", "b"]], None, "l "),
    ([["a", "b"]], None, "<>"),
    ([], ["h", "i"], "lrc"),
])
def test_render_errors(rows, headers, align):
    with pytest.raises(ValueError):
        tables.render_table(rows, headers=headers, align=align)


# rule 5
def test_render_nothing():
    assert tables.render_table([]) == ""
    assert tables.render_table([], headers=None, align="") == ""


def test_render_headers_only():
    assert tables.render_table([], headers=["name", "qty"], align="rc") == "| name | qty |\n| ---- | --- |"


# rules 6-9
def test_parse_drops_separator_and_keeps_header():
    text = "| name  | qty |\n| ----- | --- |\n| apple |   3 |\n| fig   |  12 |"
    assert tables.parse_table(text) == [["name", "qty"], ["apple", "3"], ["fig", "12"]]


def test_parse_skips_blank_lines_and_strips():
    text = "\n   \n  | a |  b  |  \n\n|c|d|\n\t\n"
    assert tables.parse_table(text) == [["a", "b"], ["c", "d"]]


def test_parse_empty_cells():
    assert tables.parse_table("| a |  | c |\n|||   |") == [["a", "", "c"], ["", "", ""]]


@pytest.mark.parametrize(("text", "rows"), [
    ("| - | -- |", []),
    ("| a | b |\n|---|---|\n|---|---|\n| c | d |", [["a", "b"], ["c", "d"]]),
    ("| a | - |\n| - | b |", [["a", "-"], ["-", "b"]]),
    ("| --- |  |", [["---", ""]]),
    ("| -a- |", [["-a-"]]),
    ("| :-- |", [[":--"]]),
])
def test_parse_separator_detection(text, rows):
    assert tables.parse_table(text) == rows


@pytest.mark.parametrize("text", ["", "\n\n", "   \n\t\n", "| --- | --- |\n"])
def test_parse_nothing(text):
    assert tables.parse_table(text) == []


@pytest.mark.parametrize("text", [
    "a | b", "| a | b", "a | b |", "| a | b |\nplain text", "| a | b |\n| c |", "| a |\n| b | c |",
    "| a | b |\n| --- | --- | --- |\n| c | d | e |",
])
def test_parse_errors(text):
    with pytest.raises(ValueError):
        tables.parse_table(text)


@pytest.mark.parametrize(("rows", "headers", "align"), [
    ([["apple", "3"], ["fig", "12"]], ["name", "qty"], "lr"),
    ([["a", "bb", "ccc"], ["dddd", "e", "f"]], None, "crl"),
    ([["x"]], ["only"], "c"),
    ([["a b", "c  d"]], ["two words", "x"], ""),
])
def test_round_trip(rows, headers, align):
    expected = ([headers] if headers else []) + rows
    assert tables.parse_table(tables.render_table(rows, headers=headers, align=align)) == expected
