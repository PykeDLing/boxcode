import re

UNITS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Parse a duration such as "45s", "1h30m" or "2h5m10s" into seconds."""
    total = 0
    for amount, unit in re.findall(r"(\d)([hms])", text):
        total += int(amount) * UNITS[unit]
    return total
