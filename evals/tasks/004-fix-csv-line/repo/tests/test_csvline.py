import pytest

from csvline import parse_line


def test_plain():
    assert parse_line("a,b,c") == ["a", "b", "c"]


def test_empty_fields():
    assert parse_line(",x,") == ["", "x", ""]


def test_quoted_delimiter():
    assert parse_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_escaped_quote():
    assert parse_line('"say ""hi""",2') == ['say "hi"', "2"]


def test_custom_delimiter():
    assert parse_line('a;"b;c"', delimiter=";") == ["a", "b;c"]


def test_unterminated_quote():
    with pytest.raises(ValueError):
        parse_line('a,"b')
