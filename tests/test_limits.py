import pytest

from draconic import DraconicInterpreter, SimpleInterpreter
from draconic.helpers import DraconicConfig
from draconic.exceptions import *


@pytest.fixture()
def i():
    config = DraconicConfig(max_loops=99999999, max_const_len=1000)  # 1000-size iterables, don't limit us by loops
    return DraconicInterpreter(config=config)


@pytest.fixture()
def e(i):
    def inner(expr):
        return i.eval(expr)

    return inner


def test_creating(i, e):
    really_long_str = 'foo' * 1000
    not_quite_as_long = 'f' * 999

    i._names['long'] = really_long_str
    i._names['lesslong'] = not_quite_as_long

    # strings
    with pytest.raises(IterableTooLong):
        e(f"'{really_long_str}'")

    # lists
    with pytest.raises(FeatureNotAvailable):  # we don't allow this
        e(f"[*long, *long]")


def test_list(i, e):
    e("long = [1] * 1000")

    with pytest.raises(IterableTooLong):
        e("long.append(1)")

    with pytest.raises(IterableTooLong):
        e("long.extend([1])")

    with pytest.raises(IterableTooLong):
        e("long.extend(long)")

    # we should always be operating using safe lists
    i.builtins['reallist'] = [1, 2, 3]
    e("my_list = [1, 2, 3]")
    assert isinstance(e("my_list + reallist"), i._list)
    assert isinstance(e("reallist + my_list"), i._list)
    e("my_list.extend(reallist)")
    assert isinstance(e("my_list"), i._list)


def test_set(i, e):
    i.builtins['range'] = range
    e("long = set(range(1000))")
    e("long2 = set(range(1000, 2000))")

    with pytest.raises(IterableTooLong):
        e("long.add(1000)")

    with pytest.raises(IterableTooLong):
        e("long.update(long2)")

    with pytest.raises(IterableTooLong):
        e("long.union(long2)")

    with pytest.raises(IterableTooLong):
        e("long.update({1000})")

    # we should always be operating using safe sets
    i.builtins['realset'] = {1, 2, 3}
    e("my_set = {3, 4, 5}")
    # these operations don't work because sets use bitwise ops and we don't allow those
    # assert isinstance(e("my_set | realset"), i._set)
    # assert isinstance(e("realset | my_set"), i._set)
    e("my_set.update(realset)")
    assert isinstance(e("my_set"), i._set)
    assert isinstance(e("my_set.union(realset)"), i._set)
