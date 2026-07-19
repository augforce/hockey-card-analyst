"""Tests for shared scale helpers.

The ordinal suffix is the kind of thing tests miss because nobody asserts it -
it slipped through once as "72th". One small test here so it doesn't slip again
as claim reasons and comparison output reuse it.
"""
import pytest

from engine.common import ordinal

CASES = [
    (1, "1st"),
    (2, "2nd"),
    (3, "3rd"),
    (4, "4th"),
    (11, "11th"),
    (12, "12th"),
    (13, "13th"),
    (21, "21st"),
    (22, "22nd"),
    (23, "23rd"),
    (33, "33rd"),
    (72, "72nd"),
    (95, "95th"),
    (100, "100th"),
]


@pytest.mark.parametrize("n,expected", CASES)
def test_ordinal(n, expected):
    assert ordinal(n) == expected
