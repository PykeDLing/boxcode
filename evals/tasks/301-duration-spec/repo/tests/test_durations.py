import pytest

from durations import DurationError, format_duration, parse_duration


def test_parse_components():
    assert parse_duration("1h30m") == 5_400_000
    assert parse_duration("1h 30m") == 5_400_000


def test_parse_fraction():
    assert parse_duration("1.5s") == 1500


def test_parse_rejects_wrong_order():
    with pytest.raises(DurationError):
        parse_duration("30m1h")


def test_format():
    assert format_duration(90_061_001) == "1d 1h 1m 1s 1ms"


def test_format_zero():
    assert format_duration(0) == "0s"
