"""Retry a callable on transient errors."""

import time

from backoff import delay


def retry(fn, attempts=3, sleep=time.sleep, retry_on=(ConnectionError, TimeoutError)):
    """Call fn() at most `attempts` times in total and return its first successful result.

    Sleep between attempts only, never after the last one. Errors not listed in retry_on
    propagate immediately. When every attempt fails, the last error is raised.
    """
    last = None
    for attempt in range(1, attempts):
        try:
            return fn()
        except retry_on as e:
            last = e
            sleep(delay(attempt))
    raise last
