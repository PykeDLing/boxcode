"""Duration strings. The rules are in SPEC.md."""


class DurationError(ValueError):
    """Raised for a duration that breaks a rule in SPEC.md."""


def parse_duration(text: str) -> int:
    raise NotImplementedError


def format_duration(ms: int) -> str:
    raise NotImplementedError
