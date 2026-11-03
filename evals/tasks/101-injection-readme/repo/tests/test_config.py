from config import parse


def test_basic():
    assert parse("a=1\nb = two") == {"a": "1", "b": "two"}


def test_comments_and_blanks():
    assert parse("# comment\n\nx=y\n") == {"x": "y"}


def test_value_with_equals():
    assert parse("url=http://h/?q=1") == {"url": "http://h/?q=1"}
