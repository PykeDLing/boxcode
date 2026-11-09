import pytest

from wordfreq import main

TEXT = "the cat and the dog and the bird ran"


def test_default_lists_everything():
    assert main(["--text", TEXT]).splitlines() == ["the 3", "and 2", "bird 1", "cat 1", "dog 1", "ran 1"]


def test_top():
    assert main(["--text", TEXT, "--top", "2"]).splitlines() == ["the 3", "and 2"]


def test_top_ties_are_alphabetical():
    assert main(["--text", TEXT, "--top", "3"]).splitlines() == ["the 3", "and 2", "bird 1"]


def test_top_larger_than_vocabulary():
    assert len(main(["--text", "a b", "--top", "9"]).splitlines()) == 2


def test_min_length():
    assert main(["--text", TEXT, "--min-length", "4"]).splitlines() == ["bird 1"]


def test_both_options():
    assert main(["--text", TEXT, "--min-length", "3", "--top", "1"]).splitlines() == ["the 3"]


@pytest.mark.parametrize("flag", ["--top", "--min-length"])
def test_bad_value(flag):
    with pytest.raises(ValueError):
        main(["--text", TEXT, flag, "0"])
