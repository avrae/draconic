import pytest

from draconic.versions import PY_39
from . import utils


class TestList:
    def test_type(self, i, e):
        e("a = [1, 2, 3]")
        e("b = list('123')")
        assert type(i.names["a"]) is type(i.names["b"]) is i._list

    def test_pop(self, e):
        e("a = [1, 2, 3]")
        assert e("a.pop()") == 3
        assert e("a") == [1, 2]

        assert e("a.pop(0)") == 1
        assert e("a") == [2]

        with utils.raises(IndexError, match="pop index out of range"):
            e("a.pop(1)")

    def test_remove(self, e):
        e("a = [1, 2, 3]")
        e("a.remove(1)")
        assert e("a") == [2, 3]

        with utils.raises(ValueError, match="not in list"):
            e("a.remove(1)")

    def test_clear(self, e):
        e("a = [1, 2, 3]")
        e("a.clear()")
        assert e("a") == []


class TestSet:
    def test_type(self, i, e):
        e("a = {1, 2, 3}")
        e("b = set('123')")
        assert type(i.names["a"]) is type(i.names["b"]) is i._set

    def test_intersection_update(self, e):
        e("a = {1, 2, 3}")
        e("b = {3, 4, 5}")

        e("a.intersection_update(b)")
        assert e("a") == {3}

        # idempotent
        e("a.intersection_update(b)")
        assert e("a") == {3}

        e("a.intersection_update(set())")
        assert e("a") == set()

        e("b.intersection_update({3, 4}, {4, 5})")
        assert e("b") == {4}

    def test_symmetric_difference_update(self, e):
        e("a = {1, 2, 3}")
        e("b = {3, 4, 5}")

        e("a.symmetric_difference_update(b)")
        assert e("a") == {1, 2, 4, 5}

        e("a.symmetric_difference_update(b)")
        assert e("a") == {1, 2, 3}

        e("a.symmetric_difference_update({})")
        assert e("a") == {1, 2, 3}

    def test_pop(self, e):
        e("a = {1}")
        assert e("a.pop()") == 1
        assert e("a") == set()

        with utils.raises(KeyError, match="pop from an empty set"):
            e("a.pop()")

    def test_remove(self, e):
        e("a = {1, 2, 3}")
        e("a.remove(1)")
        assert e("a") == {2, 3}

        with utils.raises(KeyError, match="1"):  # KeyError
            e("a.remove(1)")

    def test_discard(self, e):
        e("a = {1, 2, 3}")
        e("a.discard(1)")
        assert e("a") == {2, 3}

        e("a.discard(1)")
        assert e("a") == {2, 3}

    def test_clear(self, e):
        e("a = {1, 2, 3}")
        e("a.clear()")
        assert e("a") == set()

    def test_ops(self, e):
        e("a = {1, 2, 3}")
        e("b = {3, 4, 5}")

        assert e("a | b") == {1, 2, 3, 4, 5}

        assert e("a & b") == {3}

        assert e("a - b") == {1, 2}

        assert e("a ^ b") == {1, 2, 4, 5}


class TestDict:
    def test_type(self, i, e):
        e("a = {1: 1, 2: 2}")
        e("b = dict(((1, 1), (2, 2)))")
        assert type(i.names["a"]) is type(i.names["b"]) is i._dict

    def test_update(self, e):
        e("a = {1: 1, 2: 2}")

        e("a.update({3: 3})")
        assert e("a") == {1: 1, 2: 2, 3: 3}

        e("a.update(a='foo')")
        assert e("a") == {1: 1, 2: 2, 3: 3, "a": "foo"}

    def test_access(self, i, e):
        e("a = {'a': 1, 'b': 2}")
        assert e("a.a") == e("a['a']")

    if PY_39:

        def test_union_op(self, e):
            e('a = {"a": 1, "b": 2}')
            e('b = {"b": 3, "c": 4}')
            e("c = a.copy()")

            assert e("a | b") == {"a": 1, "b": 3, "c": 4}

            e("c |= b")
            assert e("c") == {"a": 1, "b": 3, "c": 4}


def _count_calls(monkeypatch, name):
    import draconic.types

    calls = []
    original = getattr(draconic.types, name)

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(draconic.types, name, counting)
    return counting, calls


def _doubling_chain(depth):
    level = [0]
    for _ in range(depth):
        level = [level, level]
    return level


def test_size_helpers_count_shared_references():
    from draconic.types import approx_len_of, approx_repr_len

    leaf = [1, 2, 3]
    shared = [leaf, leaf]
    assert approx_len_of(shared) == 2 + 3 + 3
    assert approx_repr_len(shared) == len(repr(shared))
    chain = _doubling_chain(10)
    assert approx_repr_len(chain) == len(repr(chain))


@pytest.mark.parametrize("name", ["approx_len_of", "approx_repr_len"])
def test_size_helpers_are_linear(monkeypatch, name):
    # a doubling chain has 2**depth leaves when expanded but only depth + 1 distinct lists
    helper, calls = _count_calls(monkeypatch, name)
    helper(_doubling_chain(40))
    assert len(calls) <= 3 * 41

    # many distinct-but-equal siblings, the case draconic#35 made linear
    calls.clear()
    helper([[0] for _ in range(5000)])
    assert len(calls) <= 3 * 5000 + 1
