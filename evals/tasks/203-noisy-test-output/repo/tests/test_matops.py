import itertools
from fractions import Fraction

import pytest

from matops import determinant, identity, multiply, transpose

SIZES = [(r, c) for r, c in itertools.product(range(2, 13), repeat=2) if r != c]


def grid(rows, cols, seed=1):
    return [[(r * 7 + c * 3 + seed * (r + c + 1)) % 19 for c in range(cols)] for r in range(rows)]


def show(label, value):
    print(label)
    for row in value:
        print("   ", " ".join(f"{x:>6}" for x in row))


def reference_det(m):
    m = [[Fraction(x) for x in row] for row in m]
    det, n = Fraction(1), len(m)
    for i in range(n):
        pivot = next((r for r in range(i, n) if m[r][i] != 0), None)
        if pivot is None:
            return 0
        if pivot != i:
            m[i], m[pivot] = m[pivot], m[i]
            det = -det
        det *= m[i][i]
        for r in range(i + 1, n):
            factor = m[r][i] / m[i][i]
            m[r] = [x - factor * y for x, y in zip(m[r], m[i])]
    return int(det)


@pytest.mark.parametrize(("rows", "cols"), SIZES)
def test_transpose(rows, cols):
    m = grid(rows, cols)
    show("input", m)
    result = transpose(m)
    show("result", result)
    assert result == [[m[r][c] for r in range(rows)] for c in range(cols)]


@pytest.mark.parametrize(("rows", "cols"), SIZES)
def test_multiply(rows, cols):
    a, b = grid(rows, cols), grid(cols, rows, seed=2)
    show("a", a)
    show("b", b)
    result = multiply(a, b)
    show("result", result)
    assert result == [[sum(a[r][k] * b[k][c] for k in range(cols)) for c in range(rows)] for r in range(rows)]


@pytest.mark.parametrize("n", range(2, 8))
def test_determinant(n):
    m = grid(n, n, seed=n + 2)
    m[0][0] += 5
    show("input", m)
    assert determinant(m) == reference_det(m)


@pytest.mark.parametrize("n", range(1, 6))
def test_multiply_by_identity(n):
    m = grid(n, n)
    assert multiply(m, identity(n)) == m
