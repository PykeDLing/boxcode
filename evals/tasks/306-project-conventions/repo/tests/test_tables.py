import pytest

import tables


def test_existing_helpers():
    assert tables.column_widths([["a", "bbb"], ["cc", "d"]]) == [2, 3]
    assert tables.pad("ab", 5, "c") == " ab  "


def test_render_with_headers():
    text = tables.render_table([["apple", "3"], ["fig", "12"]], headers=["name", "qty"], align="lr")
    assert text.split("\n") == [
        "| name  | qty |",
        "| ----- | --- |",
        "| apple |   3 |",
        "| fig   |  12 |",
    ]


def test_render_without_headers():
    assert tables.render_table([["a", "bb"], ["ccc", "d"]]) == "| a   | bb |\n| ccc | d  |"


def test_render_rejects_ragged_rows():
    with pytest.raises(ValueError):
        tables.render_table([["a", "b"], ["c"]])


def test_parse():
    assert tables.parse_table("| name | qty |\n| ---- | --- |\n| apple | 3 |\n") == [["name", "qty"], ["apple", "3"]]
