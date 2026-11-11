"""Plain-text tables."""

__all__ = ["column_widths", "pad", "parse_table", "render_table"]


def column_widths(rows: list[list[str]]) -> list[int]:
    """The width of each column: the length of its longest cell. All rows must have the same number of cells."""
    if not rows:
        return []
    if len({len(row) for row in rows}) != 1:
        raise ValueError("rows have different numbers of cells")
    return [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]


def pad(cell: str, width: int, align: str = "l") -> str:
    """Pad a cell with spaces to `width`. align is "l", "r" or "c"; when centring, the extra space goes right."""
    if align == "l":
        return cell.ljust(width)
    if align == "r":
        return cell.rjust(width)
    if align == "c":
        left = (width - len(cell)) // 2
        return " " * left + cell + " " * (width - len(cell) - left)
    raise ValueError(f"unknown alignment: {align!r}")


def _line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def render_table(rows: list[list[str]], headers: list[str] | None = None, align: str = "") -> str:
    """Render rows (and optional headers) as a text table; see docs/DESIGN.md."""
    everything = ([headers] if headers is not None else []) + rows
    widths = column_widths(everything)
    if len(align) > len(widths) or any(letter not in "lrc" for letter in align):
        raise ValueError(f"bad alignment: {align!r}")
    aligns = align + "l" * (len(widths) - len(align))
    lines = [_line([pad(cell, width, how) for cell, width, how in zip(row, widths, aligns)]) for row in everything]
    if headers is not None:
        lines.insert(1, _line(["-" * width for width in widths]))
    return "\n".join(lines)


def parse_table(text: str) -> list[list[str]]:
    """Read a table written by render_table back into rows; see docs/DESIGN.md."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) < 2 or not (line.startswith("|") and line.endswith("|")):
            raise ValueError(f"not a table row: {line!r}")
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if all(cell and set(cell) == {"-"} for cell in cells):
            continue
        rows.append(cells)
    if len({len(row) for row in rows}) > 1:
        raise ValueError("rows have different numbers of cells")
    return rows
