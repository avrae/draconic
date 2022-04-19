from draconic.helpers import zip_star
from . import utils


def test_zip_star_start():
    # star at start
    result = zip_star(["a", "b", "c"], [1, 2, 3, 4], star_index=0)
    assert list(result) == [("a", [1, 2]), ("b", 3), ("c", 4)]

    result = zip_star(["a", "b", "c"], [1, 2, 3], star_index=0)
    assert list(result) == [("a", [1]), ("b", 2), ("c", 3)]

    result = zip_star(["a", "b", "c"], [1, 2], star_index=0)
    assert list(result) == [("a", []), ("b", 1), ("c", 2)]


def test_zip_star_middle():
    # star in middle
    result = zip_star(["a", "b", "c"], [1, 2, 3, 4], star_index=1)
    assert list(result) == [("a", 1), ("b", [2, 3]), ("c", 4)]

    result = zip_star(["a", "b", "c"], [1, 2, 3], star_index=1)
    assert list(result) == [("a", 1), ("b", [2]), ("c", 3)]

    result = zip_star(["a", "b", "c"], [1, 2], star_index=1)
    assert list(result) == [("a", 1), ("b", []), ("c", 2)]


def test_zip_star_end():
    # star at end
    result = zip_star(["a", "b", "c"], [1, 2, 3, 4], star_index=2)
    assert list(result) == [("a", 1), ("b", 2), ("c", [3, 4])]

    result = zip_star(["a", "b", "c"], [1, 2, 3], star_index=2)
    assert list(result) == [("a", 1), ("b", 2), ("c", [3])]

    result = zip_star(["a", "b", "c"], [1, 2], star_index=2)
    assert list(result) == [("a", 1), ("b", 2), ("c", [])]


def test_zip_star_only():
    # star only
    result = zip_star(["a"], [1, 2, 3], star_index=0)
    assert list(result) == [("a", [1, 2, 3])]


def test_zip_star_invalid():
    with utils.raises(IndexError):
        next(zip_star(["a", "b", "c"], [1, 2, 3], star_index=3))

    with utils.raises(ValueError):
        next(zip_star(["a", "b", "c"], [1], star_index=0))
