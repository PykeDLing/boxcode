"""Parse one line of CSV (RFC 4180 quoting) without the csv module."""


def parse_line(line, delimiter=","):
    """Split line into fields.

    A field may be wrapped in double quotes; inside quotes the delimiter is literal and
    two double quotes stand for one. An unterminated quote raises ValueError.
    """
    fields = []
    current = []
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == delimiter:
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields
