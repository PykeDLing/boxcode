"""A token-bucket rate limiter."""


class TokenBucket:
    """Holds up to `capacity` tokens and gains `rate` tokens per second, starting full.

    `clock` is a zero-argument callable returning the current time in seconds.

    allow(cost=1) refills according to the time elapsed, then, if at least `cost` tokens
    are available, removes them and returns True; otherwise it removes nothing and returns False.
    available() returns the current number of tokens after refilling.
    rate and capacity must be positive and cost must not be negative, otherwise raise ValueError.
    """

    def __init__(self, rate, capacity, clock):
        raise NotImplementedError

    def allow(self, cost=1):
        raise NotImplementedError

    def available(self):
        raise NotImplementedError
