"""Exponential backoff."""


def delay(attempt, base=1.0, factor=2.0, cap=30.0):
    """Seconds to wait after failed attempt number `attempt` (1-based): base, base*factor, ... at most cap."""
    return min(base * factor ** attempt, cap)
