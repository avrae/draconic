import textwrap

import pytest

from draconic import DraconicInterpreter
from draconic.helpers import DraconicConfig


@pytest.fixture()
def i():
    config = DraconicConfig()
    inter = DraconicInterpreter(config=config)

    inter.out__ = []

    def foo(v):
        inter.out__.append(v)

    inter.builtins['print'] = foo
    inter.builtins['range'] = range
    return inter


@pytest.fixture()
def e(i):
    def inner(expr):
        return i.eval(expr)

    return inner


@pytest.fixture()
def ex(i):
    def inner(expr):
        i.out__ = []
        return i.execute(textwrap.dedent(expr))

    return inner
