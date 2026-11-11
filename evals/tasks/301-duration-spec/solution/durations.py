"""Duration strings. The rules are in SPEC.md."""

import re

UNITS = {"w": 604_800_000, "d": 86_400_000, "h": 3_600_000, "m": 60_000, "s": 1_000, "ms": 1}
ORDER = ["w", "d", "h", "m", "s", "ms"]
LIMIT = 1000 * UNITS["w"]
_COMPONENT = re.compile(r"([0-9]+)(?:\.([0-9]+))?(ms|[wdhms])")


class DurationError(ValueError):
    """Raised for a duration that breaks a rule in SPEC.md."""


def parse_duration(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("duration must be a str")
    body = text[1:] if text.startswith("-") else text
    if not body:
        raise DurationError(f"invalid duration: {text!r}")
    total = 0
    position = 0
    last_rank = -1
    fraction_seen = False
    while position < len(body):
        if position > 0 and body[position] == " ":
            position += 1
        match = _COMPONENT.match(body, position)
        if match is None or fraction_seen:
            raise DurationError(f"invalid duration: {text!r}")
        whole, fraction, unit = match.groups()
        rank = ORDER.index(unit)
        if rank <= last_rank:
            raise DurationError(f"units out of order in {text!r}")
        last_rank = rank
        total += int(whole) * UNITS[unit]
        if fraction is not None:
            fraction_seen = True
            numerator = int(fraction) * UNITS[unit]
            denominator = 10 ** len(fraction)
            if numerator % denominator:
                raise DurationError(f"not a whole number of milliseconds: {text!r}")
            total += numerator // denominator
        position = match.end()
    if total > LIMIT:
        raise DurationError(f"duration too large: {text!r}")
    return -total if text.startswith("-") else total


def format_duration(ms: int) -> str:
    if type(ms) is not int:
        raise TypeError("ms must be an int")
    if abs(ms) > LIMIT:
        raise DurationError(f"duration too large: {ms}")
    if ms == 0:
        return "0s"
    rest = abs(ms)
    parts = []
    for unit in ORDER[1:]:
        count, rest = divmod(rest, UNITS[unit])
        if count:
            parts.append(f"{count}{unit}")
    return ("-" if ms < 0 else "") + " ".join(parts)
