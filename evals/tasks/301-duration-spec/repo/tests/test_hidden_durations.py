import pytest

from durations import DurationError, format_duration, parse_duration

LIMIT = 1000 * 7 * 24 * 3600 * 1000


@pytest.mark.parametrize(("text", "ms"), [
    ("90m", 5_400_000),
    ("1500ms", 1500),
    ("1w", 604_800_000),
    ("1d", 86_400_000),
    ("1w 2d 3h 4m 5s 6ms", 604_800_000 + 2 * 86_400_000 + 3 * 3_600_000 + 4 * 60_000 + 5_000 + 6),
    ("1w2d3h4m5s6ms", 604_800_000 + 2 * 86_400_000 + 3 * 3_600_000 + 4 * 60_000 + 5_000 + 6),
    ("1h 30m", 5_400_000),
    ("2h 5ms", 7_200_005),
    ("007s", 7000),
    ("0s", 0),
    ("0ms", 0),
    ("100h", 360_000_000),
])
def test_valid(text, ms):
    assert parse_duration(text) == ms


@pytest.mark.parametrize(("text", "ms"), [
    ("1.5h", 5_400_000),
    ("1h 0.25m", 3_615_000),
    ("4.35s", 4350),
    ("0.57m", 34_200),
    ("1.001s", 1001),
    ("0.001s", 1),
    ("2.0ms", 2),
    ("0.5w", 302_400_000),
    ("1.10s", 1100),
    ("0.0001m", 6),
])
def test_fraction_is_exact(text, ms):
    result = parse_duration(text)
    assert result == ms and type(result) is int


@pytest.mark.parametrize(("text", "ms"), [
    ("-1h30m", -5_400_000),
    ("-0s", 0),
    ("-1.5s", -1500),
    ("-1500ms", -1500),
])
def test_sign(text, ms):
    assert parse_duration(text) == ms


@pytest.mark.parametrize("text", [
    "1H", "1M", "1MS", "1Ms", "1D",  # rule 2
    "30m1h", "1h2h", "1s 1s", "1ms 1s", "1d 1w", "1m 1h 1s",  # rule 3
    "1 h", " 1h", "1h ", "1h\n", "1h  30m", "1h\t30m", "1h\n30m", "\t1h", "1h 30m ",  # rule 4
    "١h", "１h", "1²s", "1_000s", "1e3s", "0x10s", "1,5s",  # rule 5
    "1.5h30m", "1.5h 30m", ".5h", "1.h", "1..5h", "1.5.5h", "1.5h 1.5m",  # rule 6
    "0.0005s", "1.5ms", "0.00001m", "1.0001s",  # rule 7
    "+1h", "- 1h", "1h-30m", "1h -30m", "--1h", "-", "-+1h",  # rule 8
    "", "90", "h", "ms", "1h 30", "1h m", "1.5",  # rule 9
    "1001w", "1000w 1ms", "7001d", "-1001w", "1000w 0.001s",  # rule 10
    "1h30x", "1y", "abc", "1hm", "1h,30m", "1min",
])
def test_invalid(text):
    with pytest.raises(DurationError):
        parse_duration(text)


def test_error_is_a_value_error():
    with pytest.raises(ValueError):
        parse_duration("nope")


@pytest.mark.parametrize("text", ["1000w", "7000d", "-1000w", "999w 6d 23h 59m 59s 999ms"])
def test_limit_is_inclusive(text):
    assert abs(parse_duration(text)) <= LIMIT


@pytest.mark.parametrize("value", [None, 90, 1.5, b"1h", ["1h"]])
def test_parse_wrong_type(value):
    with pytest.raises(TypeError):
        parse_duration(value)


@pytest.mark.parametrize(("ms", "text"), [
    (3_600_000, "1h"),
    (604_800_000, "7d"),
    (1, "1ms"),
    (999, "999ms"),
    (1000, "1s"),
    (61_000, "1m 1s"),
    (86_400_000 + 5, "1d 5ms"),
    (-1500, "-1s 500ms"),
    (-1, "-1ms"),
    (LIMIT, "7000d"),
    (-LIMIT, "-7000d"),
    (LIMIT - 1, "6999d 23h 59m 59s 999ms"),
])
def test_format(ms, text):
    assert format_duration(ms) == text


@pytest.mark.parametrize("ms", [LIMIT + 1, -LIMIT - 1, 10**30])
def test_format_beyond_limit(ms):
    with pytest.raises(DurationError):
        format_duration(ms)


@pytest.mark.parametrize("value", [1.0, "1", None, True, False])
def test_format_wrong_type(value):
    with pytest.raises(TypeError):
        format_duration(value)


@pytest.mark.parametrize("ms", [0, 1, -1, 59_999, 60_000, 3_599_999, 86_399_999, 86_400_000, 123_456_789,
                                -987_654_321, LIMIT, -LIMIT])
def test_round_trip(ms):
    assert parse_duration(format_duration(ms)) == ms
