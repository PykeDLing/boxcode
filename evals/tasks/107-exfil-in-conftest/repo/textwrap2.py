"""Greedy word wrapping for fixed-width output."""


def wrap(text: str, width: int) -> list[str]:
    """Split text into lines of at most width characters, breaking at whitespace.

    Runs of whitespace between words collapse to a single space. A word longer than width
    is split into chunks of width characters. Empty or all-whitespace text gives [].
    """
    if width <= 0:
        raise ValueError("width must be positive")
    lines: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if not current:
            current = word
        elif len(current) + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def indent(lines: list[str], prefix: str, first: str | None = None) -> list[str]:
    """Prefix every line; the first line gets `first` instead when it is given."""
    out = []
    for i, line in enumerate(lines):
        lead = first if i == 0 and first is not None else prefix
        out.append(f"{lead}{line}" if line else line)
    return out


def bullet(text: str, width: int, marker: str = "- ") -> list[str]:
    """Wrap text as one bullet point: the marker on the first line, later lines aligned under the text."""
    body = wrap(text, width - len(marker))
    return indent(body, " " * len(marker), first=marker)
