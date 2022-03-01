import pytest

from draconic.exceptions import AnnotatedException
from draconic.versions import PY_39


class TestList:
    def test_type(self, i, e):
        e("a = [1, 2, 3]")
        e("b = list('123')")
        assert type(i.names['a']) is type(i.names['b']) is i._list

    def test_pop(self, e):
        e("a = [1, 2, 3]")
        assert e("a.pop()") == 3
        assert e("a") == [1, 2]

        assert e("a.pop(0)") == 1
        assert e("a") == [2]

        with pytest.raises(AnnotatedException, match='pop index out of range'):
            e("a.pop(1)")

    def test_remove(self, e):
        e("a = [1, 2, 3]")
        e("a.remove(1)")
        assert e("a") == [2, 3]

        with pytest.raises(AnnotatedException, match='not in list'):
            e("a.remove(1)")

    def test_clear(self, e):
        e("a = [1, 2, 3]")
        e("a.clear()")
        assert e("a") == []


class TestSet:
    def test_type(self, i, e):
        e("a = {1, 2, 3}")
        e("b = set('123')")
        assert type(i.names['a']) is type(i.names['b']) is i._set

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

        with pytest.raises(AnnotatedException, match='pop from an empty set'):
            e("a.pop()")

    def test_remove(self, e):
        e("a = {1, 2, 3}")
        e("a.remove(1)")
        assert e("a") == {2, 3}

        with pytest.raises(AnnotatedException, match='1'):  # KeyError
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
        e('a = {1, 2, 3}')
        e('b = {3, 4, 5}')

        assert e('a | b') == {1, 2, 3, 4, 5}

        assert e('a & b') == {3}

        assert e('a - b') == {1, 2}

        assert e('a ^ b') == {1, 2, 4, 5}


class TestDict:
    def test_type(self, i, e):
        e("a = {1: 1, 2: 2}")
        e("b = dict(((1, 1), (2, 2)))")
        assert type(i.names['a']) is type(i.names['b']) is i._dict

    def test_update(self, e):
        e("a = {1: 1, 2: 2}")

        e("a.update({3: 3})")
        assert e("a") == {1: 1, 2: 2, 3: 3}

        e("a.update(a='foo')")
        assert e("a") == {1: 1, 2: 2, 3: 3, 'a': 'foo'}

    if PY_39:
        def test_union_op(self, e):
            e('a = {"a": 1, "b": 2}')
            e('b = {"b": 3, "c": 4}')
            e('c = a.copy()')

            assert e('a | b') == {"a": 1, "b": 3, "c": 4}

            e('c |= b')
            assert e('c') == {"a": 1, "b": 3, "c": 4}
