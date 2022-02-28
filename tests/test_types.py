from draconic.versions import PY_39


class TestList:
    def test_type(self, i, e):
        e("a = [1, 2, 3]")
        e("b = list('123')")
        assert type(i.names['a']) is type(i.names['b']) is i._list


class TestSet:
    def test_type(self, i, e):
        e("a = {1, 2, 3}")
        e("b = set('123')")
        assert type(i.names['a']) is type(i.names['b']) is i._set

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

    if PY_39:
        def test_union_op(self, e):
            e('a = {"a": 1, "b": 2}')
            e('b = {"b": 3, "c": 4}')
            e('c = a.copy()')

            assert e('a | b') == {"a": 1, "b": 3, "c": 4}

            e('c |= b')
            assert e('c') == {"a": 1, "b": 3, "c": 4}
