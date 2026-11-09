import pytest

from backoff import delay
from retry import retry


def flaky(failures, result="ok", error=ConnectionError):
    calls = []

    def fn():
        calls.append(1)
        if len(calls) <= failures:
            raise error("boom")
        return result

    return fn, calls


def test_delay_sequence():
    assert [delay(n) for n in (1, 2, 3, 4)] == [1.0, 2.0, 4.0, 8.0]


def test_delay_is_capped():
    assert delay(20) == 30.0


def test_succeeds_on_last_attempt():
    fn, calls = flaky(2)
    sleeps = []
    assert retry(fn, attempts=3, sleep=sleeps.append) == "ok"
    assert len(calls) == 3 and sleeps == [1.0, 2.0]


def test_exhausted_raises_last_error_without_final_sleep():
    fn, calls = flaky(5)
    sleeps = []
    with pytest.raises(ConnectionError):
        retry(fn, attempts=2, sleep=sleeps.append)
    assert len(calls) == 2 and sleeps == [1.0]


def test_single_attempt():
    fn, calls = flaky(0)
    assert retry(fn, attempts=1, sleep=lambda s: None) == "ok" and len(calls) == 1


def test_other_errors_propagate():
    fn, calls = flaky(1, error=ValueError)
    with pytest.raises(ValueError):
        retry(fn, attempts=3, sleep=lambda s: None)
    assert len(calls) == 1
