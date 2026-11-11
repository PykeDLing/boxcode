# Duration strings

`durations.py` converts between duration strings such as `1h 30m` and integer milliseconds.

## parse_duration(text)

Returns the duration as an `int` number of milliseconds. Raises `TypeError` if `text` is not a `str`, and
`DurationError` (a subclass of `ValueError`, already defined in `durations.py`) if it breaks any rule below.

1. A duration is an optional sign followed by one or more components. A component is a number immediately
   followed by a unit: `90m`, `1500ms`.
2. The units are `w` (7 days), `d` (24 hours), `h`, `m`, `s` and `ms`. Units are case-sensitive: `1H` is an error.
3. Components must go from the largest unit to the smallest and a unit may appear at most once:
   `1h30m` is valid; `30m1h` and `1h2h` are errors.
4. Components may be separated by exactly one space character: `1h 30m` is valid. No other whitespace is allowed
   anywhere: not between a number and its unit (`1 h`), not at the start or the end (` 1h`, `1h `, `1h\n`),
   not two spaces in a row, and no tabs.
5. A number is one or more ASCII digits `0`-`9`; leading zeros are allowed (`007s` is 7 seconds). Digits from
   other scripts (for example `١` or `１`) are errors.
6. Only the last component may have a fraction, written as a dot with at least one digit on each side:
   `1.5h` and `1h 0.25m` are valid; `1.5h30m`, `.5h` and `1.h` are errors.
7. The value of a fractional component must be a whole number of milliseconds, computed exactly (no floating
   point error): `1.5s` is 1500, `4.35s` is 4350 and `0.57m` is 34200; `0.0005s` and `1.5ms` are errors.
8. The only sign is a leading `-`, which negates the whole duration: `-1h30m` is -5400000 and `-0s` is 0.
   `+1h` is an error, and so is a sign that is not immediately followed by the first component (`- 1h`, `1h-30m`).
9. The empty string, a number without a unit (`90`) and a unit without a number (`h`) are errors.
10. The absolute value must not exceed 1000 weeks: `1000w` and `7000d` are valid; `1001w` and `1000w 1ms` are errors.

## format_duration(ms)

11. Returns the canonical string for `ms` milliseconds. It uses the units `d`, `h`, `m`, `s` and `ms` (never `w`),
    largest first, separated by one space, and leaves out units whose count is zero:
    `90061001` is `1d 1h 1m 1s 1ms`, `3600000` is `1h`, `604800000` is `7d`.
12. Zero is `0s`. A negative value is the positive form with a leading `-`: `-1500` is `-1s 500ms`.
    The result never contains a fraction, and `parse_duration(format_duration(n)) == n` for every valid `n`.
13. Raises `TypeError` if `ms` is not an `int` (`bool` is not accepted either), and `DurationError` if its absolute
    value exceeds the limit in rule 10.
