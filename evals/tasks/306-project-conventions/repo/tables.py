"""Plain-text tables."""

__all__ = ["column_widths", "pad"]


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
