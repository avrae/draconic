import pytest

from draconic import DraconicInterpreter, SimpleInterpreter
from draconic.helpers import DraconicConfig
from draconic.exceptions import *


@pytest.fixture(scope='module')
def i():
    config = DraconicConfig(max_loops=99999999, max_const_len=1000)  # 1000-size iterables, don't limit us by loops
    return DraconicInterpreter(config=config)


@pytest.fixture(scope='module')
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
