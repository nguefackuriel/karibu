"""French numbers spoken out loud, which is how a host gives their price."""

import pytest

from hub.services.numbers import parse, runs

@pytest.mark.parametrize(
    "spoken,expected",
    [
        ("deux", 2), ("huit", 8), ("dix", 10), ("quinze", 15),
        ("vingt", 20), ("vingt-cinq", 25),
        ("soixante-dix", 70), ("quatre-vingts", 80), ("quatre-vingt-dix", 90),
        ("cent", 100), ("cent cinquante", 150), ("deux cents", 200),
        ("mille", 1000), ("huit mille", 8000), ("dix mille", 10000),
        ("quinze mille", 15000), ("quatre-vingt mille", 80000),
        ("huit mille cinq cents", 8500), ("douze mille cinq cents", 12500),
        ("8000", 8000), ("8 000", 8000),
    ],
)
def test_spoken_numbers(spoken, expected):
    assert parse(spoken) == expected


def test_no_number_at_all():
    assert parse("bonjour je suis la") is None


def test_several_numbers_are_kept_apart():
    values = [value for value, _, _ in runs("j'ai deux chambres a huit mille francs")]
    assert values == [2, 8000]
