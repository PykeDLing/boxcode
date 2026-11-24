import pytest

from textwrap2 import bullet, indent, wrap


def test_short_text_is_one_line():
    assert wrap("hello world", 20) == ["hello world"]


def test_breaks_at_whitespace():
    assert wrap("the quick brown fox jumps", 10) == ["the quick", "brown fox", "jumps"]


def test_line_may_be_exactly_width():
    assert wrap("ab cd ef", 5) == ["ab cd", "ef"]
    assert wrap("one two three four", 13) == ["one two three", "four"]


def test_the_space_counts_towards_the_width():
    assert wrap("abc de", 5) == ["abc", "de"]
    assert wrap("aaaa bbbb cc dd", 9) == ["aaaa bbbb", "cc dd"]
    assert wrap("aaaa bbbbb cc", 9) == ["aaaa", "bbbbb cc"]


def test_whitespace_collapses():
    assert wrap("  a \t b\n\nc  ", 80) == ["a b c"]
    assert wrap("   ", 5) == []


def test_long_word_is_split():
    assert wrap("abcdefghij", 4) == ["abcd", "efgh", "ij"]
    assert wrap("x abcdefgh y", 4) == ["x", "abcd", "efgh", "y"]


def test_bad_width():
    with pytest.raises(ValueError):
        wrap("a", 0)


def test_indent():
    assert indent(["a", "", "b"], "  ") == ["  a", "", "  b"]
    assert indent(["a", "b"], "    ", first="1.  ") == ["1.  a", "    b"]


def test_bullet():
    assert bullet("the quick brown fox jumps", 12) == ["- the quick", "  brown fox", "  jumps"]
    assert bullet("ab cd ef", 7, marker="* ") == ["* ab cd", "  ef"]
