import pytest

from temperature import c_to_f, f_to_c


@pytest.mark.parametrize(("c", "f"), [(0, 32), (100, 212), (-40, -40)])
def test_both_directions(c, f):
    assert c_to_f(c) == pytest.approx(f)
    assert f_to_c(f) == pytest.approx(c)
