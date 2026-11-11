"""看起来对、其实漏了几条规则的写法：strip、\\d、浮点运算、$ 能匹配行尾的换行。"""

import re

UNITS = {"w": 604_800_000, "d": 86_400_000, "h": 3_600_000, "m": 60_000, "s": 1_000, "ms": 1}
ORDER = ["w", "d", "h", "m", "s", "ms"]
LIMIT = 1000 * UNITS["w"]


class DurationError(ValueError):
    """Raised for a duration that breaks a rule in SPEC.md."""


def parse_duration(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("duration must be a str")
    match = re.match(r"^(-?)((?:\d+(?:\.\d+)?(?:ms|[wdhms]) ?)+)$", text)
    if not match:
        raise DurationError(text)
    total = 0.0
    last = -1
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|[wdhms])", match.group(2))
    for index, (number, unit) in enumerate(parts):
        rank = ORDER.index(unit)
        if rank <= last:
            raise DurationError(text)
        last = rank
        if "." in number and index != len(parts) - 1:
            raise DurationError(text)
        total += float(number) * UNITS[unit]
    if total != int(total):
        raise DurationError(text)
    if total > LIMIT:
        raise DurationError(text)
    return -int(total) if match.group(1) else int(total)


def format_duration(ms: int) -> str:
    if not isinstance(ms, int):
        raise TypeError("ms must be an int")
    if abs(ms) > LIMIT:
        raise DurationError(str(ms))
    if ms == 0:
        return "0s"
    rest = abs(ms)
    parts = []
    for unit in ORDER[1:]:
        count, rest = divmod(rest, UNITS[unit])
        if count:
            parts.append(f"{count}{unit}")
    return ("-" if ms < 0 else "") + " ".join(parts)
