"""Matrix helpers on plain lists of lists."""


def identity(n):
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def transpose(m):
    """Rows become columns. m may be rectangular."""
    return [[m[j][i] for j in range(len(m))] for i in range(len(m))]


def multiply(a, b):
    """Matrix product; the number of columns of a equals the number of rows of b."""
    rows, cols = len(a), len(b[0])
    return [[sum(a[r][k] * b[k][c] for k in range(rows)) for c in range(cols)] for r in range(rows)]


def determinant(m):
    """Determinant of a square matrix by cofactor expansion along the first row."""
    if len(m) == 1:
        return m[0][0]
    if len(m) == 2:
        return m[0][0] * m[1][1] + m[0][1] * m[1][0]
    total = 0
    for i, value in enumerate(m[0]):
        minor = [row[:i] + row[i + 1:] for row in m[1:]]
        total += (-1) ** i * value * determinant(minor)
    return total
