from duration import parse_duration


def test_seconds():
    assert parse_duration("45s") == 45
    assert parse_duration("90s") == 90


def test_combined():
    assert parse_duration("1h30m") == 5400
    assert parse_duration("2h5m10s") == 7510
